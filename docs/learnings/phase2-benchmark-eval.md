# phase2-benchmark-eval

Use docs/learnings/TEMPLATE.md for each entry.

## Entry: 2026-03-01 - Benchmark Output Hardening For Improvement Loop

### Context

Phase 2 required deterministic benchmark outputs that can be consumed by RCA tooling and cross-run history analysis.

### Problem

Benchmark runs produced predictions and trace mappings, but we lacked:
1. dedicated failure rows,
2. prompt-budget metadata on runs for governance tracking.

### Evidence

1. Existing runs already emitted `predictions.jsonl` and `trace_index.jsonl`.
2. Improvement loop requirements needed `failures.jsonl` and prompt budget visibility per run.

### RCA

Data required for RCA was partially present, but not normalized for fast filtering and iteration-level comparisons.

### Fix

1. Updated `analytics-agent/eval/observability.py` to emit `failures.jsonl` on every run.
2. Updated `analytics-agent/eval/runner.py` to log:
   - `prompt_chars`
   - `prompt_tokens_est`
   - `max_prompt_chars`
   - `max_prompt_tokens_est`
   - `prompt_budget_ok`
3. Kept outputs lean and backward-compatible with existing artifacts.

### Validation

1. Spider eval run completed with updated outputs and artifacts.
2. `failures.jsonl` now exists under per-run observability directories.
3. Prompt budget metrics are visible in W&B run summary/config.

### Reusability Notes (Future Skill Candidate)

Candidate skill: "Benchmark Output Contract"

1. Ensure benchmark runs always produce predictions, failures, and trace mappings.
2. Ensure prompt-governance fields are logged on every run.
3. Keep schema stable for downstream RCA tooling.

### References

- `analytics-agent/eval/observability.py`
- `analytics-agent/eval/runner.py`
- `docs/analytics-agent-detailed-todo.md`

