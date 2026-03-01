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

