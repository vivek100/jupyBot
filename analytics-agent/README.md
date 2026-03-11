# Analytics Agent (Phase 0)

## 🎯 Accuracy Progress

![Accuracy Progress](accuracy_progress.png)

We've improved the analytics agent from **21%** to **84%** accuracy using a **Small Mistral model (7B parameters)** through systematic prompt engineering:

- **v0 (Baseline)**: 21% - Initial implementation with ambiguous output format
- **v3 (Scalar fix)**: 74.4% - Fixed `answer_value` to always be scalar and added `run_python` guidance
- **v5 (Few-shot)**: 89.7% - Added few-shot examples (39 questions)
- **v6 (100q random)**: 82.0% - Expanded to 100 randomized questions
- **v7 (Refined)**: 83.0% - Improved examples and column selection guidance
- **v8 (Real-data)**: 84.0% - Added detailed commentary and real-data examples

**Key improvements**:
- Enforced scalar `answer_value` output
- Added `run_python` tool for post-processing SQL results
- Implemented few-shot examples with column selection guidance
- Added deterministic `ORDER BY` for grouped aggregations
- Enhanced examples with step-by-step reasoning

## Setup

1. Create virtual env and install deps:
   - `pip install -r analytics-agent/requirements.txt`
2. Configure env:
   - Copy `analytics-agent/.env.example` to `analytics-agent/.env` or set vars in repo root `.env`.
3. Download Spider into `analytics-agent/data/spider` (or set `SPIDER_ROOT`).

## Phase 0 Test

Run:

```bash
python analytics-agent/phase0_tests/test_all.py
```

This script validates:

- Mistral API
- W&B logging
- Weave tracing
- Spider SQL execution
- Mistral tool calling
- Python subprocess tool behavior
- LangGraph ReAct smoke run
- Small Weave/W&B evaluation with run metadata mapping

## Phase 1 Single Question Run

```bash
python analytics-agent/agent/run_single.py --question "How many singers are there?"
```

## Git Snapshot / Restore (Agent Versions)

Create snapshot tag:

```bash
python analytics-agent/scripts/agent_version.py snapshot --name phase1-baseline
```

List snapshots:

```bash
python analytics-agent/scripts/agent_version.py list
```

Restore agent files from snapshot:

```bash
python analytics-agent/scripts/agent_version.py restore --ref agent/phase1-baseline-YYYYMMDD-HHMMSS
```

## Spider Eval Runner (Small Batch)

```bash
python analytics-agent/eval/runner.py --limit 3 --offset 0
```

Useful observability flags:

```bash
# keep lean traces but also persist notebook JSONL artifact
python analytics-agent/eval/runner.py --limit 3 --capture-notebooks

# full payload mode (trace_metadata + notebooks dumps)
python analytics-agent/eval/runner.py --limit 3 --mode full
```

Default run naming convention (when `--run-name` is omitted):

`phase2-spider_dev-<variant>-i<iteration>-o<offset>-l<limit>-<YYYYMMDD-HHMMSS>`

Example:

```bash
python analytics-agent/eval/runner.py --limit 50 --offset 0 --run-variant baseline --iteration 0
python analytics-agent/eval/runner.py --limit 50 --offset 0 --run-variant prompt_iter --iteration 1
```

Each run now logs:

- stable mapping files: `predictions.jsonl`, `trace_index.jsonl`
- failure rows: `failures.jsonl`
- compact dashboard tables: `dashboard/predictions_table`, `dashboard/failures_table`
- canonical summary keys: `summary/*` (for stable W&B workspace panels)

## Improvement Tracking Utilities

Fix workflow and approval gate reference:

```bash
analytics-agent/FIXES_README.md
```

Human approval gate (required):

1. Generate RCA and propose fixes.
2. Run overfitting checks (and prompt governance for prompt changes).
3. Record `fix_registry.py decide --decision accepted` with `user_approved=true`.
4. Only then create new version snapshot and run next eval.

Build cross-run question history:

```bash
python analytics-agent/eval/question_history.py
```

Manage fix registry and question-level fix judgements:

```bash
python analytics-agent/eval/fix_registry.py propose --fix-id fix-0001 --rca-tag tool_design --change-type sql_tool_error_handling --description "..."
python analytics-agent/eval/fix_registry.py decide --fix-id fix-0001 --decision accepted --rationale "..."
python analytics-agent/eval/fix_registry.py judge-question --question-id spider_1 --run-id <wandb_run_id> --fix-id fix-0001 --decision accepted --judgement improved
python analytics-agent/eval/fix_registry.py show
```

Run prompt-governance checks before accepting prompt updates:

```bash
python analytics-agent/eval/prompt_governance.py --rca-tag prompt_update --pattern-failure-count 7 --pattern-threshold 5
```

Generate per-question RCA rows for a run's failed questions:

```bash
python analytics-agent/eval/rca_from_run.py --run-id xk2hr6zt
```

Label runs for easy loop tracking (`run_1`, `run_2`, ...):

```bash
python analytics-agent/eval/label_runs.py --set xk2hr6zt=run_1 --set byrxw3fa=run_2
```

Republish canonical eval metrics + RCA table into a run dashboard:

```bash
python analytics-agent/eval/publish_run_dashboard.py --run-id xk2hr6zt --run-name "run 1" --run-label run_1
```
