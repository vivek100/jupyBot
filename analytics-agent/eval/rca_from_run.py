from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


def _classify_failure(pred: dict[str, Any], notebook: list[dict[str, Any]]) -> str:
    if pred.get("correct") is True:
        return "correct"
    answer_value = pred.get("answer_value")
    unresolved = False
    if notebook:
        last_out = notebook[-1].get("output") if isinstance(notebook[-1], dict) else None
        if isinstance(last_out, dict) and last_out.get("ok") is False:
            unresolved = True
    if unresolved:
        return "tool_error_unresolved"
    if isinstance(answer_value, (list, dict)):
        return "answer_shape_mismatch"
    if answer_value is None:
        text = str(pred.get("answer_text") or "").lower()
        if "sorry" in text or "couldn't" in text or "no information" in text:
            return "fallback_no_answer"
        return "null_answer"
    if isinstance(answer_value, str):
        return "answer_type_string_mismatch"
    return "other_wrong"


def _rca_mapping(category: str) -> tuple[str, str, str]:
    if category == "answer_shape_mismatch":
        return (
            "architecture_change",
            "answer_value_normalizer",
            "Model output format mismatches scorer contract (non-scalar answer_value).",
        )
    if category == "tool_error_unresolved":
        return (
            "tool_design",
            "sql_tool_error_assist",
            "SQL tool failures are not sufficiently recoverable from table/column errors.",
        )
    if category in ("fallback_no_answer", "null_answer"):
        return (
            "prompt_update",
            "strict_recovery_contract",
            "Agent finalizes without validated answer after error path.",
        )
    if category == "answer_type_string_mismatch":
        return (
            "architecture_change",
            "answer_value_normalizer",
            "Answer value emitted as free text rather than scorer-compatible scalar.",
        )
    return (
        "needs_model_training",
        "model_capability_gap",
        "No deterministic tooling/prompt pattern identified; likely model reasoning gap.",
    )


def build_rca_for_run(
    run_id: str,
    observability_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run_dir = observability_root / run_id
    pred_rows = _read_jsonl(run_dir / "predictions.jsonl")
    notebook_rows = _read_jsonl(run_dir / "notebooks.jsonl")
    notebook_by_q = {r.get("question_id"): r.get("notebook", []) for r in notebook_rows if r.get("question_id")}

    out_rows: list[dict[str, Any]] = []
    cat_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    for row in pred_rows:
        if row.get("correct") is True:
            continue
        qid = str(row.get("question_id"))
        notebook = notebook_by_q.get(qid, [])
        category = _classify_failure(row, notebook)
        tag, change_type, root_cause = _rca_mapping(category)
        cat_counts[category] += 1
        tag_counts[tag] += 1
        out_rows.append(
            {
                "run_id": run_id,
                "wandb_run_url": row.get("wandb_run_url"),
                "question_id": qid,
                "db_id": row.get("db_id"),
                "question": row.get("question"),
                "trace_id": row.get("trace_id"),
                "call_id": row.get("call_id"),
                "sql": row.get("sql"),
                "answer_value_preview": str(row.get("answer_value"))[:220],
                "answer_text_preview": str(row.get("answer_text"))[:220],
                "failure_category": category,
                "primary_rca_tag": tag,
                "suggested_change_type": change_type,
                "likely_root_cause": root_cause,
                "prompt_version": row.get("prompt_version"),
                "agent_version": row.get("agent_version"),
                "model_name": row.get("model_name"),
            }
        )

    summary = {
        "run_id": run_id,
        "questions_total": len(pred_rows),
        "questions_failed": len(out_rows),
        "failure_categories": dict(cat_counts),
        "primary_rca_tags": dict(tag_counts),
    }
    return out_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-question RCA rows for failed questions in a run.")
    parser.add_argument("--run-id", required=True, help="W&B run id (matches observability output folder).")
    parser.add_argument(
        "--observability-root",
        default="analytics-agent/outputs/observability",
        help="Root folder for observability artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default="analytics-agent/outputs/improvement",
        help="Output folder for RCA files.",
    )
    args = parser.parse_args()

    run_id = args.run_id.strip()
    rows, summary = build_rca_for_run(run_id=run_id, observability_root=Path(args.observability_root))

    output_dir = Path(args.output_dir)
    rca_rows_path = output_dir / f"rca_failures_{run_id}.jsonl"
    rca_summary_path = output_dir / f"rca_failures_{run_id}_summary.json"
    _write_jsonl(rca_rows_path, rows)
    rca_summary_path.parent.mkdir(parents=True, exist_ok=True)
    rca_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("RCA generation complete")
    print(f"run_id={run_id}")
    print(f"rows={len(rows)}")
    print(f"rca_rows_path={rca_rows_path.as_posix()}")
    print(f"rca_summary_path={rca_summary_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
