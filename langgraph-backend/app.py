from telemetry import init_telemetry

init_telemetry()

from opentelemetry import trace
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Annotated, TypedDict
import logging

AnthropicInstrumentor().instrument()

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.errors import GraphRecursionError

from tools import ALL_TOOLS

logger = logging.getLogger("langgraph-backend")
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

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
RECURSION_LIMIT = 25


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int


@app.on_event("startup")
def startup_event():
    logger.info("LangGraph backend starting")
    try:
        app.state.graph = build_graph()
        logger.info("LangGraph agent graph compiled successfully")
    except Exception as exc:
        logger.exception("Error building LangGraph graph: %s", exc)
        raise


@app.on_event("shutdown")
def shutdown_event():
    provider = trace.get_tracer_provider()
    if provider:
        provider.shutdown()
        logger.info("Tracer provider shut down")


def build_graph():
    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def agent_node(state: AgentState) -> dict:
        """Calls the LLM with the running message history. Every pass through
        this node is one iteration of the agent loop, and gets its own span
        so you can see, per iteration, how many tokens the call used and
        whether it decided to call a tool or answer."""
        iteration = state.get("iteration", 0) + 1
        with tracer.start_as_current_span(
            "langgraph.node.agent",
            attributes={
                "langgraph.node.name": "agent",
                "langgraph.iteration": iteration,
            },
        ) as span:
            response = llm_with_tools.invoke(state["messages"])

            usage = getattr(response, "usage_metadata", None) or {}
            span.set_attribute("gen_ai.usage.input_tokens", usage.get("input_tokens", 0))
            span.set_attribute("gen_ai.usage.output_tokens", usage.get("output_tokens", 0))

            tool_calls = getattr(response, "tool_calls", None) or []
            span.set_attribute("langgraph.agent.requested_tool_calls", len(tool_calls))
            if tool_calls:
                span.set_attribute(
                    "langgraph.agent.requested_tools",
                    ",".join(tc["name"] for tc in tool_calls),
                )

        return {"messages": [response], "iteration": iteration}

    def tools_node(state: AgentState) -> dict:
        """Executes every tool call the agent just requested. One span per
        pass through this node, with the tool names and count as attributes,
        so a slow or repeated loop is easy to spot in the trace waterfall."""
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None) or []
        tool_names = ",".join(tc["name"] for tc in tool_calls)

        with tracer.start_as_current_span(
            "langgraph.node.tools",
            attributes={
                "langgraph.node.name": "tools",
                "langgraph.iteration": state.get("iteration", 0),
                "langgraph.tool.names": tool_names,
                "langgraph.tool.count": len(tool_calls),
            },
        ):
            outputs = []
            for tc in tool_calls:
                tool_fn = TOOLS_BY_NAME.get(tc["name"])
                if tool_fn is None:
                    result = f"Unknown tool: {tc['name']}"
                else:
                    with tracer.start_as_current_span(
                        f"langgraph.tool.{tc['name']}",
                        attributes={"langgraph.tool.args": str(tc["args"])},
                    ):
                        result = tool_fn.invoke(tc["args"])
                outputs.append(
                    ToolMessage(content=str(result), tool_call_id=tc["id"], name=tc["name"])
                )

        return {"messages": outputs}

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: dict):
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing question field")

    graph = getattr(app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=500, detail="Agent graph not initialized")

    with tracer.start_as_current_span("chat.request", attributes={"user.question": question}) as span:
        try:
            result = graph.invoke(
                {"messages": [HumanMessage(content=question)], "iteration": 0},
                config={"recursion_limit": RECURSION_LIMIT},
            )
        except GraphRecursionError:
            logger.warning("Agent hit the recursion limit (%s) without finishing", RECURSION_LIMIT)
            return JSONResponse(
                status_code=500,
                content={"error": f"Agent did not finish within {RECURSION_LIMIT} steps. Check the trace for a loop."},
            )
        except Exception as exc:
            logger.exception("LangGraph invocation failed: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"error": "Anthropic request failed or agent failed. Check logs for details."},
            )

        answer = result["messages"][-1].content
        iterations = result.get("iteration", 0)
        span.set_attribute("langgraph.total_iterations", iterations)

        trace_id = format(span.get_span_context().trace_id, "032x")
        feedback_store[trace_id] = {"question": question}
        return {"answer": answer, "trace_id": trace_id, "iterations": iterations}


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
