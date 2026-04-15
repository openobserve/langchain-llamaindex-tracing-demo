# OpenObserve LangChain / LlamaIndex Tracing Demo

A runnable demo showing how to trace LangChain and LlamaIndex RAG apps with OpenLLMetry instrumentation, OpenTelemetry OTLP export, and OpenObserve.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com)

## What this demo shows

- A LangChain backend and a LlamaIndex backend exposing the same `/chat`, `/feedback`, and `/health` API.
- OpenLLMetry auto-instrumentation for LangChain, LlamaIndex, and Anthropic, with traces exported over OTLP to OpenObserve.
- A simple browser frontend that sends questions, shows answers, records thumbs-up/thumbs-down feedback, and returns trace IDs.
- A Docker Compose stack that starts your chosen backend and the frontend locally.

## Architecture

```
Frontend -> Backend API -> OpenLLMetry instrumentation -> OpenTelemetry SDK -> OpenObserve
```

- Frontend: static HTML/JS chat UI
- Backend: LangChain or LlamaIndex service (your choice at startup)
- LLM: Anthropic Claude (`claude-haiku-4-5-20251001`)
- Embeddings: `fastembed` with `BAAI/bge-small-en-v1.5` (local ONNX, no GPU needed)
- Instrumentation: `AnthropicInstrumentor` on both backends; `LlamaIndexInstrumentor` additionally on the LlamaIndex backend
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
   You will be prompted to choose between LangChain and LlamaIndex. Only the chosen backend starts.

5. Open http://localhost:3000 and ask a question.

## Switching between backends

Run `./run.sh` again and pick the other option. The script sets `BACKEND_URL` automatically so the frontend always points to the running backend.

- LangChain backend runs on port `8001`
- LlamaIndex backend runs on port `8002`

## What you will see in OpenObserve

- A trace for each `/chat` request.
- Nested spans for the retrieval, prompt generation, and Anthropic API call.
- `gen_ai.*` attributes on LLM spans such as prompt tokens and completion tokens.
- A separate feedback span linking back to the original trace via `linked_trace_id`.

## How it works

This demo is built as a four-layer observability pipeline:

1. Application code: LangChain or LlamaIndex RAG chain.
2. OpenLLMetry instrumentation: `AnthropicInstrumentor` (+ `LlamaIndexInstrumentor` for the LlamaIndex backend).
3. OpenTelemetry SDK: `TracerProvider`, `BatchSpanProcessor`, `OTLPSpanExporter`.
4. OpenObserve: receives OTLP traces and stores them.

For details, see `docs/architecture.md`.

## Troubleshooting

- **Traces not appearing:** verify `OPENOBSERVE_URL`, `OPENOBSERVE_ORG`, and `OPENOBSERVE_AUTH_TOKEN`. The token must be `Basic <base64>` with no surrounding quotes.
- **401 Unauthorized:** re-generate the base64 token with `echo -n "email:password" | base64` and update `.env`.
- **Instrumentation not working:** ensure `init_telemetry()` and `Instrumentor().instrument()` run before any framework imports.
- **OTLP endpoint path:** the URL must include `/api/<org>/v1/traces`.
- **Frontend cannot connect:** `BACKEND_URL` is set automatically by `run.sh`. If you start with `docker compose` directly, set it manually in `.env`.

## Learn more

- Blog post: [Trace LangChain and LlamaIndex Apps with OpenObserve](https://openobserve.ai/blog/langchain-llamaindex-openobserve)
- OpenLLMetry: https://github.com/traceloop/openllmetry
- OpenObserve docs: https://openobserve.ai/docs

## License

Apache 2.0
