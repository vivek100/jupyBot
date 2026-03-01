from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

try:
    import weave
except ImportError:  # pragma: no cover
    weave = None


def _op(fn):
    if weave is None:
        return fn
    return weave.op()(fn)


class SQLToolInput(BaseModel):
    sql: str = Field(description="SQL query to execute")
    preview_rows: int = Field(default=5, description="Number of preview rows to return")


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    return str(value)


@_op
def _execute_sql_impl(sql: str, db_path: str, preview_rows: int = 5) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {"ok": False, "error": f"DB not found: {db_path}"}
    try:
        conn = sqlite3.connect(path.as_posix())
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        preview = rows[: max(1, preview_rows)]
        dtypes = {
            col: (type(preview[0][i]).__name__ if preview else "unknown")
            for i, col in enumerate(cols)
        }
        conn.close()
        return {
            "ok": True,
            "row_count": len(rows),
            "columns": cols,
            "preview_rows": _to_json_safe(preview),
            "dtypes": dtypes,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def create_execute_sql_tool(db_path: str):
    """Create a SQL tool bound to a specific SQLite database path."""

    @tool("execute_sql", args_schema=SQLToolInput)
    def execute_sql(sql: str, preview_rows: int = 5) -> str:
        """Execute SQL against the active SQLite DB and return JSON."""
        result = _execute_sql_impl(sql=sql, db_path=db_path, preview_rows=preview_rows)
        return json.dumps(result)

    return execute_sql
