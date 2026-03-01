from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[1]
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env() -> None:
    local_env = PROJECT_ROOT / ".env"
    root_env = REPO_ROOT / ".env"
    if local_env.exists():
        load_dotenv(local_env)
    if root_env.exists():
        load_dotenv(root_env, override=False)


def resolve_spider_root() -> Path:
    env_root = os.environ.get("SPIDER_ROOT")
    if env_root:
        return Path(env_root)
    fallback = Path(r"C:\spider_data\spider_data")
    if fallback.exists():
        return fallback
    return Path("analytics-agent/data/spider")


def get_git_short_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or "no-commit"
        return "no-commit"
    except Exception:
        return "no-commit"


def run_gold_sql(db_path: Path, sql: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db_path.as_posix())
    try:
        rows = conn.execute(sql).fetchall()
        return rows
    finally:
        conn.close()


def main() -> int:
    load_env()

    required = ["MISTRAL_API_KEY", "WANDB_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing env vars: {missing}")
        return 1

    parser = argparse.ArgumentParser(description="Run Spider eval with analytics agent.")
    parser.add_argument("--limit", type=int, default=5, help="Number of Spider dev questions to run")
    parser.add_argument("--offset", type=int, default=0, help="Starting index in dev.json")
    parser.add_argument("--model", default="mistral-small-latest")
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    from agent.agent import run_analytics_agent
    from eval.observability import (
        extract_trace_metadata,
        finish_observability_session,
        load_env_defaults,
        log_question_result,
        start_observability_session,
    )
    from eval.scorer import extract_gold_value, score

    spider_root = resolve_spider_root()
    dev_path = spider_root / "dev.json"
    db_root = spider_root / "database"
    if not dev_path.exists():
        print(f"dev.json not found: {dev_path}")
        return 1
    if not db_root.exists():
        print(f"database/ not found: {db_root}")
        return 1

    with dev_path.open("r", encoding="utf-8") as f:
        dev = json.load(f)

    slice_data = dev[args.offset : args.offset + args.limit]
    if not slice_data:
        print("No examples selected; check --offset/--limit.")
        return 1

    git_sha = get_git_short_sha()
    project, entity = load_env_defaults()
    run_name = args.run_name or f"spider-eval-{args.offset}-{args.offset + len(slice_data) - 1}"

    session = start_observability_session(
        run_name=run_name,
        project=project,
        entity=entity,
        group="phase2-benchmark",
        tags=["phase2", "spider", "eval"],
        config={
            "phase": "phase2",
            "benchmark": "spider_dev",
            "offset": args.offset,
            "limit": args.limit,
            "model": args.model,
            "agent_version": git_sha,
            "prompt_version": "phase1_v1",
        },
        mode="lean",
    )

    total = 0
    correct_count = 0
    skipped = 0

    for i, ex in enumerate(slice_data):
        qid = f"spider_{args.offset + i}"
        question = ex["question"]
        db_id = ex["db_id"]
        gold_sql = ex["query"]
        db_path = db_root / db_id / f"{db_id}.sqlite"
        if not db_path.exists():
            skipped += 1
            continue

        gold_rows = run_gold_sql(db_path, gold_sql)
        expected_value = extract_gold_value(gold_rows)

        output, call = run_analytics_agent.call(
            question=question,
            db_path=db_path.as_posix(),
            model_name=args.model,
        )
        trace_meta = extract_trace_metadata(call)

        is_correct = score(output.get("answer_value"), gold_rows)
        if is_correct:
            correct_count += 1
        total += 1

        log_question_result(
            session=session,
            question_id=qid,
            question=question,
            output=output,
            trace_meta=trace_meta,
            expected_value=expected_value,
            db_id=db_id,
            prompt_version="phase1_v1",
            agent_version=git_sha,
            extra={
                "gold_sql": gold_sql,
                "gold_row_count": len(gold_rows),
                "correct": is_correct,
            },
        )

        running_acc = correct_count / total if total else 0.0
        session.run.log({"step": session.step, "running_accuracy": running_acc})
        print(
            f"[{i+1}/{len(slice_data)}] qid={qid} db={db_id} "
            f"correct={is_correct} running_acc={running_acc:.3f}"
        )

    final_acc = correct_count / total if total else 0.0
    session.run.summary["questions_total"] = total
    session.run.summary["questions_skipped"] = skipped
    session.run.summary["questions_correct"] = correct_count
    session.run.summary["final_accuracy"] = final_acc
    session.run.summary["agent_version"] = git_sha
    session.run.summary["prompt_version"] = "phase1_v1"

    run_url = finish_observability_session(session)
    print("\nEval complete")
    print(f"questions_total={total}")
    print(f"questions_correct={correct_count}")
    print(f"questions_skipped={skipped}")
    print(f"final_accuracy={final_acc:.4f}")
    print(f"wandb_run_url={run_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

