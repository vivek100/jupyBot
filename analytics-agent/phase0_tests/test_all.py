from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]  # analytics-agent/
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env() -> None:
    local_env = PROJECT_ROOT / ".env"
    root_env = REPO_ROOT / ".env"
    if local_env.exists():
        load_dotenv(local_env)
    if root_env.exists():
        load_dotenv(root_env, override=False)


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def ok(msg: str) -> None:
    safe = str(msg).encode("ascii", errors="backslashreplace").decode("ascii")
    print(f"  PASS: {safe}")


def fail(msg: str) -> None:
    safe = str(msg).encode("ascii", errors="backslashreplace").decode("ascii")
    print(f"  FAIL: {safe}")


def _run_maybe_async(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _build_temp_db() -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="phase0_db_"))
    db_path = temp_dir / "phase0.sqlite"
    conn = sqlite3.connect(db_path.as_posix())
    conn.execute(
        "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, salary REAL, department TEXT)"
    )
    conn.executemany(
        "INSERT INTO employees (name, salary, department) VALUES (?, ?, ?)",
        [
            ("Alice", 70000.0, "Sales"),
            ("Bob", 80000.0, "Sales"),
            ("Carol", 90000.0, "Engineering"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path.as_posix()


def test_mistral_basic_chat(client) -> bool:
    print("\n[1/8] Mistral API - basic chat call")
    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": "Reply with: hello"}],
        )
        content = response.choices[0].message.content
        ok(f"response={content}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_wandb_metric_logging(project: str, entity: str | None) -> bool:
    print("\n[2/8] W&B - log a metric")
    try:
        import wandb

        run = wandb.init(project=project, entity=entity, name="phase0-test", reinit=True)
        wandb.log({"test_metric": 42.0})
        run.finish()
        ok("logged test_metric=42.0")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_weave_tracing(client, project: str, entity: str | None) -> bool:
    print("\n[3/8] Weave - trace a Mistral call")
    try:
        import weave

        weave_target = f"{entity}/{project}" if entity else project
        weave.init(weave_target)

        @weave.op()
        def traced_call():
            return client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": "Reply with: traced"}],
            ).choices[0].message.content

        result = traced_call()
        ok(f"response={result}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_spider_db_and_gold_sql(spider_root: Path) -> bool:
    print("\n[4/8] Spider - load DB and run gold SQL")
    try:
        dev_path = spider_root / "dev.json"
        db_dir = spider_root / "database"
        default_db = db_dir / "concert_singer" / "concert_singer.sqlite"
        if not default_db.exists():
            raise FileNotFoundError(f"Missing SQLite file: {default_db}")
        if not dev_path.exists():
            raise FileNotFoundError(f"Missing dev split: {dev_path}")

        with dev_path.open("r", encoding="utf-8") as f:
            dev = json.load(f)
        example = dev[0]
        db_id = example["db_id"]
        db_path = db_dir / db_id / f"{db_id}.sqlite"

        conn = sqlite3.connect(db_path.as_posix())
        rows = conn.execute(example["query"]).fetchall()
        conn.close()

        ok(f"db_id={db_id} rows_preview={rows[:3]}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_mistral_tool_calling(client) -> bool:
    print("\n[5/8] Mistral - function/tool calling")
    try:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_sql",
                    "description": "Run SQL and return rows",
                    "parameters": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"],
                    },
                },
            }
        ]
        resp = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": "Call execute_sql with SELECT 1 as one"}],
            tools=tools,
            tool_choice="any",
        )
        calls = resp.choices[0].message.tool_calls
        if not calls:
            raise RuntimeError("No tool_calls returned.")
        ok(f"tool={calls[0].function.name}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_python_subprocess_exec() -> bool:
    print("\n[6/8] Python sandbox - subprocess exec with pandas")
    try:
        code = (
            "import pandas as pd\n"
            "df = pd.DataFrame({'salary':[70000,80000,90000,100000]})\n"
            "print(df['salary'].mean())\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "unknown subprocess error")
        ok(f"output={proc.stdout.strip()}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_langgraph_react_smoke() -> bool:
    print("\n[7/8] LangGraph ReAct - direct Python invoke smoke test")
    try:
        from agent.phase0_react_agent import run_phase0_agent

        config_path = REPO_ROOT / "langgraph.json"
        if not config_path.exists():
            raise FileNotFoundError("Missing langgraph.json at repo root.")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if "graphs" not in config or "phase0_react_agent" not in config["graphs"]:
            raise RuntimeError("langgraph.json missing phase0_react_agent graph entry.")

        db_path = _build_temp_db()
        question = (
            "Use execute_sql to run SELECT COUNT(*) AS c FROM employees, "
            "then return JSON with answer_value and answer_text."
        )
        result = run_phase0_agent(question=question, db_path=db_path)
        answer_text = result.get("answer_text")
        runtime = result.get("runtime")
        if not answer_text:
            raise RuntimeError(f"No answer text returned: {result}")
        ok(f"runtime={runtime} answer_preview={str(answer_text)[:120]}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_phase0_eval_and_mapping(project: str, entity: str | None) -> bool:
    print("\n[8/8] Weave/W&B eval smoke + trace/eval mapping")
    try:
        import weave

        from agent.phase0_react_agent import run_phase0_agent

        weave_target = f"{entity}/{project}" if entity else project
        weave.init(weave_target)
        db_path = _build_temp_db()
        question = (
            "Use execute_sql to count employees and return JSON with answer_value and answer_text."
        )

        # Direct traced call for explicit trace metadata mapping.
        traced_result = run_phase0_agent(question=question, db_path=db_path)
        call_id = None
        trace_id = None
        if hasattr(run_phase0_agent, "call"):
            traced_result, call = run_phase0_agent.call(question=question, db_path=db_path)
            call_id = getattr(call, "id", None)
            trace_id = getattr(call, "trace_id", None) or getattr(call, "traceId", None)

        class Phase0Model(weave.Model):
            db_path: str

            @weave.op()
            def predict(self, question: str) -> dict[str, Any]:
                return run_phase0_agent(question=question, db_path=self.db_path)

        @weave.op()
        def has_answer(output: dict[str, Any], expected_has_answer: bool) -> dict[str, Any]:
            got = bool(output.get("answer_text"))
            return {"correct": got == expected_has_answer}

        dataset = [{"question": question, "expected_has_answer": True}]
        evaluation = weave.Evaluation(dataset=dataset, scorers=[has_answer])
        model = Phase0Model(db_path=db_path)
        eval_result = _run_maybe_async(evaluation.evaluate(model))

        manual_score = bool(traced_result.get("answer_text"))
        mapping = {
            "question_id": "phase0_eval_1",
            "question": question,
            "expected_output": {"expected_has_answer": True},
            "trace": {"call_id": call_id, "trace_id": trace_id},
            "eval": {"manual_score_correct": manual_score, "weave_eval_result": str(eval_result)[:500]},
        }
        print("  Mapping:", json.dumps(mapping, default=str))
        ok("eval smoke executed and mapping created")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def main() -> int:
    load_env()

    required = ["MISTRAL_API_KEY", "WANDB_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        banner("PHASE 0 - CONFIG CHECK")
        fail(f"Missing env vars: {missing}")
        return 1

    from mistralai import Mistral

    project = os.environ.get("WANDB_PROJECT", "jupybot")
    entity = os.environ.get("WANDB_ENTITY", "shukla-vivek1993-startup")
    spider_root = Path(os.environ.get("SPIDER_ROOT", "analytics-agent/data/spider"))

    def spider_root_looks_valid(root: Path) -> bool:
        return (
            (root / "dev.json").exists()
            and (root / "tables.json").exists()
            and (root / "database" / "concert_singer" / "concert_singer.sqlite").exists()
        )

    fallback = Path(r"C:\spider_data\spider_data")
    if not spider_root_looks_valid(spider_root) and spider_root_looks_valid(fallback):
        spider_root = fallback
    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    banner("PHASE 0 - ALL TOOLS + RUNTIME VERIFICATION")
    checks = [
        test_mistral_basic_chat(client),
        test_wandb_metric_logging(project, entity),
        test_weave_tracing(client, project, entity),
        test_spider_db_and_gold_sql(spider_root),
        test_mistral_tool_calling(client),
        test_python_subprocess_exec(),
        test_langgraph_react_smoke(),
        test_phase0_eval_and_mapping(project, entity),
    ]
    passed = sum(int(x) for x in checks)
    total = len(checks)
    banner("PHASE 0 COMPLETE")
    print(f"Result: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
