"""LLM provider factory — switch between OpenAI, Anthropic, and Ollama.

The active provider is chosen by `LLM_PROVIDER`. All providers expose the same
LangChain `BaseChatModel` interface so the agents are provider-agnostic.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_llm(provider: str | None = None, model: str | None = None, temperature: float | None = None) -> BaseChatModel:
    provider = (provider or settings.LLM_PROVIDER).lower()
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model or settings.LLM_MODEL,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
        )
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # optional provider
            raise RuntimeError(
                "LLM_PROVIDER=anthropic requires `pip install langchain-anthropic`."
            ) from exc
        return ChatAnthropic(
            model=model or settings.ANTHROPIC_MODEL,
            temperature=temperature,
            api_key=settings.ANTHROPIC_API_KEY,
        )
    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:  # optional provider
            raise RuntimeError(
                "LLM_PROVIDER=ollama requires `pip install langchain-ollama`."
            ) from exc
        return ChatOllama(
            model=model or settings.OLLAMA_MODEL,
            temperature=temperature,
            base_url=settings.OLLAMA_BASE_URL,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")
