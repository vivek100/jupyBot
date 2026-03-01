from __future__ import annotations

import argparse
from typing import Any

import wandb


def parse_pairs(items: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid pair format `{item}`. Use run_id=label.")
        run_id, label = item.split("=", 1)
        run_id = run_id.strip()
        label = label.strip()
        if not run_id or not label:
            raise ValueError(f"Invalid run_id/label in `{item}`.")
        pairs.append((run_id, label))
    return pairs


def label_run(entity: str, project: str, run_id: str, label: str, extra_tags: list[str]) -> dict[str, Any]:
    api = wandb.Api()
    run = api.run(f"{entity}/{project}/{run_id}")

    tags = list(run.tags or [])
    for t in ["eval_loop", "rca_tracked", label, *extra_tags]:
        if t not in tags:
            tags.append(t)
    run.tags = tags
    run.summary["run_label"] = label
    run.summary["run_sequence"] = label
    run.summary["rca_tracking_enabled"] = True
    run.update()
    return {
        "run_id": run_id,
        "label": label,
        "url": run.url,
        "tags": tags,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply human-friendly labels/tags to W&B runs.")
    parser.add_argument("--entity", default="shukla-vivek1993-startup")
    parser.add_argument("--project", default="jupybot")
    parser.add_argument(
        "--set",
        action="append",
        required=True,
        help="Set run label in format run_id=label. Repeat for multiple runs.",
    )
    parser.add_argument(
        "--extra-tag",
        action="append",
        default=[],
        help="Optional extra tags to apply to all labeled runs.",
    )
    args = parser.parse_args()

    pairs = parse_pairs(args.set)
    for run_id, label in pairs:
        res = label_run(
            entity=args.entity,
            project=args.project,
            run_id=run_id,
            label=label,
            extra_tags=args.extra_tag,
        )
        print(f"{res['run_id']} -> {res['label']} ({res['url']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
