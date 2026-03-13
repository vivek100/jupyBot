# Self-Evolving Analytics Agent (Research Project)

Last updated: 2026-03-12

This repo documents a research-style loop for improving a **SQLite analytics agent** on the Spider benchmark using:

- a **small Mistral model (7B)**
- tool-augmented execution (`describe_schema`, `execute_sql`, `run_python`)
- end-to-end **observability** (W&B metrics + per-question traces + notebooks)
- a structured **RCA → fix → re-eval** iteration process
- a reusable **skills package** that turns the loop into an execution playbook for any coding agent

## Headline Result: 21% → 84% Accuracy

![Accuracy Progress](accuracy_progress.png)

Notes:
- The jump from **89.7% → 82.0%** happened when we expanded from a small curated slice (39 questions) to a **100-question randomized set**, exposing generalization gaps.

## What We Built

- **An analytics ReAct agent** that can inspect schema, write SQL, and post-process results in Python.
- **A scoring contract** that expects a scalar `answer_value` (the key driver behind many early failures).
- **Run artifacts for every eval**:
  - `predictions.jsonl`
  - `failures.jsonl`
  - `trace_index.jsonl`
  - `notebooks.jsonl` (tool + SQL + python "cells")
- **A fix registry + human approval gate** so we avoid overfitting and keep changes explainable.
- **A skill pack** (`skills/`) that encodes the repeatable W&B + eval + RCA workflows.

## Agent Execution Flow (Tool + Notebook Style)

```mermaid
flowchart TD
    Q[Question] --> S[describe_schema]
    S --> P[Plan: choose answer target column]
    P --> SQL1[execute_sql: explore/inspect]
    SQL1 --> SQL2[execute_sql: final answer query]
    SQL2 --> PY[run_python: extract scalar answer_value]
    PY --> A[Final JSON: answer_value + answer_text + sql + notebook_cells]

    %% Artifacts
    SQL1 -.-> NB[Notebook cells recorded]
    SQL2 -.-> NB
    PY  -.-> NB
```

Key idea: SQL does the heavy lifting (joins/filters/aggregations). `run_python` exists to make the output contract reliable (scalar extraction, formatting, light post-processing).

## Eval + RCA Improvement Loop

```mermaid
flowchart TD
    A[Pick eval slice<br/>offset/limit + seed] --> B[Run eval runner]
    B --> C[Log W and B metrics + Weave traces]
    C --> D[Persist local artifacts<br/>predictions/failures/trace_index/notebooks]
    D --> E[Generate RCA table<br/>from failures]
    E --> F[Propose fixes<br/>prompt/tool/scorer]
    F --> G[Human review gate<br/>accept/defer/reject]
    G -->|Accepted| H[Implement + snapshot]
    G -->|Deferred| I[Backlog or SFT candidate]
    H --> A
```

## Skills: Making the Loop Reusable

The `skills/` folder is an execution playbook so a coding agent can reproduce the exact loop on a new codebase.

- Entry point: `skills/skills.md`
- Topic skills:
  - `skills/wandb-projects/`
  - `skills/wandb-runs/`
  - `skills/wandb-traces/`
  - `skills/wandb-evals/`
  - `skills/wandb-reports/`
  - `skills/coding-agent-self-eval/` (orchestration + human gate)

Skills PR: https://github.com/wandb/wandb-mcp-server/pull/24

## Runs And Outcomes

| Run Label | W&B Run ID | Slice | Agent SHA | Correct / Total | Accuracy | Summary |
|---|---|---|---|---:|---:|---|
| run_1 | xk2hr6zt | offset 0, limit 100 | 1844c71 | 21 / 100 | 0.21 | Baseline |
| run_2 | ank4a2aw | offset 0, limit 100 | 34d75d4 | 69 / 100 | 0.69 | Big gain after contract/tool fixes |
| run_3 | 9xild9wl | offset 100, limit 100 | e6d031a | 37 / 100 | 0.37 | Different slice exposed generalization gaps |
| run_4 | 0uz4zvcz | offset 200, limit 100 | eeef51e | 53 / 100 | 0.53 | After schema tool + SQL no-case recovery; improved over run_3 |

## Fixes And Impact

| Fix ID | Type | Status | Change | Observed Effect |
|---|---|---|---|---|
| fix-0201 | architecture_change | implemented | Normalize non-scalar `answer_value` | Removed `answer_shape_mismatch` in run_2 |
| fix-0202 | tool_design | implemented | SQL error assist (table/column suggestions) | Removed `tool_error_unresolved` in run_2 |
| fix-0204 | architecture_change | accepted + implemented | Ground `answer_value` from executed SQL | Included in run_3 |
| fix-0205 | prompt_update | accepted + implemented | Final-answer execution guard | Included in run_3 |
| fix-0206 | needs_model_training | deferred | Route persistent semantic misses to SFT | Kept as escalation path |

## Key Learnings

1. Contract and tool-recovery fixes can yield fast wins.
2. Cross-slice testing is mandatory; same-slice gains can hide weak generalization.
3. Human-gated RCA is necessary to prevent brittle one-off prompt patches.

## Submission Assets

1. Skills index: `skills/skills.md`
2. Skills folders: `skills/wandb-*` + `skills/coding-agent-self-eval/`
3. W&B MCP skills PR: `https://github.com/wandb/wandb-mcp-server/pull/24`
4. Fix workflow gate: `analytics-agent/FIXES_README.md`
5. RCA summaries:
   - `analytics-agent/outputs/improvement/rca_failures_ank4a2aw_summary.json`
   - `analytics-agent/outputs/improvement/rca_failures_9xild9wl_summary.json`
6. Next backlog (separate from presentation): `docs/submission-next-todo.md`

## Run-Centric Demo Data

Use this path during demo so judges can navigate by run label instead of run ID:

1. `analytics-agent/outputs/runs/README.md`
2. `analytics-agent/outputs/runs/run_1/`
3. `analytics-agent/outputs/runs/run_2/`
4. `analytics-agent/outputs/runs/run_3/`
5. `analytics-agent/outputs/runs/run_4/`

Each run folder contains:
1. `README.md` (what happened in that run)
2. `metadata.json` (run id/url/metrics/fix context)
3. `observability/` (predictions, failures, trace mapping, notebooks if available)
4. `rca/` (RCA rows and summary)
