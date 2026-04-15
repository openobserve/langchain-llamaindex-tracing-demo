from telemetry import init_telemetry

init_telemetry()

from opentelemetry import trace
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

AnthropicInstrumentor().instrument()

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS

from ingest import ingest_documents

logger = logging.getLogger("langchain-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

tracer = trace.get_tracer(__name__)
feedback_store = {}


@app.on_event("startup")
def startup_event():
    logger.info("LangChain backend starting")
    faiss_dir = Path("./faiss_index")
    if not faiss_dir.exists() or not any(faiss_dir.iterdir()):
        logger.info("FAISS index not found, running ingestion")
        ingest_documents(force=False)

    try:
        build_chain()
        logger.info("LangChain chain built successfully")
    except Exception as exc:
        logger.exception("Error building LangChain chain: %s", exc)
        raise


@app.on_event("shutdown")
def shutdown_event():
    provider = trace.get_tracer_provider()
    if provider:
        provider.shutdown()
        logger.info("Tracer provider shut down")


def build_chain():
    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    vectorstore = FAISS.load_local(
        "./faiss_index",
        embeddings,
        allow_dangerous_deserialization=True,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    prompt = ChatPromptTemplate.from_template(
        """
Answer the question based on this context:
{context}

Question: {question}
"""
    )

    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
    chain = (
        RunnableParallel(
            context=retriever,
            question=RunnablePassthrough()
        )
        | prompt
        | llm
        | StrOutputParser()
    )
    app.state.chain = chain
    app.state.retriever = retriever


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: dict):
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing question field")

    retriever = getattr(app.state, "retriever", None)
    if retriever is None:
        raise HTTPException(status_code=500, detail="Retriever not initialized")

    sources = []
    try:
        docs = retriever.get_relevant_documents(question)
        sources = [doc.metadata.get("source", doc.page_content[:120]) for doc in docs]
    except Exception:
        sources = []

    with tracer.start_as_current_span("chat.request", attributes={"user.question": question}) as span:
        try:
            answer = app.state.chain.invoke(question)
        except Exception as exc:
            logger.exception("LangChain invocation failed: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"error": "Anthropic request failed or chain failed. Check logs for details."},
            )
        trace_id = format(span.get_span_context().trace_id, "032x")
        feedback_store[trace_id] = {"question": question}
        return {"answer": answer, "trace_id": trace_id, "sources": sources}


@app.post("/feedback")
def feedback(payload: dict):
    trace_id = payload.get("trace_id")
    rating = payload.get("rating")
    comment = payload.get("comment", "")
    if not trace_id or rating not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="Invalid feedback payload")

    attributes = {
        "feedback.rating": rating,
        "feedback.comment": comment,
        "linked_trace_id": trace_id,
    }
    if trace_id in feedback_store:
        attributes["feedback.question"] = feedback_store[trace_id].get("question", "")

    with tracer.start_as_current_span("feedback", attributes=attributes):
        logger.info("Feedback recorded for trace %s: %s", trace_id, rating)
        return {"status": "recorded"}
