from __future__ import annotations

import json
import subprocess
import sys
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


class PythonToolInput(BaseModel):
    code: str = Field(description="Python code to execute")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-serializable context variables available to the cell",
    )


def _runner_script() -> str:
    return """
import io
import json
import traceback
from contextlib import redirect_stdout

import numpy as np
import pandas as pd

def decode_context(v):
    if isinstance(v, dict) and v.get("__type__") == "dataframe":
        return pd.DataFrame(v.get("records", []), columns=v.get("columns"))
    return v

def encode_value(v):
    if isinstance(v, pd.DataFrame):
        return {
            "__type__": "dataframe",
            "columns": list(v.columns),
            "records": v.head(200).to_dict(orient="records"),
            "row_count": int(len(v)),
        }
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [encode_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): encode_value(x) for k, x in v.items()}
    return repr(v)

payload = json.loads(input())
code = payload.get("code", "")
context = payload.get("context", {})
scope = {"pd": pd, "np": np}
for k, v in context.items():
    scope[k] = decode_context(v)

buf = io.StringIO()
try:
    with redirect_stdout(buf):
        exec(code, scope, scope)
    result = scope.get("result", scope.get("RESULT"))
    next_context = {}
    for k, v in scope.items():
        if k.startswith("__"):
            continue
        if k in ("pd", "np", "io", "json", "traceback", "redirect_stdout"):
            continue
        if callable(v):
            continue
        next_context[k] = encode_value(v)
    print(json.dumps({
        "ok": True,
        "stdout": buf.getvalue(),
        "result": encode_value(result),
        "context": next_context
    }))
except Exception as exc:
    print(json.dumps({
        "ok": False,
        "stdout": buf.getvalue(),
        "error": str(exc),
        "traceback": traceback.format_exc()
    }))
"""


@_op
def _run_python_impl(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _runner_script()],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        try:
            parsed = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "invalid python tool output",
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        return parsed
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def create_run_python_tool():
    @tool("run_python", args_schema=PythonToolInput)
    def run_python(code: str, context: dict[str, Any] | None = None) -> str:
        """Execute Python code in a sandboxed subprocess and return JSON."""
        payload = {"code": code, "context": context or {}}
        result = _run_python_impl(payload)
        return json.dumps(result)

    return run_python


# Backward-compatible alias used by existing imports/tests.
run_python = create_run_python_tool()


@tool("run_python_simple")
def run_python_simple(code: str) -> str:
    """Execute Python code with no context. Phase 0 compatibility helper."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            return json.dumps(
                {
                    "ok": False,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                }
            )
        return json.dumps({"ok": True, "stdout": proc.stdout.strip()})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
