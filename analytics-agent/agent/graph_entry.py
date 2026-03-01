from __future__ import annotations

import os

from dotenv import load_dotenv

from .agent import build_phase1_graph, resolve_default_db_path
from .phase0_react_agent import _build_agent


def _load_env() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    agent_root = os.path.dirname(here)
    repo_root = os.path.dirname(agent_root)
    local_env = os.path.join(agent_root, ".env")
    root_env = os.path.join(repo_root, ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env)
    if os.path.exists(root_env):
        load_dotenv(root_env, override=False)


def _resolve_db_path() -> str:
    explicit = os.environ.get("PHASE0_DB_PATH")
    if explicit:
        return explicit
    # May not exist in early setup; that's acceptable for compile-time graph loading.
    return os.path.join(
        "analytics-agent",
        "data",
        "spider",
        "database",
        "concert_singer",
        "concert_singer.sqlite",
    )


_load_env()
phase0_graph, _RUNTIME = _build_agent(
    model_name=os.environ.get("MISTRAL_MODEL", "mistral-small-latest"),
    db_path=_resolve_db_path(),
)

phase1_graph, _PHASE1_RUNTIME = build_phase1_graph(
    model_name=os.environ.get("MISTRAL_MODEL", "mistral-small-latest"),
    db_path=resolve_default_db_path(),
)
