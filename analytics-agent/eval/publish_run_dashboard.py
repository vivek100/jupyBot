from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import wandb


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
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _table_cell(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


def _table_from_rows(rows: list[dict[str, Any]]) -> wandb.Table:
    if not rows:
        return wandb.Table(columns=["note"], data=[["no rows"]])
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    # Use string-safe cells to avoid W&B mixed-type inference collisions.
    data = []
    for row in rows:
        out_row = []
        for col in columns:
            val = row.get(col)
            if val is None:
                out_row.append("")
            else:
                out_row.append(str(_table_cell(val)))
        data.append(out_row)
    return wandb.Table(columns=columns, data=data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish canonical eval metrics and RCA tables to a W&B run.")
    parser.add_argument("--entity", default="shukla-vivek1993-startup")
    parser.add_argument("--project", default="jupybot")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional new display name for the run (e.g., 'run 1').",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Optional run label stored in summary (e.g., run_1).",
    )
    parser.add_argument(
        "--observability-root",
        default="analytics-agent/outputs/observability",
    )
    parser.add_argument(
        "--improvement-root",
        default="analytics-agent/outputs/improvement",
    )
    parser.add_argument(
        "--rca-max-rows",
        type=int,
        default=200,
        help="Max RCA rows to put in dashboard table.",
    )
    args = parser.parse_args()

    run_id = args.run_id.strip()
    obs_dir = Path(args.observability_root) / run_id
    imp_dir = Path(args.improvement_root)

    predictions = _read_jsonl(obs_dir / "predictions.jsonl")
    failures = _read_jsonl(obs_dir / "failures.jsonl")
    rca_rows = _read_jsonl(imp_dir / f"rca_failures_{run_id}.jsonl")
    rca_summary_path = imp_dir / f"rca_failures_{run_id}_summary.json"
    rca_summary = {}
    if rca_summary_path.exists():
        try:
            rca_summary = json.loads(rca_summary_path.read_text(encoding="utf-8"))
        except Exception:
            rca_summary = {}

    questions_total = len(predictions)
    questions_correct = sum(1 for r in predictions if r.get("correct") is True)
    final_accuracy = (questions_correct / questions_total) if questions_total else 0.0

    run = wandb.init(
        project=args.project,
        entity=args.entity,
        id=run_id,
        resume="allow",
        name=args.run_name,
        reinit="finish_previous",
    )

    # Canonical eval summary keys for dashboard filtering.
    run.summary["eval/questions_total"] = questions_total
    run.summary["eval/questions_correct"] = questions_correct
    run.summary["eval/questions_failed"] = questions_total - questions_correct
    run.summary["eval/final_accuracy"] = final_accuracy
    run.summary["final_accuracy"] = final_accuracy
    run.summary["questions_total"] = questions_total
    run.summary["questions_correct"] = questions_correct
    if args.run_label:
        run.summary["run_label"] = args.run_label
        run.summary["run_sequence"] = args.run_label

    if rca_summary:
        run.summary["rca/questions_failed"] = rca_summary.get("questions_failed")
        run.summary["rca/failure_categories"] = rca_summary.get("failure_categories")
        run.summary["rca/primary_tags"] = rca_summary.get("primary_rca_tags")

    # Dashboard tables.
    run.log(
        {
            "dashboard/eval_score": final_accuracy,
            "dashboard/failed_questions_count": len(failures),
            "dashboard/rca_failures_table": _table_from_rows(rca_rows[: max(1, args.rca_max_rows)]),
        }
    )

    # Attach a compact RCA summary artifact for this run dashboard.
    artifact = wandb.Artifact(name=f"dashboard-rca-{run_id}", type="analysis")
    if rca_summary_path.exists():
        artifact.add_file(str(rca_summary_path))
    rca_rows_path = imp_dir / f"rca_failures_{run_id}.jsonl"
    if rca_rows_path.exists():
        artifact.add_file(str(rca_rows_path))
    run.log_artifact(artifact)

    url = run.url
    run.finish()
    print(f"updated_run={run_id}")
    print(f"run_url={url}")
    print(f"questions_total={questions_total}")
    print(f"questions_correct={questions_correct}")
    print(f"eval_final_accuracy={final_accuracy:.4f}")
    print(f"rca_rows={len(rca_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
