from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .notebook import NotebookAccumulator
from .prompt import SYSTEM_PROMPT
from .tools import build_tools

try:
    import weave
except ImportError:  # pragma: no cover
    weave = None


def _op(fn):
    if weave is None:
        return fn
    return weave.op()(fn)


def load_env() -> None:
    here = Path(__file__).resolve()
    agent_dir = here.parent
    project_dir = agent_dir.parent
    repo_root = project_dir.parent

    local_env = project_dir / ".env"
    root_env = repo_root / ".env"

    if local_env.exists():
        load_dotenv(local_env)
    if root_env.exists():
        load_dotenv(root_env, override=False)


def resolve_default_db_path() -> str:
    # Highest priority: explicit per-run env.
    explicit = os.environ.get("DB_PATH")
    if explicit:
        return explicit

    # Next: SPIDER_ROOT.
    spider_root = os.environ.get("SPIDER_ROOT")
    if spider_root:
        return str(Path(spider_root) / "database" / "concert_singer" / "concert_singer.sqlite")

    # Local project path.
    candidate = (
        Path("analytics-agent")
        / "data"
        / "spider"
        / "database"
        / "concert_singer"
        / "concert_singer.sqlite"
    )
    if candidate.exists():
        return candidate.as_posix()

    # Windows-safe fallback used during setup.
    fallback = Path(r"C:\spider_data\spider_data\database\concert_singer\concert_singer.sqlite")
    return fallback.as_posix()


def _extract_answer_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        output = result.get("output")
        if isinstance(output, str):
            return output
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                content = last.get("content")
                if isinstance(content, str):
                    return content
            content = getattr(last, "content", None)
            if isinstance(content, str):
                return content
    return str(result)


def _parse_json_block(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except Exception:
            return {}
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except Exception:
            return {}
    return {}


def _msg_type(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("type") or msg.get("role") or "")
    msg_type = getattr(msg, "type", None)
    if msg_type:
        return str(msg_type)
    role = getattr(msg, "role", None)
    return str(role or "")


def _msg_content(msg: Any) -> Any:
    if isinstance(msg, dict):
        return msg.get("content")
    return getattr(msg, "content", None)


def _tool_calls_from_ai(msg: Any) -> list[dict[str, Any]]:
    calls = []
    raw_calls = []
    if isinstance(msg, dict):
        raw_calls = msg.get("tool_calls") or []
    else:
        raw_calls = getattr(msg, "tool_calls", None) or []

    for call in raw_calls:
        if isinstance(call, dict):
            call_id = call.get("id") or call.get("tool_call_id")
            name = call.get("name")
            args = call.get("args")
            if name is None and isinstance(call.get("function"), dict):
                fn = call["function"]
                name = fn.get("name")
                args = fn.get("arguments")
        else:
            call_id = getattr(call, "id", None) or getattr(call, "tool_call_id", None)
            name = getattr(call, "name", None)
            args = getattr(call, "args", None)
            fn = getattr(call, "function", None)
            if name is None and fn is not None:
                name = getattr(fn, "name", None)
                args = getattr(fn, "arguments", args)

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if not isinstance(args, dict):
            args = {}

        calls.append(
            {
                "id": call_id,
                "name": name or "unknown_tool",
                "args": args,
            }
        )
    return calls


def notebook_from_messages(messages: list[Any]) -> NotebookAccumulator:
    notebook = NotebookAccumulator()
    pending: dict[str, dict[str, Any]] = {}

    for msg in messages:
        msg_type = _msg_type(msg)
        if msg_type in ("ai", "assistant"):
            for tc in _tool_calls_from_ai(msg):
                if tc["id"]:
                    pending[tc["id"]] = tc
        elif msg_type == "tool":
            if isinstance(msg, dict):
                tcid = msg.get("tool_call_id")
            else:
                tcid = getattr(msg, "tool_call_id", None)
            if not tcid:
                continue
            call = pending.pop(tcid, None)
            if not call:
                continue
            notebook.add_tool(call["name"], call["args"], _msg_content(msg))

    return notebook


def _metrics_from_notebook(notebook: NotebookAccumulator, latency_ms: int) -> dict[str, Any]:
    sql_cells = [c for c in notebook.cells if c.get("cell_type") == "sql"]
    py_cells = [c for c in notebook.cells if c.get("cell_type") == "python"]
    tool_calls = len([c for c in notebook.cells if c.get("cell_type") in ("sql", "python", "tool")])

    sql_errors = 0
    py_errors = 0
    for c in sql_cells:
        out = c.get("output")
        if isinstance(out, dict) and out.get("ok") is False:
            sql_errors += 1
    for c in py_cells:
        out = c.get("output")
        if isinstance(out, dict) and out.get("ok") is False:
            py_errors += 1

    return {
        "exec_accuracy": None,
        "sql_error_rate": (sql_errors / len(sql_cells)) if sql_cells else 0.0,
        "python_error_rate": (py_errors / len(py_cells)) if py_cells else 0.0,
        "tool_calls_count": tool_calls,
        "cells_generated": len(notebook),
        "retry_count": sql_errors + py_errors,
        "latency_ms": latency_ms,
    }


def _is_scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _scalar_from_any(v: Any) -> Any:
    if _is_scalar(v):
        return v
    if isinstance(v, (list, tuple)):
        if not v:
            return None
        return _scalar_from_any(v[0])
    if isinstance(v, dict):
        if not v:
            return None
        for key in ("answer_value", "value", "result"):
            if key in v:
                return _scalar_from_any(v[key])
        first_val = next(iter(v.values()))
        return _scalar_from_any(first_val)
    return None


def _scalar_from_sql_preview(notebook: NotebookAccumulator) -> Any:
    for cell in reversed(notebook.cells):
        if cell.get("cell_type") != "sql":
            continue
        out = cell.get("output")
        if not isinstance(out, dict) or out.get("ok") is not True:
            continue
        preview = out.get("preview_rows")
        value = _scalar_from_any(preview)
        if _is_scalar(value):
            return value
    return None


def _normalize_answer_value(raw_answer_value: Any, notebook: NotebookAccumulator) -> Any:
    # fix-0201: normalize non-scalar model outputs to scorer-compatible scalar.
    direct = _scalar_from_any(raw_answer_value)
    if _is_scalar(direct):
        return direct
    preview_value = _scalar_from_sql_preview(notebook)
    if _is_scalar(preview_value):
        return preview_value
    return raw_answer_value


def _looks_numeric_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    try:
        float(text)
        return True
    except Exception:
        return False


def _ground_answer_value(raw_answer_value: Any, notebook: NotebookAccumulator) -> Any:
    """
    fix-0204: prefer SQL-grounded scalar value when model emits narrative strings.
    """
    preview_value = _scalar_from_sql_preview(notebook)
    normalized = _normalize_answer_value(raw_answer_value, notebook)

    # If model returned None but we have a grounded SQL value, use grounded value.
    if normalized is None and _is_scalar(preview_value):
        return preview_value

    # If model returned a non-numeric free-form string, prefer grounded SQL cell.
    if isinstance(normalized, str) and not _looks_numeric_text(normalized):
        if _is_scalar(preview_value) and preview_value is not None:
            return preview_value

    return normalized


def build_phase1_graph(model_name: str, db_path: str):
    load_env()
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY missing.")

    from langchain_mistralai import ChatMistralAI

    llm = ChatMistralAI(model=model_name, api_key=api_key, temperature=0)
    tools = build_tools(db_path)

    try:
        from langchain.agents import create_agent

        graph = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)
        return graph, "langchain.create_agent"
    except Exception:
        from langgraph.prebuilt import create_react_agent

        graph = create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
        return graph, "langgraph.prebuilt.create_react_agent"


@_op
def run_analytics_agent(
    question: str,
    db_path: str | None = None,
    model_name: str = "mistral-small-latest",
) -> dict[str, Any]:
    started = time.perf_counter()
    db_path = db_path or resolve_default_db_path()
    graph, runtime = build_phase1_graph(model_name=model_name, db_path=db_path)

    result = graph.invoke({"messages": [{"role": "user", "content": question}]})
    final_text = _extract_answer_text(result)
    parsed = _parse_json_block(final_text)

    messages = result.get("messages") if isinstance(result, dict) else []
    notebook = notebook_from_messages(messages if isinstance(messages, list) else [])
    raw_answer_value = parsed.get("answer_value")
    answer_value = _ground_answer_value(raw_answer_value, notebook)

    final_sql = parsed.get("sql")
    if not final_sql:
        sql_cells = [c for c in notebook.cells if c.get("cell_type") == "sql"]
        final_sql = sql_cells[-1]["code"] if sql_cells else None

    latency_ms = int((time.perf_counter() - started) * 1000)
    metrics = _metrics_from_notebook(notebook, latency_ms=latency_ms)

    return {
        "runtime": runtime,
        "model_name": model_name,
        "db_path": db_path,
        "answer_value": answer_value,
        "answer_value_raw": raw_answer_value,
        "answer_value_was_normalized": answer_value != raw_answer_value,
        "answer_text": parsed.get("answer_text", final_text),
        "sql": final_sql,
        "notebook_cells": parsed.get("notebook_cells", len(notebook)),
        "notebook": notebook.to_list(),
        "metrics": metrics,
        "raw_final_content": final_text,
    }
