"""Shared helpers for LLM agents: structured JSON invocation."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort parse of JSON from an LLM response (handles code fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("Could not parse JSON from LLM output: %.200s", text)
    return {}


def run_agent(system: str, prompt: str) -> dict[str, Any]:
    """Invoke the configured LLM with a system+user prompt and parse JSON output."""
    llm = get_llm()
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=prompt + "\n\nRespond with ONLY valid JSON."),
    ]
    try:
        response = llm.invoke(messages)
        return _extract_json(response.content if hasattr(response, "content") else str(response))
    except Exception as exc:  # noqa: BLE001 — never let one agent crash the graph
        logger.exception("Agent LLM call failed")
        return {"_error": str(exc)}
