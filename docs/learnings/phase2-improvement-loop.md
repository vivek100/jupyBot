# phase2-improvement-loop

Use docs/learnings/TEMPLATE.md for each entry.

## Entry: 2026-03-01 - RCA Tooling Foundation (History + Fix Registry + Prompt Governance)

### Context

To run an evidence-driven improvement loop, we needed lightweight tooling where the coding agent makes RCA decisions and scripts persist the decision trail.

### Problem

RCA decisions and fix outcomes were not recorded in a structured, queryable format across runs/questions/versions.

### Evidence

1. We had run-level observability artifacts, but no fix-registry/event model.
2. We needed per-question cross-run transitions to evaluate whether a fix actually helped.
3. We needed explicit prompt-governance checks to avoid prompt bloat.

### RCA

Missing operational primitives:
1. question longitudinal history builder,
2. fix proposal/decision registry,
3. prompt policy checker.

### Fix

Implemented three utilities:

1. `analytics-agent/eval/question_history.py`
   - Builds `question_history.jsonl`, `question_latest.jsonl`, `question_history_summary.json`.
   - Joins optional `fix_judgement.jsonl`.
2. `analytics-agent/eval/fix_registry.py`
   - `propose`, `decide`, `link-evidence`, `judge-question`, `show`, `export-current`.
   - Enforces RCA taxonomy choices at proposal time.
3. `analytics-agent/eval/prompt_governance.py`
   - Enforces prompt budget and pattern-threshold rules for `prompt_update`.
   - Returns machine-readable JSON output and non-zero status on violations.

### Validation

1. Prompt-governance checker blocks prompt update when threshold is not met.
2. Fix registry can record proposal/decision/evidence and question-level judgements.
3. Question history builds successfully from existing observability runs.

### Reusability Notes (Future Skill Candidate)

Candidate skill: "RCA Iteration Control Plane"

1. Agent proposes and decides fixes from evidence.
2. Scripts persist and validate the loop state.
3. History artifacts provide direct comparability across versions/runs/questions.

### References

- `analytics-agent/eval/question_history.py`
- `analytics-agent/eval/fix_registry.py`
- `analytics-agent/eval/prompt_governance.py`
- `docs/analytics-agent-detailed-todo.md`

## Entry: 2026-03-01 - Baseline Eval (100) RCA And Fix Proposals

### Context

Ran a first real baseline eval on Spider to start the improvement loop and generate evidence for RCA.

### Evidence

1. Baseline run executed 100 questions:
   - run id: `xk2hr6zt`
   - run name: `phase2-spider_dev-baseline-i00-o0-l100-20260301-141132`
   - run url: `https://wandb.ai/shukla-vivek1993-startup/jupybot/runs/xk2hr6zt`
2. Local RCA report generated:
   - `analytics-agent/outputs/improvement/rca_xk2hr6zt.json`
3. Summary from run artifacts:
   - total: `100`
   - correct: `21`
   - accuracy: `0.21`
   - failures: `79`
4. Failure category counts:
   - `answer_shape_mismatch`: `55`
   - `null_answer`: `12`
   - `tool_error_unresolved`: `7`
   - `answer_type_string_mismatch`: `3`
   - `fallback_no_answer`: `2`
5. Representative failed trace ids used for RCA:
   - `019cab75-1f1e-7ffe-b892-4592539129e7` (shape mismatch)
   - `019cab75-4ce0-7f22-8b39-04b1de461975` (shape mismatch)
   - `019cab75-601f-7f0e-b015-c1dfae134ecb` (unresolved table error)
   - `019cab75-14d4-7a88-a273-7eff0d22e4bc` (fallback/no-answer)

### RCA

Primary issues were not model capability limits; they were mostly contract and recovery behavior issues:

1. **Answer contract mismatch** (majority):
   - Agent frequently returns list/dict in `answer_value`.
   - Current scorer compares first scalar from gold SQL result.
   - This creates many false negatives even when SQL appears directionally correct.
2. **Schema recovery gaps after SQL errors**:
   - Repeated `no such table` failures (`singers`, `concerts`, `stadiums`) are not always recovered before final answer.
3. **Premature fallback finalization**:
   - Some flows produce apology/no-answer text with `answer_value=None` instead of retrying to a valid query.

Relevant code touchpoints reviewed during RCA:
- Agent output parsing and final payload: `analytics-agent/agent/agent.py`
- SQL tool error payload behavior: `analytics-agent/agent/tools/sql_tool.py`
- Scoring contract (first-value comparison): `analytics-agent/eval/scorer.py`

### Fix Proposals Logged

Proposed and recorded in `fix_registry.jsonl`:

1. `fix-0201` (`architecture_change`)
   - Add answer normalizer to coerce list/dict outputs into scorer-compatible scalar value.
2. `fix-0202` (`tool_design`)
   - Enrich SQL tool errors with schema suggestions from `sqlite_master` to improve retry quality.
3. `fix-0203` (`prompt_update`)
   - Tighten prompt recovery rule: on SQL error, inspect tables and retry corrected SQL before finalizing.

Prompt governance check for `fix-0203`:
- passed with clustered pattern count (`14 >= threshold 5`)
- output: `analytics-agent/outputs/improvement/prompt_governance_fix-0203.json`

### Validation Notes

1. The initial 100-run completed question execution but failed at finish-time dashboard table typing due mixed `answer_value` types.
2. `eval/observability.py` table builder was hardened to support mixed column types.
3. Post-fix rerun (10 questions) completed end-to-end:
   - run id: `hoes9ova`
   - run url: `https://wandb.ai/shukla-vivek1993-startup/jupybot/runs/hoes9ova`

### Operational Gap

Attempted direct MCP Weave trace retrieval for targeted call ids, but current MCP transport returned decode errors. RCA was completed using run artifacts (`trace_index.jsonl`, `predictions.jsonl`, `notebooks.jsonl`) and run-linked trace ids.

### References

- `analytics-agent/eval/runner.py`
- `analytics-agent/eval/observability.py`
- `analytics-agent/eval/scorer.py`
- `analytics-agent/agent/agent.py`
- `analytics-agent/agent/tools/sql_tool.py`
- `analytics-agent/outputs/improvement/rca_xk2hr6zt.json`

## Entry: 2026-03-01 - Run Labeling + Per-Question RCA Tracking

### Context

Need consistent run-to-run tracking and failed-question RCA visibility per run.

### Fix

1. Added `analytics-agent/eval/rca_from_run.py`:
   - emits `rca_failures_<run_id>.jsonl` and summary JSON for failed questions.
2. Added `analytics-agent/eval/label_runs.py`:
   - applies labels/tags (e.g., `run_1`, `run_2`) directly to W&B runs.
3. Applied labels:
   - `xk2hr6zt -> run_1`
   - `byrxw3fa -> run_2`
4. Uploaded per-question RCA artifact to baseline run:
   - `phase2-rca-failures-xk2hr6zt`

### Validation

1. RCA file generated for run `xk2hr6zt` with `79` failed-question rows.
2. W&B run labels/tags updated successfully for run_1 and run_2.
3. RCA artifact attached to run_1.

### References

- `analytics-agent/eval/rca_from_run.py`
- `analytics-agent/eval/label_runs.py`

