# Analytics Agent — Project Plan
### Self-Improving SQL + Python Notebook Agent on Mistral + W&B

---

## Stack

| Component | Choice | Why |
|---|---|---|
| Model | `mistral-small-latest` | Fast iteration, cheap, swap to medium for SFT |
| Inference | Mistral API | Native tool calling, SFT API in same platform |
| Agent Framework | LangGraph ReAct | Clean tool-calling loop, easy to trace |
| Benchmark | Spider (dev set) | Clean SQLite DBs, gold SQL, 1034 questions |
| Experiment Tracking | W&B Models | Metrics, artifacts, before/after comparison |
| Tracing | W&B Weave | Full trace tree per question, failure diagnosis |
| Fine-tuning | Mistral SFT API | Same platform, no infra needed |
| Environment | Local venv | Persistent files, no Colab pain |

---

## Folder Structure

```
analytics-agent/
├── requirements.txt
├── .env
├── data/
│   └── spider/              # download Spider dev set here
├── phase0_tests/
│   ├── test_mistral.py
│   ├── test_wandb.py
│   ├── test_weave.py
│   ├── test_spider.py
│   ├── test_tool_calling.py
│   └── test_python_exec.py
├── agent/
│   ├── tools.py             # execute_sql + run_python
│   ├── prompt.py            # system prompt with workflow
│   ├── agent.py             # LangGraph ReAct agent
│   └── notebook.py          # notebook cell accumulator
├── eval/
│   ├── runner.py            # runs N questions, logs to W&B
│   ├── scorer.py            # compares agent answer to gold
│   └── improve.py           # failure analysis + prompt improvement
└── sft/
    ├── build_dataset.py
    └── finetune.py
```

---

## Environment Setup

### Required API Keys

Create a `.env` file in the project root:

```bash
# Mistral — get from https://console.mistral.ai/
MISTRAL_API_KEY=your_mistral_api_key_here

# W&B — get from https://wandb.ai/settings
WANDB_API_KEY=your_wandb_api_key_here

# W&B project config (no key needed, just set these)
WANDB_PROJECT=analytics-agent-hackathon
WANDB_ENTITY=your_wandb_username_or_team
```

### Installing Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install mistralai wandb weave langgraph langchain-core \
            pandas numpy matplotlib scipy python-dotenv
```

### Downloading Spider

```bash
# Option A — Hugging Face CLI
pip install huggingface_hub
huggingface-cli download xlangai/spider --repo-type dataset --local-dir data/spider

# Option B — Direct from Yale
# https://yale-lily.github.io/spider → download link on page
# Unzip into data/spider/
```

Expected structure after download:
```
data/spider/
├── dev.json              # 1034 eval questions with gold SQL
├── train_spider.json     # training questions
├── tables.json           # schema metadata
└── database/
    ├── concert_singer/
    │   └── concert_singer.sqlite
    ├── pets_1/
    │   └── pets_1.sqlite
    └── ... (200 databases)
```

---

## Phase 0 — Verify All Tools
**Time estimate: 1-2hrs**  
**Goal: Every integration works in isolation before touching agent code**

All checks are in a **single file** `phase0_tests/test_all.py`. Run it top to bottom — each section is clearly labeled and will print PASS or FAIL. Do not proceed to Phase 1 until all pass.

```python
# phase0_tests/test_all.py
import os, json, subprocess, sqlite3
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]
WANDB_API_KEY   = os.environ["WANDB_API_KEY"]
WANDB_PROJECT   = os.environ.get("WANDB_PROJECT", "analytics-agent-hackathon")
SPIDER_DB_PATH  = "data/spider/database/concert_singer/concert_singer.sqlite"
SPIDER_DEV_PATH = "data/spider/dev.json"

print("=" * 60)
print("PHASE 0 — ALL TOOLS VERIFICATION")
print("=" * 60)


# ── TEST 1: Mistral basic chat ────────────────────────────────
print("\n[1/6] Mistral API — basic chat call")
try:
    from mistralai import Mistral
    client = Mistral(api_key=MISTRAL_API_KEY)
    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": "Reply with: hello"}]
    )
    print("  Response:", response.choices[0].message.content)
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")


# ── TEST 2: W&B metric logging ────────────────────────────────
print("\n[2/6] W&B — log a metric")
try:
    import wandb
    run = wandb.init(project=WANDB_PROJECT, name="phase0-test", reinit=True)
    wandb.log({"test_metric": 42.0})
    run.finish()
    print("  ✅ PASS — check your W&B dashboard for 'phase0-test' run")
except Exception as e:
    print(f"  ❌ FAIL: {e}")


# ── TEST 3: Weave tracing ─────────────────────────────────────
print("\n[3/6] Weave — trace a Mistral call")
try:
    import weave
    weave.init(WANDB_PROJECT)

    @weave.op()
    def test_weave_call():
        return client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": "Reply with: traced"}]
        ).choices[0].message.content

    result = test_weave_call()
    print("  Response:", result)
    print("  ✅ PASS — check Weave UI for trace")
except Exception as e:
    print(f"  ❌ FAIL: {e}")


# ── TEST 4: Spider DB + gold SQL ──────────────────────────────
print("\n[4/6] Spider — load DB and run gold SQL")
try:
    conn = sqlite3.connect(SPIDER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("  Tables:", tables)

    with open(SPIDER_DEV_PATH) as f:
        dev = json.load(f)
    example = dev[0]
    print("  Question:", example["question"])
    print("  Gold SQL:", example["query"])

    db_path = f"data/spider/database/{example['db_id']}/{example['db_id']}.sqlite"
    conn2 = sqlite3.connect(db_path)
    result = conn2.execute(example["query"]).fetchall()
    print("  Gold result:", result[:3])
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")


# ── TEST 5: Mistral tool/function calling ─────────────────────
print("\n[5/6] Mistral — function/tool calling")
try:
    tools = [{
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Run a SQL query and return results",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL query to execute"}
                },
                "required": ["sql"]
            }
        }
    }]

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": "How many rows are in the employees table?"}],
        tools=tools,
        tool_choice="any"
    )
    tool_call = response.choices[0].message.tool_calls[0]
    print("  Tool called:", tool_call.function.name)
    print("  Arguments:", tool_call.function.arguments)
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")


# ── TEST 6: Safe Python subprocess execution ──────────────────
print("\n[6/6] Python sandbox — subprocess exec with pandas")
try:
    code = """
import pandas as pd
import numpy as np
df = pd.DataFrame({'salary': [70000, 80000, 90000, 100000]})
print(df['salary'].mean())
"""
    result = subprocess.run(
        ["python", "-c", code],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print("  Output:", result.stdout.strip())
        print("  ✅ PASS")
    else:
        print(f"  ❌ FAIL: {result.stderr}")
except Exception as e:
    print(f"  ❌ FAIL: {e}")


print("\n" + "=" * 60)
print("PHASE 0 COMPLETE — fix any ❌ before proceeding")
print("=" * 60)
```

### ✅ Phase 0 Done When
- [ ] All 6 tests print ✅ PASS
- [ ] W&B dashboard shows `phase0-test` run with `test_metric: 42`
- [ ] Weave UI shows a trace for `test_weave_call`
- [ ] Spider gold SQL returns correct rows

---

## Phase 1 — ReAct Analytics Agent
**Time estimate: 4hrs**  
**Goal: Working agent + baseline accuracy number logged in W&B**

### Agent Design

One LangGraph ReAct agent. The workflow is defined in the system prompt — not in separate graph nodes. The agent reasons through EXPLORE → PLAN → EXECUTE → ANSWER on its own.

**System prompt workflow:**
```
You are an analytics agent. For every question follow these steps:

1. EXPLORE  — Understand the question. List what data you need.
              Use execute_sql to inspect table schemas and sample rows.
              
2. PLAN     — Break the question into steps.
              Decide which steps need SQL (large data, joins, aggregation)
              and which need Python (complex calc, formatting, plotting).
              
3. EXECUTE  — Run cells one by one. Inspect each output before writing the next.
              Build a notebook as you go. Pass data between cells via context.
              For datasets > 10k rows: aggregate in SQL first, then load into Python.
              
4. ANSWER   — Synthesize a final answer. Return structured JSON with answer_value.
```

### Two Tools

**`execute_sql(sql: str)`**
- Runs SQL against Spider SQLite DB
- Agent should use SQL for: filtering, joins, GROUP BY, CTEs, aggregation on large tables
- Returns: row count, column names, first 5 rows, data types
- On error: returns error message so agent can self-correct

**`run_python(code: str, context: dict)`**
- Executes a Python/pandas cell in a sandboxed subprocess (timeout: 15s)
- `context` passes previously computed DataFrames by name
- Pre-installed: `pandas`, `numpy`, `matplotlib`, `scipy`
- Returns: stdout, errors, serialized output value
- On error: returns traceback so agent can self-correct

### SQL vs Python Split Rule

| Use SQL for | Use Python for |
|---|---|
| Filtering rows | Complex multi-step calculations |
| Joins across tables | Statistical analysis |
| GROUP BY aggregations | String formatting / parsing |
| CTEs and views | Plotting |
| Any data > 10k rows | Final answer formatting |

### Notebook Accumulator

Agent builds a notebook as it executes:
```python
notebook = [
    {"cell_type": "sql",    "code": "SELECT...",     "output": {...}},
    {"cell_type": "python", "code": "df.groupby...", "output": {...}},
    {"cell_type": "python", "code": "df.describe()", "output": {...}},
]
```
Full notebook logged as W&B artifact at end of each question.

### Answer Format

Agent always returns structured JSON alongside natural language:
```json
{
  "answer_value": 83400.0,
  "answer_text": "The average salary in Sales is $83,400",
  "sql": "SELECT AVG(salary) FROM employees WHERE department='Sales'",
  "notebook_cells": 3
}
```
`answer_value` is used for eval comparison — no formatting noise.

### Tracing with Weave

Every tool decorated with `@weave.op()`. In Weave UI you see:

```
run_agent
  └── explore_schema     (SQL call + output)
  └── generate_plan      (Mistral reasoning)
  └── execute_sql        (tool call 1)
  └── run_python         (tool call 2)
  └── format_answer      (final output)
```

Click any node to see exact inputs/outputs and latency. Failed evals are diagnosable by inspecting which node went wrong.

### W&B Metrics per Question

| Metric | What it measures |
|---|---|
| `exec_accuracy` | Final answer matches gold SQL result |
| `sql_error_rate` | SQL syntax/runtime errors |
| `python_error_rate` | Python cell crashes |
| `tool_calls_count` | Total SQL + Python calls |
| `cells_generated` | Notebook length |
| `retry_count` | Self-correction attempts |
| `latency_ms` | End-to-end time |

### Scorer — Handling Formatting

Gold SQL returns raw rows e.g. `[(83400.0,)]`.  
Agent returns `answer_value: 83400.0`.

Comparison:
```python
def score(agent_value, gold_rows):
    gold_value = gold_rows[0][0] if gold_rows else None
    return str(round(float(agent_value), 2)) == str(round(float(gold_value), 2))
```

No string matching. No SQL string comparison. Just final value match.

### ✅ Phase 1 Done When
- [ ] Agent runs end-to-end on a single Spider question
- [ ] Weave shows full trace tree
- [ ] W&B shows per-question metrics
- [ ] Baseline accuracy logged on 50-100 questions (expect ~40-60%)
- [ ] Notebooks saved as W&B artifacts

---

## Phase 2 — Eval Loop + Self-Improvement
**Time estimate: 4hrs**  
**Goal: Measurable accuracy improvement via automated prompt optimization**

### Eval Runner

Run agent on 100 Spider dev questions. Log everything.

```python
for i, example in enumerate(dev_data[:100]):
    output = run_agent(example["question"], db_path)
    gold   = execute(example["query"])
    
    correct = score(output["answer_value"], gold)
    
    wandb.log({
        "step": i,
        "correct": correct,
        "running_accuracy": cumulative_accuracy,
        ...
    })
```

### Failure Clustering

After each eval run, auto-cluster failures into categories:

| Category | Example |
|---|---|
| `wrong_table` | Agent queried `employees` instead of `staff` |
| `bad_join` | Missing join key, returned wrong rows |
| `missing_aggregation` | Forgot GROUP BY |
| `python_crash` | pandas cell threw exception |
| `answer_extraction_fail` | Could not parse final answer_value |
| `hallucinated_column` | Referenced column that doesn't exist |

Mistral call analyzes top 20 failures and returns structured categories + suggested prompt fixes.

### Improvement Loop

```
Run 100 questions → log accuracy (W&B)
         ↓
Cluster failures (Mistral call)
         ↓
Propose system prompt improvements (Mistral call)
         ↓
Re-run same 100 questions → log new accuracy (W&B)
         ↓
Repeat until accuracy delta < 1% (plateau)
```

Each iteration is a separate W&B run. W&B gives you an accuracy-over-iterations chart — this is your demo centerpiece.

### ✅ Phase 2 Done When
- [ ] At least 3 improvement iterations completed
- [ ] W&B chart shows accuracy trend across iterations
- [ ] Failure categories documented
- [ ] Plateau detected (or clear improvement story)
- [ ] Best prompt version saved as W&B artifact

---

## Phase 3 — SFT on Failure Cases
**Time estimate: 3hrs — only start when plateau is hit**  
**Goal: Fine-tuned Mistral model shows lift over best prompt-only version**

### Build SFT Dataset

Use questions the agent eventually got right (after retries) as training signal. The supervision is the full reasoning trace — not just gold SQL.

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Schema: ...\nQuestion: What is the average salary in Sales?"
    },
    {
      "role": "assistant", 
      "content": "EXPLORE: I need the employees table and department filter.\nPLAN: Single SQL aggregation, no Python needed.\nSQL: SELECT AVG(salary) FROM employees WHERE department='Sales'\nANSWER: {\"answer_value\": 83400.0, \"answer_text\": \"The average salary is $83,400\"}"
    }
  ]
}
```

Focus on the ~200 hardest failure cases. These are the highest signal examples.

### Fine-tune via Mistral API

```python
# Upload training file
# Call Mistral fine-tuning API
response = client.fine_tuning.jobs.create(
    model="mistral-small-latest",
    training_files=[{"file_id": uploaded_file_id}],
    hyperparameters={"epochs": 3}
)
```

Log fine-tuned model as W&B artifact.

### Evaluate Fine-tuned Model

Re-run same 100 eval questions with fine-tuned model. Log as new W&B run. Compare:

| Version | Accuracy |
|---|---|
| Baseline (Phase 1) | ~50% |
| Best prompt (Phase 2) | ~70% |
| Fine-tuned (Phase 3) | ~75%+ |

### ✅ Phase 3 Done When
- [ ] SFT dataset built from failure cases
- [ ] Fine-tune job completed via Mistral API
- [ ] Fine-tuned model evaluated on same 100 questions
- [ ] Before/after comparison visible in W&B
- [ ] Model artifact logged in W&B

---

## Demo Story

> "We built a self-improving analytics agent that explores schemas, writes SQL for large-scale transformations, and generates Python notebook cells for complex analysis. Starting from a 50% baseline on Spider, our automated eval loop diagnosed failure patterns and improved prompts to reach 70%. At plateau, we fine-tuned Mistral Small on the hardest cases and reached 75%+. Every step is traced in Weave and every metric is logged in W&B."

---

## Key Links

- [Spider Dataset](https://yale-lily.github.io/spider)
- [Spider on Hugging Face](https://huggingface.co/datasets/xlangai/spider)
- [Mistral Fine-Tuning Docs](https://docs.mistral.ai/capabilities/finetuning/)
- [W&B Weave Docs](https://docs.wandb.ai/weave)
- [W&B Models Docs](https://docs.wandb.ai/models)
- [W&B MCP Server](https://github.com/wandb/wandb-mcp-server)
- [LangGraph ReAct Agent](https://langchain-ai.github.io/langgraph/)
