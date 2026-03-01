# Fixes README

Last updated: 2026-03-01

## Purpose

This file tracks fix status and enforces a human approval gate before:
1. creating a new agent version, and
2. running the next benchmark eval.

Goal: prevent overfitting to a small failure slice while still improving measured benchmark performance.

## Current Fix Ledger

1. `fix-0201`  
Status: implemented  
Type: `architecture_change`  
Scope: normalize non-scalar `answer_value` to scorer-compatible scalar in [`analytics-agent/agent/agent.py`](/C:/Users/shukl/Desktop/projects/jupyBot/analytics-agent/agent/agent.py)

2. `fix-0202`  
Status: implemented  
Type: `tool_design`  
Scope: enrich SQL errors with schema recovery hints in [`analytics-agent/agent/tools/sql_tool.py`](/C:/Users/shukl/Desktop/projects/jupyBot/analytics-agent/agent/tools/sql_tool.py)

3. `fix-0203`  
Status: proposed (governance-allowed), not mandatory to apply immediately  
Type: `prompt_update`  
Scope: stricter retry-before-finalize behavior after SQL errors

## Mandatory Pre-Release Workflow (Human Gate)

This is required for every new fix batch.

1. Run/collect benchmark evidence on current version.
2. Generate RCA rows for failed questions.
3. Propose fix candidates with evidence links.
4. Run overfitting checks:
   - Failure-pattern count and spread across multiple questions/dbs.
   - Prompt governance check (if `prompt_update`).
   - Risk note: does change optimize only a tiny set of exact questions?
5. User approval gate:
   - User reviews proposed fixes and overfitting risk.
   - Only user-approved fixes can move forward.
   - Record approval in fix registry decision metadata.
6. Only after approval:
   - Create version snapshot/commit.
   - Implement approved fixes.
   - Run targeted validation slice.
   - Run full eval.
7. Label/publish run (`run_1`, `run_2`, `run_3`, ...), then attach RCA artifacts.

## Commands (Approval-Centric)

### 1) Generate RCA from a run

```bash
python analytics-agent/eval/rca_from_run.py --run-id <run_id>
```

### 2) Propose fix

```bash
python analytics-agent/eval/fix_registry.py propose \
  --fix-id fix-XXXX \
  --rca-tag tool_design \
  --change-type <short_change_type> \
  --description "<what changes and why>" \
  --run-id <run_id> \
  --question-ids "spider_1,spider_4" \
  --trace-ids "<trace_id_1>,<trace_id_2>"
```

### 3) Prompt governance check (for prompt fixes)

```bash
python analytics-agent/eval/prompt_governance.py \
  --rca-tag prompt_update \
  --pattern-failure-count <count> \
  --pattern-threshold 5
```

### 4) Record user approval decision (required before version/eval)

```bash
python analytics-agent/eval/fix_registry.py decide \
  --fix-id fix-XXXX \
  --decision accepted \
  --rationale "User-approved after overfitting review" \
  --metadata "{\"user_approved\": true, \"overfit_risk\": \"low\", \"approver\": \"user\"}"
```

If a fix is risky/overfit:

```bash
python analytics-agent/eval/fix_registry.py decide \
  --fix-id fix-XXXX \
  --decision deferred \
  --rationale "Potential overfitting; needs broader validation"
```

### 5) After approval: snapshot, evaluate, label, publish

```bash
python analytics-agent/scripts/agent_version.py snapshot --name phase2-approved-fix-batch
python analytics-agent/eval/runner.py --limit 100 --offset 0 --run-name run_3
python analytics-agent/eval/label_runs.py --set <run_id>=run_3
python analytics-agent/eval/publish_run_dashboard.py --run-id <run_id> --run-name "run 3" --run-label run_3
```

## Hard Rule

Do not create a new version or run a new full eval unless the fix has a recorded user-approved `accepted` decision in fix registry.
