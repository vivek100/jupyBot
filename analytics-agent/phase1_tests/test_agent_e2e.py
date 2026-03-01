from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import sqlite3
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


def _run_maybe_async(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


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


def build_temp_db() -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="phase1_db_"))
    db_path = temp_dir / "phase1.sqlite"
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
            ("Dan", 100000.0, "Engineering"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path.as_posix()


def _extract_numeric_answer(output: dict[str, Any]) -> float | None:
    value = output.get("answer_value")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    text = str(output.get("answer_text", ""))
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def test_agent_e2e_and_traces(project: str, entity: str | None) -> bool:
    print("\n[1/3] Agent end-to-end output + notebook + trace IDs")
    try:
        import weave

        from agent.agent import run_analytics_agent

        weave_target = f"{entity}/{project}" if entity else project
        weave.init(weave_target)
        db_path = build_temp_db()
        question = (
            "Use execute_sql to count employees in the table. "
            "Return JSON with answer_value and answer_text."
        )

        output, call = run_analytics_agent.call(question=question, db_path=db_path)
        notebook = output.get("notebook", [])
        metrics = output.get("metrics", {})

        if not output.get("answer_text"):
            raise RuntimeError(f"Missing answer_text: {output}")
        if not isinstance(notebook, list) or len(notebook) == 0:
            raise RuntimeError(f"Notebook missing/empty: {notebook}")
        if int(metrics.get("tool_calls_count", 0)) < 1:
            raise RuntimeError(f"No tool calls recorded: {metrics}")
        call_id = getattr(call, "id", None)
        trace_id = getattr(call, "trace_id", None) or getattr(call, "traceId", None)
        if not call_id or not trace_id:
            raise RuntimeError("Missing call_id/trace_id from traced run.")

        cell_types = sorted({c.get("cell_type", "unknown") for c in notebook})
        ok(f"runtime={output.get('runtime')} tool_calls={metrics.get('tool_calls_count')} cell_types={cell_types}")
        ok(f"trace call_id={call_id} trace_id={trace_id}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_agent_weave_eval(project: str, entity: str | None) -> bool:
    print("\n[2/3] Agent Weave eval (micro dataset)")
    try:
        import weave

        from agent.agent import run_analytics_agent

        weave_target = f"{entity}/{project}" if entity else project
        weave.init(weave_target)
        db_path = build_temp_db()

        class Phase1AgentModel(weave.Model):
            db_path: str

            @weave.op()
            def predict(self, question: str) -> dict[str, Any]:
                return run_analytics_agent(question=question, db_path=self.db_path)

        @weave.op()
        def numeric_match(output: dict[str, Any], expected_value: float) -> dict[str, Any]:
            got = _extract_numeric_answer(output)
            if got is None:
                return {"correct": False, "got": None}
            return {"correct": round(got, 2) == round(float(expected_value), 2), "got": got}

        dataset = [
            {"question": "Count all employees and return JSON answer.", "expected_value": 4.0},
            {"question": "What is average salary across all employees? Return JSON.", "expected_value": 85000.0},
        ]
        evaluation = weave.Evaluation(dataset=dataset, scorers=[numeric_match])
        model = Phase1AgentModel(db_path=db_path)
        result = _run_maybe_async(evaluation.evaluate(model))
        ok(f"weave_eval_result={str(result)[:300]}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def test_trace_eval_mapping_artifact(project: str, entity: str | None) -> bool:
    print("\n[3/3] Trace-to-eval mapping artifact generation")
    try:
        import weave

        from agent.agent import run_analytics_agent

        weave_target = f"{entity}/{project}" if entity else project
        weave.init(weave_target)
        db_path = build_temp_db()
        question = "Count employees and return JSON answer."
        expected_value = 4.0

        output, call = run_analytics_agent.call(question=question, db_path=db_path)
        got = _extract_numeric_answer(output)
        correct = got is not None and round(got, 2) == round(expected_value, 2)

        mapping = {
            "question_id": "phase1_qa_1",
            "question": question,
            "expected_output": {"answer_value": expected_value},
            "prediction": {"answer_value": output.get("answer_value"), "answer_text": output.get("answer_text")},
            "metrics": output.get("metrics", {}),
            "trace": {
                "call_id": getattr(call, "id", None),
                "trace_id": getattr(call, "trace_id", None) or getattr(call, "traceId", None),
            },
            "eval": {"correct": correct, "got_numeric": got},
        }

        out_dir = PROJECT_ROOT / "phase1_tests" / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "agent_eval_trace_mapping.json"
        out_path.write_text(json.dumps(mapping, indent=2, default=str), encoding="utf-8")
        ok(f"mapping_artifact={out_path.as_posix()}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def main() -> int:
    load_env()
    required = ["MISTRAL_API_KEY", "WANDB_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        banner("PHASE 1 TESTS - CONFIG CHECK")
        fail(f"Missing env vars: {missing}")
        return 1

    project = os.environ.get("WANDB_PROJECT", "jupybot")
    entity = os.environ.get("WANDB_ENTITY", "shukla-vivek1993-startup")

    banner("PHASE 1 TESTS - AGENT/TRACES/EVAL")
    checks = [
        test_agent_e2e_and_traces(project, entity),
        test_agent_weave_eval(project, entity),
        test_trace_eval_mapping_artifact(project, entity),
    ]
    passed = sum(int(x) for x in checks)
    total = len(checks)
    banner("PHASE 1 TESTS COMPLETE")
    print(f"Result: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
