from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _status_from_correct(correct: Any) -> str:
    return "pass" if correct is True else "fail"


@dataclass
class HistoryBuildResult:
    history_rows: list[dict[str, Any]]
    latest_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _find_trace_index_files(observability_root: Path, run_ids: list[str] | None = None) -> list[Path]:
    if run_ids:
        return [
            observability_root / rid / "trace_index.jsonl"
            for rid in run_ids
            if (observability_root / rid / "trace_index.jsonl").exists()
        ]
    return sorted(observability_root.glob("*/trace_index.jsonl"))


def _fix_judgement_index(fix_judgement_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    idx: dict[tuple[str, str], dict[str, Any]] = {}
    for row in fix_judgement_rows:
        qid = str(row.get("question_id") or "").strip()
        rid = str(row.get("wandb_run_id") or row.get("run_id") or "").strip()
        if not qid or not rid:
            continue
        idx[(qid, rid)] = row
    return idx


def build_question_history(
    trace_rows: list[dict[str, Any]],
    fix_judgement_rows: list[dict[str, Any]] | None = None,
) -> HistoryBuildResult:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trace_rows:
        qid = row.get("question_id")
        if not qid:
            continue
        grouped[str(qid)].append(row)

    judgement_idx = _fix_judgement_index(fix_judgement_rows or [])
    history_rows: list[dict[str, Any]] = []
    latest_rows: list[dict[str, Any]] = []

    transition_counts: dict[str, int] = defaultdict(int)
    question_counts = {"total": 0, "stable_pass": 0, "stable_fail": 0, "mixed": 0}

    for qid, rows in grouped.items():
        def _sort_key(r: dict[str, Any]) -> tuple[Any, Any, Any]:
            dt = _parse_iso(r.get("logged_at")) or _parse_iso(r.get("trace_started_at"))
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_value = dt.timestamp()
            else:
                dt_value = 0.0
            step = r.get("step")
            run_id = r.get("wandb_run_id")
            return (dt_value, step if isinstance(step, int) else -1, run_id or "")

        rows_sorted = sorted(rows, key=_sort_key)
        first_seen = rows_sorted[0]
        first_pass_row: dict[str, Any] | None = None
        prev_status: str | None = None
        statuses: list[str] = []

        for idx, row in enumerate(rows_sorted):
            current_status = _status_from_correct(row.get("correct"))
            statuses.append(current_status)
            transition = (
                f"start_{current_status}" if prev_status is None else f"{prev_status}->{current_status}"
            )
            transition_counts[transition] += 1

            if first_pass_row is None and current_status == "pass":
                first_pass_row = row

            run_id = str(row.get("wandb_run_id") or "")
            judgement = judgement_idx.get((qid, run_id), {})

            history_row = {
                "question_id": qid,
                "sequence_index": idx,
                "transition": transition,
                "previous_status": prev_status,
                "current_status": current_status,
                "changed_from_previous": prev_status is not None and prev_status != current_status,
                "logged_at": row.get("logged_at"),
                "wandb_run_id": row.get("wandb_run_id"),
                "wandb_run_name": row.get("wandb_run_name"),
                "wandb_run_url": row.get("wandb_run_url"),
                "phase": row.get("phase"),
                "group": row.get("group"),
                "agent_version": row.get("agent_version"),
                "prompt_version": row.get("prompt_version"),
                "model_name": row.get("model_name"),
                "correct": row.get("correct"),
                "expected_value": row.get("expected_value"),
                "answer_value": row.get("answer_value"),
                "trace_id": row.get("trace_id"),
                "call_id": row.get("call_id"),
                "fix_id": judgement.get("fix_id"),
                "fix_decision": judgement.get("decision"),
                "fix_judgement": judgement.get("judgement"),
                "fix_notes": judgement.get("notes"),
                "first_seen_run_id": first_seen.get("wandb_run_id"),
                "first_seen_logged_at": first_seen.get("logged_at"),
                "first_pass_run_id": first_pass_row.get("wandb_run_id") if first_pass_row else None,
                "first_pass_logged_at": first_pass_row.get("logged_at") if first_pass_row else None,
            }
            history_rows.append(history_row)
            prev_status = current_status

        latest = history_rows[-1].copy()
        latest["records_seen"] = len(rows_sorted)
        latest_rows.append(latest)

        question_counts["total"] += 1
        unique_statuses = set(statuses)
        if unique_statuses == {"pass"}:
            question_counts["stable_pass"] += 1
        elif unique_statuses == {"fail"}:
            question_counts["stable_fail"] += 1
        else:
            question_counts["mixed"] += 1

    history_rows.sort(key=lambda r: (r.get("question_id") or "", r.get("sequence_index") or -1))
    latest_rows.sort(key=lambda r: r.get("question_id") or "")

    summary = {
        "questions": question_counts,
        "rows_written": len(history_rows),
        "latest_rows_written": len(latest_rows),
        "transition_counts": dict(sorted(transition_counts.items())),
    }
    return HistoryBuildResult(history_rows=history_rows, latest_rows=latest_rows, summary=summary)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build cross-run question history from observability trace_index.jsonl files."
    )
    parser.add_argument(
        "--observability-root",
        default="analytics-agent/outputs/observability",
        help="Directory containing per-run observability folders.",
    )
    parser.add_argument(
        "--output-dir",
        default="analytics-agent/outputs/improvement",
        help="Directory to write question_history outputs.",
    )
    parser.add_argument(
        "--run-ids",
        default=None,
        help="Optional comma-separated wandb run ids to include. Default: all runs under observability-root.",
    )
    parser.add_argument(
        "--fix-judgement-path",
        default="analytics-agent/outputs/improvement/fix_judgement.jsonl",
        help="Optional fix-judgement JSONL used to enrich question history rows.",
    )
    args = parser.parse_args()

    observability_root = Path(args.observability_root)
    output_dir = Path(args.output_dir)
    run_ids = [x.strip() for x in str(args.run_ids).split(",") if x.strip()] if args.run_ids else None
    fix_judgement_path = Path(args.fix_judgement_path)

    trace_files = _find_trace_index_files(observability_root=observability_root, run_ids=run_ids)
    if not trace_files:
        print(f"No trace_index files found under: {observability_root}")
        return 1

    trace_rows: list[dict[str, Any]] = []
    for f in trace_files:
        trace_rows.extend(_read_jsonl(f))

    fix_judgement_rows = _read_jsonl(fix_judgement_path) if fix_judgement_path.exists() else []
    result = build_question_history(trace_rows=trace_rows, fix_judgement_rows=fix_judgement_rows)

    history_path = output_dir / "question_history.jsonl"
    latest_path = output_dir / "question_latest.jsonl"
    summary_path = output_dir / "question_history_summary.json"
    _write_jsonl(history_path, result.history_rows)
    _write_jsonl(latest_path, result.latest_rows)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(result.summary, indent=2), encoding="utf-8")

    print("Question history build complete")
    print(f"trace_files={len(trace_files)}")
    print(f"history_rows={len(result.history_rows)}")
    print(f"latest_rows={len(result.latest_rows)}")
    print(f"history_path={history_path.as_posix()}")
    print(f"latest_path={latest_path.as_posix()}")
    print(f"summary_path={summary_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
