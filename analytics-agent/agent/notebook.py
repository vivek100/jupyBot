from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _parse_json_maybe(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


@dataclass
class NotebookAccumulator:
    cells: list[dict[str, Any]] = field(default_factory=list)

    def add_sql(self, sql: str, output: Any) -> None:
        self.cells.append(
            {"cell_type": "sql", "code": sql, "output": _parse_json_maybe(output)}
        )

    def add_python(self, code: str, output: Any) -> None:
        self.cells.append(
            {"cell_type": "python", "code": code, "output": _parse_json_maybe(output)}
        )

    def add_tool(self, tool_name: str, args: dict[str, Any], output: Any) -> None:
        if tool_name == "execute_sql":
            self.add_sql(args.get("sql", ""), output)
            return
        if tool_name == "run_python":
            self.add_python(args.get("code", ""), output)
            return
        self.cells.append(
            {
                "cell_type": "tool",
                "tool_name": tool_name,
                "args": args,
                "output": _parse_json_maybe(output),
            }
        )

    def to_list(self) -> list[dict[str, Any]]:
        return list(self.cells)

    def __len__(self) -> int:
        return len(self.cells)

