from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
        return {"call_id": None, "trace_id": None}
    return {
        "call_id": getattr(call_obj, "id", None),
        "trace_id": getattr(call_obj, "trace_id", None) or getattr(call_obj, "traceId", None),
        "parent_id": getattr(call_obj, "parent_id", None) or getattr(call_obj, "parentId", None),
        "op_name": getattr(call_obj, "op_name", None) or getattr(call_obj, "display_name", None),
        "started_at": getattr(call_obj, "started_at", None),
        "ended_at": getattr(call_obj, "ended_at", None),
    }


@dataclass
class ObservabilitySession:
    run: Any
    out_dir: Path
    predictions_path: Path
    traces_path: Path | None
    notebooks_path: Path | None
    mapping_path: Path
    mode: str
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
) -> ObservabilitySession:
    run = wandb.init(
        project=project,
        entity=entity,
        name=run_name,
        group=group,
        tags=tags or ["phase1", "observability"],
        config=config or {},
        reinit="finish_previous",
    )

    out_path = Path(out_dir) / run.id
    out_path.mkdir(parents=True, exist_ok=True)
    traces_path = out_path / "trace_metadata.jsonl" if mode == "full" else None
    notebooks_path = out_path / "notebooks.jsonl" if mode == "full" else None
    return ObservabilitySession(
        run=run,
        out_dir=out_path,
        predictions_path=out_path / "predictions.jsonl",
        traces_path=traces_path,
        notebooks_path=notebooks_path,
        mapping_path=out_path / "trace_index.jsonl",
        mode=mode,
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

    pred_row = {
        "question_id": question_id,
        "question": question,
        "db_id": db_id,
        "expected_value": expected_value,
        "answer_value": output.get("answer_value"),
        "answer_text": output.get("answer_text"),
        "sql": output.get("sql"),
        "notebook_cells": output.get("notebook_cells"),
        "correct": correct,
        "metrics": metrics,
        "trace_id": trace_meta.get("trace_id"),
        "call_id": trace_meta.get("call_id"),
        "wandb_run_id": session.run.id,
        "prompt_version": prompt_version,
        "agent_version": agent_version,
    }
    if extra:
        pred_row["extra"] = extra
    _append_jsonl(session.predictions_path, pred_row)

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
            "question_id": question_id,
            "notebook": output.get("notebook", []),
        }
        _append_jsonl(session.notebooks_path, notebook_row)

    mapping_row = {
        "question_id": question_id,
        "question": question,
        "db_id": db_id,
        "expected_value": expected_value,
        "answer_value": output.get("answer_value"),
        "correct": correct,
        "wandb_run_id": session.run.id,
        "trace_id": trace_meta.get("trace_id"),
        "call_id": trace_meta.get("call_id"),
        "prompt_version": prompt_version,
        "agent_version": agent_version,
        "model_name": output.get("model_name"),
    }
    if extra:
        mapping_row["extra"] = extra
    _append_jsonl(session.mapping_path, mapping_row)

    log_payload = {
        "step": session.step,
        "question_id": question_id,
        "exec_accuracy": correct,
        "sql_error_rate": metrics.get("sql_error_rate"),
        "python_error_rate": metrics.get("python_error_rate"),
        "tool_calls_count": metrics.get("tool_calls_count"),
        "cells_generated": metrics.get("cells_generated"),
        "retry_count": metrics.get("retry_count"),
        "latency_ms": metrics.get("latency_ms"),
    }
    if db_id is not None:
        log_payload["db_id"] = db_id
    if trace_meta.get("trace_id"):
        log_payload["trace_id"] = trace_meta.get("trace_id")
    session.run.log(log_payload)
    session.step += 1
    return pred_row


def finish_observability_session(session: ObservabilitySession) -> str:
    artifact = wandb.Artifact(
        name=f"phase1-observability-{session.run.id}",
        type="analysis",
    )
    artifact.add_file(str(session.predictions_path))
    if session.traces_path is not None:
        artifact.add_file(str(session.traces_path))
    if session.notebooks_path is not None:
        artifact.add_file(str(session.notebooks_path))
    artifact.add_file(str(session.mapping_path))
    session.run.log_artifact(artifact)
    run_url = session.run.url
    session.run.finish()
    return run_url


def load_env_defaults() -> tuple[str, str | None]:
    project = os.environ.get("WANDB_PROJECT", "jupybot")
    entity = os.environ.get("WANDB_ENTITY", "shukla-vivek1993-startup")
    return project, entity
