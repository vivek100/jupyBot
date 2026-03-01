from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

from .tools import build_tools

try:
    import weave
except ImportError:  # pragma: no cover
    weave = None


def _op(fn):
    if weave is None:
        return fn
    return weave.op()(fn)


def _load_local_env() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    agent_root = os.path.dirname(here)
    repo_root = os.path.dirname(agent_root)
    local_env = os.path.join(agent_root, ".env")
    root_env = os.path.join(repo_root, ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env)
    if os.path.exists(root_env):
        load_dotenv(root_env, override=False)


def _extract_answer_text(result: Any) -> str:
    # LangGraph/LangChain agent invoke output shape can vary across versions.
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "output" in result and isinstance(result["output"], str):
            return result["output"]
        msgs = result.get("messages")
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            if isinstance(last, dict):
                content = last.get("content")
                if isinstance(content, str):
                    return content
            content = getattr(last, "content", None)
            if isinstance(content, str):
                return content
    return str(result)


def _build_agent(model_name: str, db_path: str):
    _load_local_env()
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY missing for Phase 0 agent.")

    from langchain_mistralai import ChatMistralAI

    llm = ChatMistralAI(
        model=model_name,
        api_key=api_key,
        temperature=0,
    )
    tools = build_tools(db_path)
    system_prompt = (
        "You are a minimal analytics ReAct agent.\n"
        "Use tools when needed.\n"
        "Return compact JSON with keys: answer_value, answer_text, sql, notebook_cells."
    )

    # Preferred path for LangGraph v1 runtime.
    try:
        from langchain.agents import create_agent

        agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
        return agent, "langchain.create_agent"
    except Exception:
        # Compatibility fallback for older stacks.
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
        return agent, "langgraph.prebuilt.create_react_agent"


@_op
def run_phase0_agent(question: str, db_path: str, model_name: str = "mistral-small-latest") -> dict[str, Any]:
    """Invoke minimal ReAct-style agent once and normalize output."""
    agent, runtime = _build_agent(model_name=model_name, db_path=db_path)
    user_msg = {"role": "user", "content": question}
    result = agent.invoke({"messages": [user_msg]})
    answer_text = _extract_answer_text(result)
    parsed = {}
    try:
        parsed = json.loads(answer_text)
    except Exception:
        parsed = {}
    return {
        "runtime": runtime,
        "raw_result_preview": str(result)[:2000],
        "answer_text": answer_text,
        "answer_value": parsed.get("answer_value"),
        "final_json": parsed,
    }
