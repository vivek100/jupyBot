from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
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


def build_temp_db() -> str:
    tmp_dir = Path(tempfile.mkdtemp(prefix="obs_db_"))
    db_path = tmp_dir / "obs.sqlite"
    conn = sqlite3.connect(db_path.as_posix())
    conn.execute("CREATE TABLE employees(id INTEGER PRIMARY KEY, salary REAL)")
    conn.executemany(
        "INSERT INTO employees(salary) VALUES (?)",
        [(70000.0,), (80000.0,), (90000.0,)],
    )
    conn.commit()
    conn.close()
    return db_path.as_posix()


def test_minimal_observability() -> bool:
    print("\n[1/1] Lean observability (trace index + run linkage)")
    try:
        from agent.agent import run_analytics_agent
        from eval.observability import (
            extract_trace_metadata,
            finish_observability_session,
            load_env_defaults,
            log_question_result,
            start_observability_session,
        )

        project, entity = load_env_defaults()
        db_path = build_temp_db()
        session = start_observability_session(
            run_name="phase1-observability-minimal-test",
            project=project,
            entity=entity,
            mode="lean",
            config={"phase": "phase1", "test": "minimal_observability"},
        )

        qid = "obs_q1"
        question = "Count employees and return JSON answer."
        output, call = run_analytics_agent.call(question=question, db_path=db_path)
        trace_meta = extract_trace_metadata(call)
        log_question_result(
            session=session,
            question_id=qid,
            question=question,
            output=output,
            trace_meta=trace_meta,
            expected_value=3.0,
            db_id="temp_obs_db",
            prompt_version="phase1_v1",
            agent_version="phase1_v1",
            extra={"mode": "lean"},
        )
        run_url = finish_observability_session(session)

        if not session.mapping_path.exists():
            raise RuntimeError("trace_index.jsonl not created")
        if not session.predictions_path.exists():
            raise RuntimeError("predictions.jsonl not created")
        if session.traces_path is not None and session.traces_path.exists():
            raise RuntimeError("lean mode unexpectedly created trace_metadata.jsonl")
        if session.notebooks_path is not None and session.notebooks_path.exists():
            raise RuntimeError("lean mode unexpectedly created notebooks.jsonl")

        row = None
        with session.mapping_path.open("r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
        if row is None:
            raise RuntimeError("trace_index.jsonl empty")

        required_fields = [
            "question_id",
            "expected_value",
            "answer_value",
            "correct",
            "wandb_run_id",
            "trace_id",
            "call_id",
            "prompt_version",
            "agent_version",
        ]
        missing = [k for k in required_fields if k not in row]
        if missing:
            raise RuntimeError(f"missing mapping fields: {missing}")
        if row["question_id"] != qid:
            raise RuntimeError("question_id mismatch in mapping")
        if not row.get("trace_id"):
            raise RuntimeError("trace_id missing in mapping")
        if not row.get("wandb_run_id"):
            raise RuntimeError("wandb_run_id missing in mapping")

        ok(f"mapping_path={session.mapping_path.as_posix()}")
        ok(f"run_url={run_url}")
        return True
    except Exception as exc:  # pragma: no cover
        fail(str(exc))
        return False


def main() -> int:
    load_env()
    required = ["MISTRAL_API_KEY", "WANDB_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        banner("PHASE 1 OBS TEST - CONFIG CHECK")
        fail(f"Missing env vars: {missing}")
        return 1

    banner("PHASE 1 OBS TEST - MINIMAL")
    checks = [test_minimal_observability()]
    passed = sum(int(x) for x in checks)
    total = len(checks)
    banner("PHASE 1 OBS TEST COMPLETE")
    print(f"Result: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

