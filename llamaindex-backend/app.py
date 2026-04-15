from telemetry import init_telemetry

init_telemetry()

from opentelemetry import trace
from opentelemetry.instrumentation.llamaindex import LlamaIndexInstrumentor
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

LlamaIndexInstrumentor().instrument()
AnthropicInstrumentor().instrument()

from llama_index.core import Settings, StorageContext, load_index_from_storage
from llama_index.llms.anthropic import Anthropic
from llama_index.embeddings.fastembed import FastEmbedEmbedding

from ingest import ingest_documents

Settings.llm = Anthropic(model="claude-haiku-4-5-20251001", temperature=0)
Settings.embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")

logger = logging.getLogger("llamaindex-backend")
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
    logger.info("LlamaIndex backend starting")
    storage_dir = Path("./llamaindex_storage")
    if not storage_dir.exists() or not any(storage_dir.iterdir()):
        logger.info("LlamaIndex storage not found, running ingestion")
        ingest_documents(force=False)

    try:
        load_index()
        logger.info("LlamaIndex index loaded successfully")
    except Exception as exc:
        logger.exception("Error loading LlamaIndex index: %s", exc)
        raise


@app.on_event("shutdown")
def shutdown_event():
    provider = trace.get_tracer_provider()
    if provider:
        provider.shutdown()
        logger.info("Tracer provider shut down")


def load_index():
    storage_context = StorageContext.from_defaults(persist_dir="./llamaindex_storage")
    index = load_index_from_storage(storage_context)
    app.state.index = index


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: dict):
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing question field")

    if not getattr(app.state, "index", None):
        raise HTTPException(status_code=500, detail="Index not initialized")

    with tracer.start_as_current_span("chat.request", attributes={"user.question": question}) as span:
        try:
            query_engine = app.state.index.as_query_engine(similarity_top_k=4)
            response = query_engine.query(question)
            answer = str(response)
            trace_id = format(span.get_span_context().trace_id, "032x")
            feedback_store[trace_id] = {"question": question}
            return {"answer": answer, "trace_id": trace_id, "sources": []}
        except Exception as exc:
            logger.exception("LlamaIndex query failed: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"error": "Anthropic request failed or index query failed. Check logs for details."},
            )


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
