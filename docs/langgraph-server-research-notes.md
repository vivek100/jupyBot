# LangGraph Server Research Notes

Last reviewed: 2026-03-01

## Why this file exists

This is the implementation reference for the LangGraph runtime and deployment choices in `docs/analytics-agent-detailed-todo.md`.

## Current doc findings (2026-03-01)

1. `langgraph.json` is the required config entrypoint for LangGraph CLI/Agent Server.
2. Agent Server exposes runs/threads/assistants and persistence capabilities.
3. LangGraph v1 guidance deprecates `create_react_agent` in favor of LangChain `create_agent` (which runs on LangGraph).
4. `create_agent` returns a compiled LangGraph graph that can be referenced directly in `langgraph.json`.
5. LangGraph tracing/observability is centered on full run traces (node/run level), not tool-only traces.

## Decision gate for implementation

- Primary path (recommended): `langchain.agents.create_agent` on LangGraph runtime.
- Compatibility path (only if explicitly required): pin to legacy prebuilt ReAct API (`create_react_agent`) and document version lock/risk.
- For this project, keep the external behavior "ReAct-style agent", but runtime should follow current stable docs unless an explicit pin is requested.

## Required `langgraph.json` coverage

Include at minimum:

1. `$schema`
2. `dependencies`
3. `graphs`
4. `env`

Planned optional fields for this project:

1. `api_version`
2. `checkpointer` (for thread persistence + reproducibility)
3. `store` (if notebook/event state outgrows in-memory)
4. `http.configurable_headers` (run metadata propagation)

## Full-run tracing requirement

Tracing must capture end-to-end agent execution for each benchmark question:

1. root run metadata
2. graph/node transitions
3. tool spans as child operations
4. final output and structured score payload

Tool traces are necessary but not sufficient. Evaluation must be run-centric.

## Run metadata contract (to map trace -> benchmark row)

Each run should carry:

1. `benchmark_name` (e.g., spider_dev)
2. `question_id` (stable row id)
3. `db_id`
4. `expected_output_ref` (or compact expected value hash)
5. `wandb_run_id`
6. `prompt_version`
7. `agent_version`

## Notebook architecture exploration checklist

Evaluate these options before implementation lock:

1. Graph state notebook list (simple, easy, may grow large).
2. Event-sourced notebook (append-only per step, artifactized after run).
3. External store-backed notebook (best for concurrency/high volume, more moving parts).

Recommendation target:

1. Start with event-sourced notebook plus artifact persistence.
2. Keep graph state minimal (IDs and summaries, not full dataframes).
3. Add store/checkpointer only when concurrency/size issues appear.

## Multi-request and concurrency notes

1. Use LangGraph threads/checkpointing model for multi-turn continuity.
2. Keep per-request IDs deterministic and included in both W&B logs and trace metadata.
3. Ensure evaluation runners are idempotent and resumable.

## Sources

- LangGraph v1 migration guide: https://docs.langchain.com/oss/python/migrate/langgraph-v1
- LangGraph v1 release notes: https://docs.langchain.com/oss/python/releases/langgraph-v1
- LangGraph CLI and `langgraph.json` config: https://docs.langchain.com/langgraph-platform/cli
- LangGraph Studio setup (`create_agent` + `langgraph.json`): https://docs.langchain.com/oss/python/langgraph/studio
- LangGraph observability overview: https://docs.langchain.com/oss/python/langgraph/observability

