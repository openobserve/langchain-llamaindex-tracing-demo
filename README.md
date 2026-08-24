# OpenObserve LangChain / LlamaIndex / LangGraph Tracing Demo

A runnable demo showing how to trace LangChain and LlamaIndex RAG apps, and a LangGraph tool-calling agent, with OpenLLMetry instrumentation, OpenTelemetry OTLP export, and OpenObserve.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com)

## What this demo shows

- A LangChain backend, a LlamaIndex backend, and a LangGraph agent backend, all exposing the same `/chat`, `/feedback`, and `/health` API.
- OpenLLMetry auto-instrumentation for LangChain, LlamaIndex, and Anthropic, with traces exported over OTLP to OpenObserve.
- For the LangGraph backend specifically: a manual span per graph node (`agent`, `tools`) tagged with `langgraph.iteration`, so you can see exactly how many times the agent looped, what it called each pass, and the input/output token count per LLM call, in the trace waterfall.
- A simple browser frontend that sends questions, shows answers, records thumbs-up/thumbs-down feedback, and returns trace IDs.
- A Docker Compose stack that starts your chosen backend and the frontend locally.

## Architecture

```
Frontend -> Backend API -> OpenLLMetry instrumentation -> OpenTelemetry SDK -> OpenObserve
```

- Frontend: static HTML/JS chat UI
- Backend: LangChain, LlamaIndex, or LangGraph service (your choice at startup)
- LLM: Anthropic Claude (`claude-haiku-4-5-20251001`)
- Embeddings (LangChain/LlamaIndex only): `fastembed` with `BAAI/bge-small-en-v1.5` (local ONNX, no GPU needed)
- Tools (LangGraph only): mocked, deliberately dependent trip-planning tools (airport lookup, weather, flight price, currency conversion) that force more than one agent -> tools loop per question
- Instrumentation: `AnthropicInstrumentor` on all three backends; `LlamaIndexInstrumentor` additionally on the LlamaIndex backend; manual per-node spans on the LangGraph backend
- Export: OTLP HTTP exporter to OpenObserve

## Prerequisites

- Docker and Docker Compose
- An OpenObserve account (cloud or self-hosted)
- An Anthropic API key

## Quick start

1. Clone the repo.

2. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

3. Generate your `OPENOBSERVE_AUTH_TOKEN`:
   ```bash
   echo -n "you@example.com:yourpassword" | base64
   ```
   Then set it in `.env` as:
   ```
   OPENOBSERVE_AUTH_TOKEN=Basic <base64-value>
   ```

4. Run the demo:
   ```bash
   ./run.sh
   ```
   You will be prompted to choose LangChain, LlamaIndex, or LangGraph. Only the chosen backend starts.

5. Open http://localhost:3000 and ask a question.

   To see the LangGraph agent actually loop, ask something that needs more than one tool in sequence, for example:
   > What's the weather in Tokyo, and what would a flight from New York cost in yen?

   The agent has to look up airport codes before it can call weather, price, or currency conversion, so a question like this takes 3-4 passes through the agent node, each one its own span.

## Switching between backends

Run `./run.sh` again and pick a different option. The script sets `BACKEND_URL` automatically so the frontend always points to the running backend.

- LangChain backend runs on port `8001`
- LlamaIndex backend runs on port `8002`
- LangGraph backend runs on port `8003`

## What you will see in OpenObserve

- A trace for each `/chat` request.
- **LangChain / LlamaIndex:** nested spans for the retrieval, prompt generation, and Anthropic API call.
- **LangGraph:** a `langgraph.node.agent` span per loop iteration (tagged with `langgraph.iteration`) and a `langgraph.node.tools` span per tool-execution pass, each containing the Anthropic call or tool invocation as a child span. `langgraph.total_iterations` on the parent `chat.request` span tells you how many loops the whole request took without opening the waterfall.
- `gen_ai.*` attributes on LLM spans such as prompt tokens and completion tokens (also copied onto the LangGraph agent-node span directly, from the response's `usage_metadata`, so per-iteration token cost doesn't require digging into the nested Anthropic span).
- A separate feedback span linking back to the original trace via `linked_trace_id`.

## How it works

This demo is built as a four-layer observability pipeline:

1. Application code: LangChain/LlamaIndex RAG chain, or a LangGraph tool-calling agent.
2. OpenLLMetry instrumentation: `AnthropicInstrumentor` on every backend (+ `LlamaIndexInstrumentor` for the LlamaIndex backend), plus manual spans around each LangGraph node so the loop structure itself shows up in the trace, not just the LLM calls inside it.
3. OpenTelemetry SDK: `TracerProvider`, `BatchSpanProcessor`, `OTLPSpanExporter`.
4. OpenObserve: receives OTLP traces and stores them.

For details, see `docs/architecture.md`.

## Troubleshooting

- **Traces not appearing:** verify `OPENOBSERVE_URL`, `OPENOBSERVE_ORG`, and `OPENOBSERVE_AUTH_TOKEN`. The token must be `Basic <base64>` with no surrounding quotes.
- **401 Unauthorized:** re-generate the base64 token with `echo -n "email:password" | base64` and update `.env`.
- **Instrumentation not working:** ensure `init_telemetry()` and `Instrumentor().instrument()` run before any framework imports.
- **OTLP endpoint path:** the URL must include `/api/<org>/v1/traces`.
- **LangGraph agent errors with "did not finish within 25 steps":** it hit the graph's recursion limit, which usually means a tool call is repeatedly failing and the model keeps retrying. Check the `langgraph.node.tools` spans in the trace to see what's actually being returned to the model each iteration.
- **Frontend cannot connect:** `BACKEND_URL` is set automatically by `run.sh`. If you start with `docker compose` directly, set it manually in `.env`.

## Learn more

- Blog post: [Trace LangChain and LlamaIndex Apps with OpenObserve](https://openobserve.ai/blog/langchain-llamaindex-openobserve)
- OpenLLMetry: https://github.com/traceloop/openllmetry
- OpenObserve docs: https://openobserve.ai/docs

## License

Apache 2.0
