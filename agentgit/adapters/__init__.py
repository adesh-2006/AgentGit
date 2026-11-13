"""Framework adapters — auto-detect and wrap agent callables."""

from __future__ import annotations

from agentgit.adapters.anthropic_adapter import AnthropicAdapter
from agentgit.adapters.base import BaseAdapter
from agentgit.adapters.crewai_adapter import CrewAIAdapter
from agentgit.adapters.generic_adapter import GenericAdapter
from agentgit.adapters.langchain_adapter import LangChainAdapter
from agentgit.adapters.openai_adapter import OpenAIAdapter

__all__ = [
    "BaseAdapter",
    "GenericAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "LangChainAdapter",
    "CrewAIAdapter",
    "detect_framework",
    "get_adapter",
]


def detect_framework(obj: object) -> str:
    """Detect which AI framework *obj* belongs to.

    Returns one of ``"openai"``, ``"anthropic"``, ``"langchain"``, ``"crewai"``, ``"generic"``.
    """
    module = getattr(type(obj), "__module__", "") or ""

    if "openai" in module:
        return "openai"
    if "anthropic" in module:
        return "anthropic"
    if "langchain" in module or "langgraph" in module:
        return "langchain"
    if "crewai" in module:
        return "crewai"
    return "generic"


def get_adapter(framework: str) -> BaseAdapter:
    """Return an adapter instance for the given framework name."""
    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "langchain": LangChainAdapter,
        "crewai": CrewAIAdapter,
        "generic": GenericAdapter,
    }
    cls = adapters.get(framework, GenericAdapter)
    return cls()
