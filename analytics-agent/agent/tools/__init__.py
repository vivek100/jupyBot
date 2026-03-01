from __future__ import annotations

from .python_tool import create_run_python_tool, run_python
from .sql_tool import create_execute_sql_tool


def build_tools(db_path: str):
    return [create_execute_sql_tool(db_path), create_run_python_tool()]
