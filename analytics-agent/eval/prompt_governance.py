from __future__ import annotations

import argparse
import ast
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RCA_TAGS = [
    "prompt_update",
    "tool_design",
    "architecture_change",
    "needs_model_training",
]


def extract_prompt_string(prompt_file: Path, variable_name: str = "SYSTEM_PROMPT") -> str:
    text = prompt_file.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == variable_name:
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value
                    if isinstance(value, ast.JoinedStr):
                        parts = []
                        for part in value.values:
                            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                                parts.append(part.value)
                        return "".join(parts)
    raise RuntimeError(f"Could not find string variable `{variable_name}` in {prompt_file.as_posix()}")


def estimate_tokens(char_count: int) -> int:
    # Conservative rough estimate for English-heavy prompts.
    return max(1, int(char_count / 4))


@dataclass
class GovernanceResult:
    ok: bool
    reasons: list[str]
    prompt_chars: int
    prompt_tokens_est: int
    max_prompt_chars: int
    max_prompt_tokens_est: int
    rca_tag: str | None
    pattern_failure_count: int
    pattern_threshold: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": self.reasons,
            "prompt_chars": self.prompt_chars,
            "prompt_tokens_est": self.prompt_tokens_est,
            "max_prompt_chars": self.max_prompt_chars,
            "max_prompt_tokens_est": self.max_prompt_tokens_est,
            "rca_tag": self.rca_tag,
            "pattern_failure_count": self.pattern_failure_count,
            "pattern_threshold": self.pattern_threshold,
        }


def evaluate_prompt_governance(
    prompt_chars: int,
    max_prompt_chars: int,
    max_prompt_tokens_est: int,
    rca_tag: str | None,
    pattern_failure_count: int,
    pattern_threshold: int,
) -> GovernanceResult:
    reasons: list[str] = []
    tokens_est = estimate_tokens(prompt_chars)

    if prompt_chars > max_prompt_chars:
        reasons.append(
            f"prompt size violation: chars={prompt_chars} exceeds max_prompt_chars={max_prompt_chars}"
        )
    if tokens_est > max_prompt_tokens_est:
        reasons.append(
            f"prompt token estimate violation: tokens~={tokens_est} exceeds max_prompt_tokens_est={max_prompt_tokens_est}"
        )
    if rca_tag == "prompt_update" and pattern_failure_count < pattern_threshold:
        reasons.append(
            "prompt update blocked by pattern threshold: "
            f"pattern_failure_count={pattern_failure_count} < pattern_threshold={pattern_threshold}"
        )

    return GovernanceResult(
        ok=len(reasons) == 0,
        reasons=reasons,
        prompt_chars=prompt_chars,
        prompt_tokens_est=tokens_est,
        max_prompt_chars=max_prompt_chars,
        max_prompt_tokens_est=max_prompt_tokens_est,
        rca_tag=rca_tag,
        pattern_failure_count=pattern_failure_count,
        pattern_threshold=pattern_threshold,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prompt-governance checker for RCA-driven fix policy."
    )
    parser.add_argument(
        "--prompt-file",
        default="analytics-agent/agent/prompt.py",
        help="Path to prompt source file containing SYSTEM_PROMPT.",
    )
    parser.add_argument(
        "--prompt-variable",
        default="SYSTEM_PROMPT",
        help="Prompt variable name in prompt file.",
    )
    parser.add_argument(
        "--rca-tag",
        choices=RCA_TAGS,
        default=None,
        help="RCA tag for the proposed fix. If prompt_update, pattern threshold rule is applied.",
    )
    parser.add_argument(
        "--pattern-failure-count",
        type=int,
        default=0,
        help="How many failures this pattern appears in.",
    )
    parser.add_argument(
        "--pattern-threshold",
        type=int,
        default=5,
        help="Minimum pattern count required before prompt_update is allowed.",
    )
    parser.add_argument(
        "--max-prompt-chars",
        type=int,
        default=int(os.environ.get("MAX_PROMPT_CHARS", "5000")),
    )
    parser.add_argument(
        "--max-prompt-tokens-est",
        type=int,
        default=int(os.environ.get("MAX_PROMPT_TOKENS_EST", "1400")),
    )
    parser.add_argument(
        "--emit-json",
        default=None,
        help="Optional output path for JSON result.",
    )
    args = parser.parse_args()

    prompt_file = Path(args.prompt_file)
    if not prompt_file.exists():
        print(f"prompt file not found: {prompt_file.as_posix()}")
        return 1
    prompt_text = extract_prompt_string(prompt_file=prompt_file, variable_name=args.prompt_variable)
    result = evaluate_prompt_governance(
        prompt_chars=len(prompt_text),
        max_prompt_chars=args.max_prompt_chars,
        max_prompt_tokens_est=args.max_prompt_tokens_est,
        rca_tag=args.rca_tag,
        pattern_failure_count=args.pattern_failure_count,
        pattern_threshold=args.pattern_threshold,
    )

    payload = result.as_dict()
    if args.emit_json:
        out_path = Path(args.emit_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["emit_json"] = out_path.as_posix()

    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
