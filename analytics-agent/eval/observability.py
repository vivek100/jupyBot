from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import wandb


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (list, tuple, dict, set)):
        return len(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _truncate_text(value: Any, limit: int = 400) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _get_attr_or_key(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _table_cell_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


def _table_from_dict_rows(rows: list[dict[str, Any]]) -> wandb.Table:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                columns.append(key)
                seen.add(key)

    # W&B tables infer strict per-column types; mixed primitive types in a column
    # (e.g., number + string across rows) can fail at add_data time.
    col_types: dict[str, set[str]] = {c: set() for c in columns}
    for row in rows:
        for col in columns:
            val = row.get(col)
            if val is None:
                continue
            if isinstance(val, bool):
                col_types[col].add("bool")
            elif isinstance(val, (int, float)):
                col_types[col].add("number")
            elif isinstance(val, str):
                col_types[col].add("string")
            else:
                col_types[col].add("other")

    force_string_cols = {c for c, t in col_types.items() if len(t) > 1 or "other" in t}
    data = []
    for row in rows:
        out_row = []
        for col in columns:
            val = row.get(col)
            if col in force_string_cols and val is not None:
                out_row.append(str(val))
            else:
                out_row.append(_table_cell_value(val))
        data.append(out_row)
    return wandb.Table(columns=columns, data=data)


def _extract_trace_status(call_obj: Any | None) -> str | None:
    if call_obj is None:
        return None
    direct = _get_attr_or_key(call_obj, "status")
    if direct:
        return str(direct)
    summary = _get_attr_or_key(call_obj, "summary")
    if isinstance(summary, dict):
        weave_summary = summary.get("weave")
        if isinstance(weave_summary, dict):
            status = weave_summary.get("status")
            if status:
                return str(status)
    return None


def _extract_trace_latency_ms(call_obj: Any | None) -> int | None:
    if call_obj is None:
        return None
    direct = _get_attr_or_key(call_obj, "latency_ms")
    if isinstance(direct, (int, float)):
        return int(direct)
    summary = _get_attr_or_key(call_obj, "summary")
    if isinstance(summary, dict):
        weave_summary = summary.get("weave")
        if isinstance(weave_summary, dict):
            latency = weave_summary.get("latency_ms")
            if isinstance(latency, (int, float)):
                return int(latency)
    return None


def score_answer_value(answer_value: Any, expected_value: Any) -> bool | None:
    if expected_value is None:
        return None
    got = _to_float(answer_value)
    exp = _to_float(expected_value)
    if got is not None and exp is not None:
        return round(got, 2) == round(exp, 2)
    if answer_value is None:
        return False
    return str(answer_value).strip() == str(expected_value).strip()


def extract_trace_metadata(call_obj: Any | None) -> dict[str, Any]:
    if call_obj is None:
        return {
            "call_id": None,
            "trace_id": None,
            "parent_id": None,
            "op_name": None,
            "status": None,
            "exception": None,
            "started_at": None,
            "ended_at": None,
            "latency_ms": None,
        }
    return {
        "call_id": _get_attr_or_key(call_obj, "id", "call_id"),
        "trace_id": _get_attr_or_key(call_obj, "trace_id", "traceId"),
        "parent_id": _get_attr_or_key(call_obj, "parent_id", "parentId"),
        "op_name": _get_attr_or_key(call_obj, "op_name", "display_name", "displayName"),
        "status": _extract_trace_status(call_obj),
        "exception": _get_attr_or_key(call_obj, "exception"),
        "started_at": _get_attr_or_key(call_obj, "started_at", "startedAt"),
        "ended_at": _get_attr_or_key(call_obj, "ended_at", "endedAt"),
        "latency_ms": _extract_trace_latency_ms(call_obj),
    }


@dataclass
class ObservabilitySession:
    run: Any
    out_dir: Path
    predictions_path: Path
    failures_path: Path
    traces_path: Path | None
    notebooks_path: Path | None
    mapping_path: Path
    mode: str
    phase: str
    group: str
    prompt_version: str | None
    agent_version: str | None
    model_name: str | None
    table_max_rows: int
    text_truncate_length: int
    questions_total: int = 0
    questions_correct: int = 0
    running_latency_total_ms: int = 0
    prediction_preview_rows: list[dict[str, Any]] | None = None
    failure_preview_rows: list[dict[str, Any]] | None = None
    step: int = 0


def start_observability_session(
    run_name: str,
    project: str,
    entity: str | None,
    out_dir: str | Path = "analytics-agent/outputs/observability",
    group: str = "phase1-observability",
    tags: list[str] | None = None,
    config: dict[str, Any] | None = None,
    mode: str = "lean",
    phase: str = "phase1",
    capture_notebooks: bool = False,
    table_max_rows: int = 200,
    text_truncate_length: int = 400,
) -> ObservabilitySession:
    config_payload = dict(config or {})
    config_payload.setdefault("phase", phase)
    run = wandb.init(
        project=project,
        entity=entity,
        name=run_name,
        group=group,
        tags=tags or ["phase1", "observability"],
        config=config_payload,
        reinit="finish_previous",
    )

    out_path = Path(out_dir) / run.id
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "failures.jsonl").touch(exist_ok=True)
    traces_path = out_path / "trace_metadata.jsonl" if mode == "full" else None
    notebooks_path = out_path / "notebooks.jsonl" if (mode == "full" or capture_notebooks) else None
    return ObservabilitySession(
        run=run,
        out_dir=out_path,
        predictions_path=out_path / "predictions.jsonl",
        failures_path=out_path / "failures.jsonl",
        traces_path=traces_path,
        notebooks_path=notebooks_path,
        mapping_path=out_path / "trace_index.jsonl",
        mode=mode,
        phase=phase,
        group=group,
        prompt_version=config_payload.get("prompt_version"),
        agent_version=config_payload.get("agent_version"),
        model_name=config_payload.get("model"),
        table_max_rows=max(1, int(table_max_rows)),
        text_truncate_length=max(80, int(text_truncate_length)),
        prediction_preview_rows=[],
        failure_preview_rows=[],
    )


def log_question_result(
    session: ObservabilitySession,
    question_id: str,
    question: str,
    output: dict[str, Any],
    trace_meta: dict[str, Any],
    expected_value: Any | None = None,
    db_id: str | None = None,
    prompt_version: str | None = None,
    agent_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = output.get("metrics", {}) if isinstance(output, dict) else {}
    correct = score_answer_value(output.get("answer_value"), expected_value)
    resolved_prompt_version = prompt_version or session.prompt_version
    resolved_agent_version = agent_version or session.agent_version
    resolved_model_name = output.get("model_name") or session.model_name
    trace_status = trace_meta.get("status")
    if not trace_status:
        trace_status = "error" if trace_meta.get("exception") else "success"
    now_iso = datetime.utcnow().isoformat() + "Z"

    pred_row = {
        "logged_at": now_iso,
        "step": session.step,
        "phase": session.phase,
        "group": session.group,
        "wandb_run_name": session.run.name,
        "wandb_run_url": session.run.url,
        "question_id": question_id,
        "question": _truncate_text(question, session.text_truncate_length),
        "db_id": db_id,
        "expected_value": expected_value,
        "answer_value": output.get("answer_value"),
        "answer_text": _truncate_text(output.get("answer_text"), session.text_truncate_length),
        "sql": _truncate_text(output.get("sql"), session.text_truncate_length),
        "notebook_cells": _coerce_int(output.get("notebook_cells"), default=0),
        "correct": correct,
        "status": trace_status,
        "exec_accuracy": correct,
        "sql_error_rate": metrics.get("sql_error_rate"),
        "python_error_rate": metrics.get("python_error_rate"),
        "tool_calls_count": metrics.get("tool_calls_count"),
        "cells_generated": metrics.get("cells_generated"),
        "retry_count": metrics.get("retry_count"),
        "latency_ms": metrics.get("latency_ms"),
        "trace_latency_ms": trace_meta.get("latency_ms"),
        "trace_started_at": trace_meta.get("started_at"),
        "trace_ended_at": trace_meta.get("ended_at"),
        "trace_op_name": trace_meta.get("op_name"),
        "trace_exception": _truncate_text(trace_meta.get("exception"), 240),
        "metrics": metrics,
        "trace_id": trace_meta.get("trace_id"),
        "call_id": trace_meta.get("call_id"),
        "parent_id": trace_meta.get("parent_id"),
        "wandb_run_id": session.run.id,
        "prompt_version": resolved_prompt_version,
        "agent_version": resolved_agent_version,
        "model_name": resolved_model_name,
    }
    if extra:
        pred_row["extra"] = extra
    _append_jsonl(session.predictions_path, pred_row)
    if correct is not True:
        _append_jsonl(session.failures_path, pred_row)

    if session.traces_path is not None:
        trace_row = {
            "question_id": question_id,
            "question": question,
            "db_id": db_id,
            **trace_meta,
        }
        _append_jsonl(session.traces_path, trace_row)

    if session.notebooks_path is not None:
        notebook_row = {
            "step": session.step,
            "question_id": question_id,
            "db_id": db_id,
            "notebook": output.get("notebook", []),
        }
        _append_jsonl(session.notebooks_path, notebook_row)

    mapping_row = {
        "logged_at": now_iso,
        "step": session.step,
        "phase": session.phase,
        "group": session.group,
        "question_id": question_id,
        "question": question,
        "db_id": db_id,
        "expected_value": expected_value,
        "answer_value": output.get("answer_value"),
        "correct": correct,
        "status": trace_status,
        "wandb_run_id": session.run.id,
        "wandb_run_name": session.run.name,
        "wandb_run_url": session.run.url,
        "trace_id": trace_meta.get("trace_id"),
        "call_id": trace_meta.get("call_id"),
        "parent_id": trace_meta.get("parent_id"),
        "op_name": trace_meta.get("op_name"),
        "trace_started_at": trace_meta.get("started_at"),
        "trace_ended_at": trace_meta.get("ended_at"),
        "trace_latency_ms": trace_meta.get("latency_ms"),
        "trace_exception": _truncate_text(trace_meta.get("exception"), 240),
        "prompt_version": resolved_prompt_version,
        "agent_version": resolved_agent_version,
        "model_name": resolved_model_name,
    }
    if extra:
        mapping_row["extra"] = extra
    _append_jsonl(session.mapping_path, mapping_row)

    next_questions_total = session.questions_total + 1
    next_questions_correct = session.questions_correct + (1 if correct is True else 0)
    running_accuracy = next_questions_correct / next_questions_total if next_questions_total else 0.0

    log_payload = {
        "step": session.step,
        "question_number": next_questions_total,
        "question_id": question_id,
        "correct": 1 if correct is True else 0,
        "exec_accuracy": correct,
        "running_accuracy": running_accuracy,
        "running_accuracy_pct": round(running_accuracy * 100.0, 4),
        "sql_error_rate": metrics.get("sql_error_rate"),
        "python_error_rate": metrics.get("python_error_rate"),
        "tool_calls_count": metrics.get("tool_calls_count"),
        "cells_generated": metrics.get("cells_generated"),
        "retry_count": metrics.get("retry_count"),
        "latency_ms": metrics.get("latency_ms"),
        "trace_status": trace_status,
        "trace_latency_ms": trace_meta.get("latency_ms"),
        "model_name": resolved_model_name,
        "phase": session.phase,
        "group": session.group,
        "prompt_version": resolved_prompt_version,
        "agent_version": resolved_agent_version,
    }
    if db_id is not None:
        log_payload["db_id"] = db_id
    if trace_meta.get("trace_id"):
        log_payload["trace_id"] = trace_meta.get("trace_id")
    session.run.log(log_payload)

    session.questions_total = next_questions_total
    session.questions_correct = next_questions_correct
    latency_value = metrics.get("latency_ms")
    if isinstance(latency_value, (int, float)):
        session.running_latency_total_ms += int(latency_value)
    if session.prediction_preview_rows is not None and len(session.prediction_preview_rows) < session.table_max_rows:
        session.prediction_preview_rows.append(
            {
                "step": session.step,
                "question_id": question_id,
                "question": _truncate_text(question, 220),
                "db_id": db_id,
                "correct": correct,
                "answer_value": output.get("answer_value"),
                "expected_value": expected_value,
                "latency_ms": metrics.get("latency_ms"),
                "tool_calls_count": metrics.get("tool_calls_count"),
                "sql_error_rate": metrics.get("sql_error_rate"),
                "python_error_rate": metrics.get("python_error_rate"),
                "trace_id": trace_meta.get("trace_id"),
                "call_id": trace_meta.get("call_id"),
                "trace_status": trace_status,
                "prompt_version": resolved_prompt_version,
                "agent_version": resolved_agent_version,
                "model_name": resolved_model_name,
            }
        )
    if (
        correct is not True
        and session.failure_preview_rows is not None
        and len(session.failure_preview_rows) < session.table_max_rows
    ):
        session.failure_preview_rows.append(
            {
                "step": session.step,
                "question_id": question_id,
                "question": _truncate_text(question, 220),
                "db_id": db_id,
                "expected_value": expected_value,
                "answer_value": output.get("answer_value"),
                "answer_text": _truncate_text(output.get("answer_text"), 220),
                "sql": _truncate_text(output.get("sql"), 220),
                "trace_id": trace_meta.get("trace_id"),
                "call_id": trace_meta.get("call_id"),
                "trace_status": trace_status,
                "trace_exception": _truncate_text(trace_meta.get("exception"), 180),
                "latency_ms": metrics.get("latency_ms"),
            }
        )

    running_accuracy = session.questions_correct / session.questions_total if session.questions_total else 0.0
    mean_latency = (
        session.running_latency_total_ms / session.questions_total
        if session.questions_total
        else 0.0
    )
    session.run.summary["summary/questions_total"] = session.questions_total
    session.run.summary["summary/questions_correct"] = session.questions_correct
    session.run.summary["summary/running_accuracy"] = running_accuracy
    session.run.summary["summary/mean_latency_ms"] = round(mean_latency, 3)
    session.step += 1
    return pred_row


def finish_observability_session(session: ObservabilitySession) -> str:
    artifact = wandb.Artifact(
        name=f"phase1-observability-{session.run.id}",
        type="analysis",
    )
    artifact.add_file(str(session.predictions_path))
    artifact.add_file(str(session.failures_path))
    if session.traces_path is not None:
        artifact.add_file(str(session.traces_path))
    if session.notebooks_path is not None:
        artifact.add_file(str(session.notebooks_path))
    artifact.add_file(str(session.mapping_path))
    session.run.log_artifact(artifact)

    if session.prediction_preview_rows:
        session.run.log(
            {"dashboard/predictions_table": _table_from_dict_rows(session.prediction_preview_rows)}
        )
        session.run.summary["summary/predictions_table_rows"] = len(session.prediction_preview_rows)
    if session.failure_preview_rows:
        session.run.log(
            {"dashboard/failures_table": _table_from_dict_rows(session.failure_preview_rows)}
        )
        session.run.summary["summary/failures_table_rows"] = len(session.failure_preview_rows)

    existing_total = session.run.summary.get("questions_total")
    existing_correct = session.run.summary.get("questions_correct")
    existing_final_accuracy = session.run.summary.get("final_accuracy")

    if existing_total is None:
        session.run.summary["questions_total"] = session.questions_total
    if existing_correct is None:
        session.run.summary["questions_correct"] = session.questions_correct
    if existing_final_accuracy is None:
        session.run.summary["final_accuracy"] = (
            session.questions_correct / session.questions_total if session.questions_total else 0.0
        )

    session.run.summary["summary/phase"] = session.phase
    session.run.summary["summary/group"] = session.group
    session.run.summary["summary/prompt_version"] = session.prompt_version
    session.run.summary["summary/agent_version"] = session.agent_version
    session.run.summary["summary/model_name"] = session.model_name
    session.run.summary["summary/trace_index_path"] = session.mapping_path.as_posix()
    session.run.summary["summary/predictions_path"] = session.predictions_path.as_posix()
    session.run.summary["summary/failures_path"] = session.failures_path.as_posix()
    session.run.summary["summary/has_notebooks_artifact"] = bool(session.notebooks_path is not None)

    run_url = session.run.url
    session.run.finish()
    return run_url


def load_env_defaults() -> tuple[str, str | None]:
    project = os.environ.get("WANDB_PROJECT", "jupybot")
    entity = os.environ.get("WANDB_ENTITY", "shukla-vivek1993-startup")
    return project, entity
