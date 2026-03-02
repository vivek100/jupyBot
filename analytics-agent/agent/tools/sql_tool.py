from __future__ import annotations

import difflib
import json
import re
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


def _extract_missing_object(error_text: str) -> tuple[str | None, str | None]:
    table_match = re.search(r"no such table:\s*([^\s]+)", error_text, flags=re.IGNORECASE)
    col_match = re.search(r"no such column:\s*([^\s]+)", error_text, flags=re.IGNORECASE)
    missing_table = table_match.group(1).strip("'\"`[]") if table_match else None
    missing_column = col_match.group(1).strip("'\"`[]") if col_match else None
    if missing_column and "." in missing_column:
        missing_column = missing_column.split(".")[-1]
    return missing_table, missing_column


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _list_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    safe = table_name.replace('"', '""')
    rows = conn.execute(f'PRAGMA table_info("{safe}")').fetchall()
    return [str(r[1]) for r in rows if len(r) > 1 and r[1]]


def _suggest(target: str, candidates: list[str], limit: int = 5) -> list[str]:
    if not target or not candidates:
        return []
    variants = {target}
    if target.endswith("s") and len(target) > 1:
        variants.add(target[:-1])
    variants.add(target + "s")
    out: list[str] = []
    for v in variants:
        for m in difflib.get_close_matches(v, candidates, n=limit, cutoff=0.35):
            if m not in out:
                out.append(m)
    return out[:limit]


def _build_nocase_variant(sql: str) -> str | None:
    if re.search(r"\bcollate\s+nocase\b", sql, flags=re.IGNORECASE):
        return None
    if not re.search(r"=\s*'[^']*'", sql):
        return None
    # Apply case-insensitive equality for string literals.
    variant = re.sub(
        r"=\s*'([^']*)'",
        lambda m: f"= '{m.group(1)}' COLLATE NOCASE",
        sql,
    )
    if variant == sql:
        return None
    return variant


def _build_error_assist(conn: sqlite3.Connection, sql: str, error_text: str) -> dict[str, Any]:
    tables = _list_tables(conn)
    missing_table, missing_column = _extract_missing_object(error_text)
    payload: dict[str, Any] = {
        "attempted_sql": sql,
        "available_tables": tables[:30],
    }

    if missing_table:
        payload["missing_table"] = missing_table
        table_suggestions = _suggest(missing_table, tables)
        payload["table_suggestions"] = table_suggestions
        if table_suggestions:
            payload["suggested_recovery_sql"] = [
                f'SELECT * FROM "{table_suggestions[0]}" LIMIT 5;',
                "SELECT name FROM sqlite_master WHERE type='table';",
            ]

    if missing_column:
        payload["missing_column"] = missing_column
        all_columns: list[str] = []
        col_to_tables: dict[str, list[str]] = {}
        for table in tables:
            cols = _list_columns(conn, table)
            for col in cols:
                all_columns.append(col)
                col_to_tables.setdefault(col, []).append(table)
        col_suggestions = _suggest(missing_column, all_columns)
        payload["column_suggestions"] = col_suggestions
        payload["column_candidate_tables"] = {
            c: col_to_tables.get(c, [])[:8] for c in col_suggestions
        }

    return payload


@_op
def _execute_sql_impl(sql: str, db_path: str, preview_rows: int = 5) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {"ok": False, "error": f"DB not found: {db_path}"}
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(path.as_posix())
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        executed_sql = sql

        # fix-0302: automatic case-insensitive retry for zero-row string equality filters.
        auto_recovered = False
        auto_recovery_sql = None
        if len(rows) == 0:
            nocase_sql = _build_nocase_variant(sql)
            if nocase_sql:
                try:
                    cur2 = conn.cursor()
                    cur2.execute(nocase_sql)
                    rows2 = cur2.fetchall()
                    if rows2:
                        rows = rows2
                        cols = [d[0] for d in (cur2.description or cols)]
                        executed_sql = nocase_sql
                        auto_recovered = True
                        auto_recovery_sql = nocase_sql
                except Exception:
                    pass

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
            "executed_sql": executed_sql,
            "auto_recovered": auto_recovered,
            "auto_recovery_sql": auto_recovery_sql,
        }
    except Exception as exc:
        payload = {"ok": False, "error": str(exc), "attempted_sql": sql}
        if conn is not None:
            try:
                payload.update(_build_error_assist(conn, sql=sql, error_text=str(exc)))
            except Exception:
                pass
        return payload
    finally:
        if conn is not None:
            conn.close()


def create_execute_sql_tool(db_path: str):
    """Create a SQL tool bound to a specific SQLite database path."""

    @tool("execute_sql", args_schema=SQLToolInput)
    def execute_sql(sql: str, preview_rows: int = 5) -> str:
        """Execute SQL against the active SQLite DB and return JSON."""
        result = _execute_sql_impl(sql=sql, db_path=db_path, preview_rows=preview_rows)
        return json.dumps(result)

    return execute_sql
