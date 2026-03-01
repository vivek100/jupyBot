# phase1-observability

Use `docs/learnings/TEMPLATE.md` for each entry.

## Entry: 2026-03-01 - Lean Observability Baseline

### Context

Started Phase 1 observability, but constrained implementation to a lean payload after confirming current Weave traces already contain rich run/node/tool spans.

### Problem

Initial observability draft was too heavy (extra dumps by default). Needed a minimal, stable mapping layer for benchmark/eval RCA.

### Evidence

1. Direct Weave client inspection showed existing traces already include:
   - root run call (`run_analytics_agent`)
   - child graph/model/tool spans
   - `call_id`, `trace_id`, timestamps, op names, exception state
2. New minimal observability test:
   - `analytics-agent/phase1_tests/test_observability_minimal.py`
   - result: `1/1` passed
   - W&B run: `phase1-observability-minimal-test`
   - trace index artifact created and uploaded
3. Regression check:
   - `analytics-agent/phase1_tests/test_agent_e2e.py`
   - result: `3/3` passed

### RCA

Tracing coverage was already sufficient at execution level. Missing piece was reliable mapping and version linkage for evaluation/RCA workflows.

### Fix

Implemented lean-by-default observability module (`analytics-agent/eval/observability.py`):

1. Default mode: `lean`
2. Persist:
   - `predictions.jsonl`
   - `trace_index.jsonl`
3. Include required mapping fields:
   `question_id`, `expected_value`, `answer_value`, `correct`,
   `wandb_run_id`, `trace_id`, `call_id`, `prompt_version`, `agent_version`
4. Keep heavy dumps optional via `mode=full`.

### Validation

1. Minimal observability test passed and produced expected files/artifact.
2. Agent-level integration tests still pass after observability changes.
3. Weave traces and W&B run logging remain visible and linked.

### Reusability Notes (Future Skill Candidate)

Future reusable skill: "Lean Trace-Index Observability"

1. Start run session
2. Capture trace IDs from run call handle
3. Persist trace index + predictions
4. Log core per-question metrics
5. Upload artifact for RCA joins

### References

- `docs/analytics-agent-detailed-todo.md`
- `analytics-agent/eval/observability.py`
- `analytics-agent/phase1_tests/test_observability_minimal.py`

## Entry: 2026-03-01 - Metadata Contract + Dashboard Tables

### Context

Phase 1 needed stronger consistency in run metadata and a dashboard-ready output shape before scaling benchmark loops.

### Problem

Trace linkage worked, but row schemas were not explicit enough for stable cross-run dashboards and RCA joins.

### Evidence

1. Existing outputs had required IDs but mixed payload shape (`metrics` nested + partial flat fields).
2. Dashboard panels are easier to keep stable when summary keys and row columns are consistent.
3. Notebook artifact logging was available only in full mode, not controllable for lean runs.

### RCA

Missing contract enforcement around:
1. run metadata fields,
2. trace status/timing fields,
3. dashboard-oriented table outputs.

### Fix

Updated `analytics-agent/eval/observability.py` and `analytics-agent/eval/runner.py`:

1. Standardized mapping/prediction fields:
   - run linkage: `wandb_run_id`, `wandb_run_name`, `wandb_run_url`, `phase`, `group`
   - trace linkage: `trace_id`, `call_id`, `parent_id`, `op_name`, `trace_started_at`, `trace_ended_at`, `trace_latency_ms`, `trace_exception`
   - version linkage: `prompt_version`, `agent_version`, `model_name`
2. Added compact dashboard logs:
   - `dashboard/predictions_table`
   - `dashboard/failures_table`
3. Added canonical summary metrics:
   - `summary/questions_total`, `summary/questions_correct`, `summary/running_accuracy`, `summary/mean_latency_ms`
4. Added runner flag:
   - `--capture-notebooks` to persist notebook JSONL even in lean mode.

### Validation

1. `phase1_tests/test_observability_minimal.py` validates expanded mapping contract.
2. Eval runs continue to emit run URL, metrics, and artifacts.
3. Lean mode remains default; heavy payloads stay optional.

### Reusability Notes (Future Skill Candidate)

Future skill candidate: "Eval Observability Contract"

1. Emit deterministic run/trace/version fields for every eval row.
2. Emit stable summary keys for dashboard portability.
3. Keep payload lean with optional notebook/trace expansion flags.

### References

- `analytics-agent/eval/observability.py`
- `analytics-agent/eval/runner.py`
- `analytics-agent/phase1_tests/test_observability_minimal.py`
