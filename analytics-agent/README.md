# Analytics Agent (Phase 0)

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
