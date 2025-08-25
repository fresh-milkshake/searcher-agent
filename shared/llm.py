"""Shared LLM model registry for agents.

Configures multiple model backends (OpenAI, OpenRouter, Ollama-compatible) and
exposes typed model objects for use with the Agents SDK.

Environment variables:
- ``OPENAI_API_KEY``
- ``OPENROUTER_API_KEY``

:ivar AGENT_MODEL: Default chat model for text agents.
:ivar MULTIMODAL_MODEL: Default model for multimodal agents.
"""

import os
from typing import Optional, TYPE_CHECKING
from dotenv import load_dotenv

if TYPE_CHECKING:
    from agents import OpenAIChatCompletionsModel
    from openai import AsyncOpenAI

load_dotenv(override=True)

# Lazy client initialization
_openai_client: Optional["AsyncOpenAI"] = None
_ollama_client: Optional["AsyncOpenAI"] = None
_open_router: Optional["AsyncOpenAI"] = None
_agent_model: Optional["OpenAIChatCompletionsModel"] = None
_multimodal_model: Optional["OpenAIChatCompletionsModel"] = None


def _get_openai_client() -> "AsyncOpenAI":
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI

        _openai_client = AsyncOpenAI(
            base_url="https://api.openai.com/v1", api_key=os.getenv("OPENAI_API_KEY")
        )
    return _openai_client


def _get_ollama_client() -> "AsyncOpenAI":
    global _ollama_client
    if _ollama_client is None:
        from openai import AsyncOpenAI

        _ollama_client = AsyncOpenAI(
            base_url="http://localhost:11434/v1", api_key="ollama"
        )
    return _ollama_client


def _get_open_router() -> "AsyncOpenAI":
    global _open_router
    if _open_router is None:
        from openai import AsyncOpenAI

        _open_router = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _open_router


AGENT_MODEL = property(lambda self: _get_openai_client())
FALLBACK_MODEL = property(lambda self: _get_open_router())


def get_agent_model() -> "OpenAIChatCompletionsModel":
    """Get the default chat model for text agents.

    :returns: Configured OpenAIChatCompletionsModel instance.
    """
    global _agent_model
    if _agent_model is None:
        from agents import OpenAIChatCompletionsModel

        _agent_model = OpenAIChatCompletionsModel(
            model="gpt-4o-mini", openai_client=_get_openai_client()
        )
    return _agent_model


def get_fallback_model() -> "OpenAIChatCompletionsModel":
    """Get the fallback model for when primary model fails.

    :returns: Configured OpenAIChatCompletionsModel instance using OpenRouter.
    """
    from agents import OpenAIChatCompletionsModel

    return OpenAIChatCompletionsModel(
        model="deepseek/deepseek-chat-v3-0324:free", openai_client=_get_open_router()
    )
