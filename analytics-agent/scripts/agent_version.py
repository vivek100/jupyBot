from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS = [
    "analytics-agent/agent",
    "langgraph.json",
    "analytics-agent/eval",
]


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def ensure_repo() -> None:
    try:
        run_git(["rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError as exc:  # pragma: no cover
        raise RuntimeError("Not a git repository. Run `git init` first.") from exc


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-")
    return cleaned or "snapshot"


def current_ref() -> str:
    proc = run_git(["rev-parse", "--short", "HEAD"], check=False)
    if proc.returncode != 0:
        return "no-commit"
    return proc.stdout.strip()


def snapshot(name: str, paths: list[str]) -> str:
    ensure_repo()
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"agent/{sanitize_name(name)}-{ts}"

    run_git(["add", *paths])
    status = run_git(["status", "--porcelain"], check=False).stdout.strip()
    if not status:
        print("No staged changes detected; creating lightweight tag on current HEAD.")
        run_git(["tag", tag])
        return tag

    msg = f"agent snapshot: {name} [{ts}]"
    run_git(["commit", "-m", msg])
    run_git(["tag", tag])
    return tag


def list_tags(limit: int = 30) -> list[str]:
    ensure_repo()
    proc = run_git(
        ["tag", "--list", "agent/*", "--sort=-creatordate"],
        check=False,
    )
    tags = [t.strip() for t in proc.stdout.splitlines() if t.strip()]
    return tags[:limit]


def restore(ref: str, paths: list[str]) -> None:
    ensure_repo()
    # File/path-limited restore to avoid destructive full-checkout behavior.
    run_git(["checkout", ref, "--", *paths])


def main() -> int:
    parser = argparse.ArgumentParser(description="Git snapshot/rollback helper for analytics agent.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snapshot = sub.add_parser("snapshot", help="Commit and tag current agent state.")
    p_snapshot.add_argument("--name", required=True, help="Snapshot label (e.g., phase1-observability)")
    p_snapshot.add_argument(
        "--paths",
        nargs="+",
        default=DEFAULT_PATHS,
        help="Paths to include in snapshot commit",
    )

    p_list = sub.add_parser("list", help="List recent agent tags.")
    p_list.add_argument("--limit", type=int, default=30)

    p_restore = sub.add_parser("restore", help="Restore agent files from tag/commit.")
    p_restore.add_argument("--ref", required=True, help="Tag or commit ref to restore from.")
    p_restore.add_argument(
        "--paths",
        nargs="+",
        default=DEFAULT_PATHS,
        help="Paths to restore",
    )

    sub.add_parser("status", help="Show current ref and dirty state.")

    args = parser.parse_args()

    if args.cmd == "snapshot":
        tag = snapshot(name=args.name, paths=args.paths)
        print(f"Snapshot created: {tag}")
        print(f"Current ref: {current_ref()}")
        print(f"Restore example: python analytics-agent/scripts/agent_version.py restore --ref {tag}")
        return 0

    if args.cmd == "list":
        tags = list_tags(limit=args.limit)
        if not tags:
            print("No agent tags found.")
            return 0
        print("\n".join(tags))
        return 0

    if args.cmd == "restore":
        restore(ref=args.ref, paths=args.paths)
        print(f"Restored {args.paths} from {args.ref}")
        return 0

    if args.cmd == "status":
        ensure_repo()
        ref = current_ref()
        dirty = bool(run_git(["status", "--porcelain"], check=False).stdout.strip())
        print(f"ref={ref}")
        print(f"dirty={dirty}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

