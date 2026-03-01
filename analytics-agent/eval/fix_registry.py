from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RCA_TAGS = [
    "prompt_update",
    "tool_design",
    "architecture_change",
    "needs_model_training",
]

DECISIONS = ["proposed", "accepted", "rejected", "deferred", "rolled_back"]
QUESTION_JUDGEMENTS = ["improved", "regressed", "unchanged", "not_applicable"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
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


def _csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON argument: {value}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON argument must be an object.")
    return parsed


def _reduce_registry(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_fix: dict[str, dict[str, Any]] = {}
    for ev in events:
        fix_id = str(ev.get("fix_id") or "").strip()
        if not fix_id:
            continue
        state = by_fix.setdefault(
            fix_id,
            {
                "fix_id": fix_id,
                "status": "proposed",
                "_has_decision": False,
                "rca_tag": None,
                "change_type": None,
                "description": None,
                "agent_version": None,
                "prompt_version": None,
                "toolset_version": None,
                "graph_version": None,
                "related_run_ids": [],
                "related_trace_ids": [],
                "related_question_ids": [],
                "last_updated_at": None,
                "event_count": 0,
            },
        )

        state["event_count"] += 1
        state["last_updated_at"] = ev.get("event_at")

        for key in ("rca_tag", "change_type", "description", "agent_version", "prompt_version", "toolset_version", "graph_version"):
            if ev.get(key) not in (None, ""):
                state[key] = ev.get(key)

        decision = ev.get("decision")
        if decision and ev.get("event_type") == "decision":
            state["status"] = decision
            state["_has_decision"] = True
        elif ev.get("event_type") == "proposed" and not state.get("_has_decision"):
            state["status"] = "proposed"

        for src, dst in (
            ("run_id", "related_run_ids"),
            ("trace_ids", "related_trace_ids"),
            ("question_ids", "related_question_ids"),
        ):
            val = ev.get(src)
            vals: list[str]
            if isinstance(val, list):
                vals = [str(x) for x in val if str(x).strip()]
            elif isinstance(val, str):
                vals = [v.strip() for v in val.split(",") if v.strip()]
            else:
                vals = []
            for item in vals:
                if item not in state[dst]:
                    state[dst].append(item)

    for s in by_fix.values():
        s.pop("_has_decision", None)
    return by_fix


def _print_registry(state_by_fix: dict[str, dict[str, Any]]) -> None:
    if not state_by_fix:
        print("No fixes in registry.")
        return
    for fix_id in sorted(state_by_fix):
        s = state_by_fix[fix_id]
        print(
            f"{fix_id} status={s.get('status')} rca={s.get('rca_tag')} "
            f"agent={s.get('agent_version')} prompt={s.get('prompt_version')} "
            f"runs={len(s.get('related_run_ids', []))} questions={len(s.get('related_question_ids', []))}"
        )


def cmd_propose(args: argparse.Namespace) -> int:
    row = {
        "event_at": _utc_now_iso(),
        "event_type": "proposed",
        "fix_id": args.fix_id,
        "rca_tag": args.rca_tag,
        "change_type": args.change_type,
        "description": args.description,
        "hypothesis": args.hypothesis,
        "decision": "proposed",
        "agent_version": args.agent_version,
        "prompt_version": args.prompt_version,
        "toolset_version": args.toolset_version,
        "graph_version": args.graph_version,
        "run_id": args.run_id,
        "trace_ids": _csv_list(args.trace_ids),
        "question_ids": _csv_list(args.question_ids),
        "metadata": _json_arg(args.metadata),
    }
    _append_jsonl(Path(args.registry_path), row)
    print(f"Proposed fix recorded: {args.fix_id}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    row = {
        "event_at": _utc_now_iso(),
        "event_type": "decision",
        "fix_id": args.fix_id,
        "decision": args.decision,
        "rationale": args.rationale,
        "run_id": args.run_id,
        "trace_ids": _csv_list(args.trace_ids),
        "question_ids": _csv_list(args.question_ids),
        "metadata": _json_arg(args.metadata),
    }
    _append_jsonl(Path(args.registry_path), row)
    print(f"Decision recorded: {args.fix_id} -> {args.decision}")
    return 0


def cmd_link_evidence(args: argparse.Namespace) -> int:
    row = {
        "event_at": _utc_now_iso(),
        "event_type": "evidence",
        "fix_id": args.fix_id,
        "run_id": args.run_id,
        "trace_ids": _csv_list(args.trace_ids),
        "question_ids": _csv_list(args.question_ids),
        "metrics_before": _json_arg(args.metrics_before),
        "metrics_after": _json_arg(args.metrics_after),
        "notes": args.notes,
        "metadata": _json_arg(args.metadata),
    }
    _append_jsonl(Path(args.registry_path), row)
    print(f"Evidence linked: {args.fix_id}")
    return 0


def cmd_judge_question(args: argparse.Namespace) -> int:
    row = {
        "judged_at": _utc_now_iso(),
        "question_id": args.question_id,
        "wandb_run_id": args.run_id,
        "fix_id": args.fix_id,
        "decision": args.decision,
        "judgement": args.judgement,
        "notes": args.notes,
        "metadata": _json_arg(args.metadata),
    }
    _append_jsonl(Path(args.fix_judgement_path), row)
    print(f"Question judgement recorded: q={args.question_id} fix={args.fix_id}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    events = _read_jsonl(Path(args.registry_path))
    state = _reduce_registry(events)
    _print_registry(state)
    return 0


def cmd_export_current(args: argparse.Namespace) -> int:
    events = _read_jsonl(Path(args.registry_path))
    state = _reduce_registry(events)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for fix_id in sorted(state):
            f.write(json.dumps(state[fix_id], default=str) + "\n")
    print(f"Exported current registry state: {out_path.as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fix registry and question judgement manager.")
    parser.add_argument(
        "--registry-path",
        default="analytics-agent/outputs/improvement/fix_registry.jsonl",
        help="Path to append/read fix registry events.",
    )
    parser.add_argument(
        "--fix-judgement-path",
        default="analytics-agent/outputs/improvement/fix_judgement.jsonl",
        help="Path to append question-level fix judgements.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    propose = sub.add_parser("propose", help="Record a proposed fix.")
    propose.add_argument("--fix-id", required=True)
    propose.add_argument("--rca-tag", required=True, choices=RCA_TAGS)
    propose.add_argument("--change-type", required=True)
    propose.add_argument("--description", required=True)
    propose.add_argument("--hypothesis", default=None)
    propose.add_argument("--agent-version", default=None)
    propose.add_argument("--prompt-version", default=None)
    propose.add_argument("--toolset-version", default=None)
    propose.add_argument("--graph-version", default=None)
    propose.add_argument("--run-id", default=None)
    propose.add_argument("--trace-ids", default=None, help="Comma-separated list.")
    propose.add_argument("--question-ids", default=None, help="Comma-separated list.")
    propose.add_argument("--metadata", default=None, help="JSON object string.")
    propose.set_defaults(func=cmd_propose)

    decide = sub.add_parser("decide", help="Record fix decision.")
    decide.add_argument("--fix-id", required=True)
    decide.add_argument("--decision", required=True, choices=DECISIONS[1:])
    decide.add_argument("--rationale", required=True)
    decide.add_argument("--run-id", default=None)
    decide.add_argument("--trace-ids", default=None)
    decide.add_argument("--question-ids", default=None)
    decide.add_argument("--metadata", default=None)
    decide.set_defaults(func=cmd_decide)

    evidence = sub.add_parser("link-evidence", help="Link run/trace/question evidence to a fix.")
    evidence.add_argument("--fix-id", required=True)
    evidence.add_argument("--run-id", required=True)
    evidence.add_argument("--trace-ids", default=None)
    evidence.add_argument("--question-ids", default=None)
    evidence.add_argument("--metrics-before", default=None, help="JSON object string.")
    evidence.add_argument("--metrics-after", default=None, help="JSON object string.")
    evidence.add_argument("--notes", default=None)
    evidence.add_argument("--metadata", default=None)
    evidence.set_defaults(func=cmd_link_evidence)

    judge = sub.add_parser("judge-question", help="Record question-level outcome for a fix.")
    judge.add_argument("--question-id", required=True)
    judge.add_argument("--run-id", required=True)
    judge.add_argument("--fix-id", required=True)
    judge.add_argument("--decision", required=True, choices=DECISIONS[1:])
    judge.add_argument("--judgement", required=True, choices=QUESTION_JUDGEMENTS)
    judge.add_argument("--notes", default=None)
    judge.add_argument("--metadata", default=None)
    judge.set_defaults(func=cmd_judge_question)

    show = sub.add_parser("show", help="Print reduced current fix registry state.")
    show.set_defaults(func=cmd_show)

    export_current = sub.add_parser("export-current", help="Export reduced state to JSONL.")
    export_current.add_argument(
        "--out-path",
        default="analytics-agent/outputs/improvement/fix_registry_current.jsonl",
    )
    export_current.set_defaults(func=cmd_export_current)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
