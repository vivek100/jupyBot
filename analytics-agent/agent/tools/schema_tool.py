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


class SchemaToolInput(BaseModel):
    table_name: str | None = Field(
        default=None,
        description="Optional table name to describe. If omitted, describes all tables.",
    )
    include_foreign_keys: bool = Field(
        default=True,
        description="Whether to include foreign key relationships.",
    )


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    safe = table.replace('"', '""')
    rows = conn.execute(f'PRAGMA table_info("{safe}")').fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "cid": int(r[0]),
                "name": str(r[1]),
                "type": str(r[2] or ""),
                "notnull": bool(r[3]),
                "default": r[4],
                "pk": bool(r[5]),
            }
        )
    return out


def _table_foreign_keys(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    safe = table.replace('"', '""')
    rows = conn.execute(f'PRAGMA foreign_key_list("{safe}")').fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r[0]),
                "seq": int(r[1]),
                "ref_table": str(r[2]),
                "from_col": str(r[3]),
                "to_col": str(r[4]),
            }
        )
    return out


@_op
def _describe_schema_impl(
    db_path: str,
    table_name: str | None = None,
    include_foreign_keys: bool = True,
) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {"ok": False, "error": f"DB not found: {db_path}"}

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(path.as_posix())
        all_tables = _list_tables(conn)
        if table_name:
            tables = [t for t in all_tables if t.lower() == table_name.lower()]
            if not tables:
                return {
                    "ok": False,
                    "error": f"Table not found: {table_name}",
                    "available_tables": all_tables,
                }
        else:
            tables = all_tables

        schema_tables: list[dict[str, Any]] = []
        for t in tables:
            row = {
                "table": t,
                "columns": _table_columns(conn, t),
            }
            if include_foreign_keys:
                row["foreign_keys"] = _table_foreign_keys(conn, t)
            schema_tables.append(row)

        return {
            "ok": True,
            "table_count": len(schema_tables),
            "tables": schema_tables,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if conn is not None:
            conn.close()


def create_describe_schema_tool(db_path: str):
    @tool("describe_schema", args_schema=SchemaToolInput)
    def describe_schema(table_name: str | None = None, include_foreign_keys: bool = True) -> str:
        """Describe SQLite schema (tables, columns, foreign keys) as JSON."""
        result = _describe_schema_impl(
            db_path=db_path,
            table_name=table_name,
            include_foreign_keys=include_foreign_keys,
        )
        return json.dumps(result)

    return describe_schema

