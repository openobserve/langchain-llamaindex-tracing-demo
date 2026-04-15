# Trace Examples

This page describes the example traces you should see when the demo is running.

## Normal query

A normal query is one where the retriever is fast, the prompt is generated quickly, and the OpenAI model returns a clean answer.

Expected trace shape:

- `chat.request`
  - `RunnableParallel` / `QueryEngine.query`
    - `Retriever` / `Retriever.retrieve`
    - `ChatPromptTemplate` / prompt formatting span
    - `ChatOpenAI` / `LLM.chat`

The waterfall should show the retriever and LLM spans as the main contributors to total latency. The assistant response should be returned with a trace ID visible in the UI.

### Screenshot placeholder

- `docs/screenshots/normal-trace.png`

## Slow query

A slow query is one where one stage is clearly slower than the others. In the demo this may be the retriever or the OpenAI API call.

Expected trace shape:

- `chat.request`
  - slow child span in the waterfall
  - other spans remain short

This trace demonstrates how OpenObserve makes it easy to identify the bottleneck instead of guessing from application logs.

### Screenshot placeholder

- `docs/screenshots/slow-query.png`

## Feedback trace

A thumbs-down rating should create a feedback span that references the original trace.

Expected behavior:

- the frontend sends `POST /feedback` with `trace_id`, `rating`, and `comment`
- the backend emits a `feedback` span with a `linked_trace_id` attribute
- the feedback span can be searched in OpenObserve by the trace ID or rating attribute

### Screenshot placeholder

- `docs/screenshots/feedback-trace.png`
