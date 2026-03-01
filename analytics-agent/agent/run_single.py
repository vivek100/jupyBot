from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from agent.agent import resolve_default_db_path, run_analytics_agent
else:
    from .agent import resolve_default_db_path, run_analytics_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one analytics-agent question.")
    parser.add_argument("--question", required=True, help="Natural language question")
    parser.add_argument(
        "--db-path",
        default=resolve_default_db_path(),
        help="Path to target SQLite database",
    )
    parser.add_argument(
        "--model",
        default="mistral-small-latest",
        help="Mistral model name",
    )
    args = parser.parse_args()

    result = run_analytics_agent(
        question=args.question,
        db_path=args.db_path,
        model_name=args.model,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
