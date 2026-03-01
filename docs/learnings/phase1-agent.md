# phase1-agent

Use `docs/learnings/TEMPLATE.md` for each entry.

## Entry: 2026-03-01 - Phase 1 Core Agent and Agent-Focused Tests

### Context

Implemented Phase 1 core agent path (prompt + tools + notebook + runner) and replaced tool-level confidence checks with agent-level integration tests.

### Problem

We needed confidence in full-agent behavior (tool routing, self-correction, trace capture, eval mapping), not isolated tool calls.

### Evidence

- Phase 1 integration suite:
  `analytics-agent/phase1_tests/test_agent_e2e.py`
  result: `3/3 checks passed`.
- Spider e2e smoke:
  question on `concert_singer.sqlite` returned `answer_value=6` with notebook/tool history.
- Trace evidence captured with `call_id` + `trace_id`.
- Mapping artifact generated:
  `analytics-agent/phase1_tests/artifacts/agent_eval_trace_mapping.json`

### RCA

Tool-level tests were not sufficient to validate final agent output quality or trace/eval linkage. Agent-level tests make failure modes visible at the level we actually ship and evaluate.

### Fix

1. Added reusable Phase 1 integration test suite focusing on:
   - structured output validity
   - notebook/tool-call evidence
   - trace id presence
   - micro Weave evaluation over real agent predictions
2. Added production runner for single-question execution:
   `analytics-agent/agent/run_single.py`
3. Kept LangGraph runtime compatibility path (`create_agent` preferred, fallback handled).

### Validation

1. `.\.venv\Scripts\python.exe analytics-agent\phase1_tests\test_agent_e2e.py` passed.
2. `.\.venv\Scripts\python.exe analytics-agent\agent\run_single.py ...` on Spider DB passed.
3. Output included JSON answer + SQL + notebook cells + metrics.

### Reusability Notes (Future Skill Candidate)

Potential future skill: "Agent Runtime Verification"

1. Run agent-level integration tests.
2. Validate trace/eval linkage contract.
3. Emit mapping artifacts for RCA workflows.

### References

- `docs/analytics-agent-detailed-todo.md`
- `analytics-agent/agent/agent.py`
- `analytics-agent/phase1_tests/test_agent_e2e.py`

