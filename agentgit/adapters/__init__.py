"""Framework adapters — auto-detect and wrap agent callables."""

from __future__ import annotations

from agentgit.adapters.anthropic_adapter import AnthropicAdapter
from agentgit.adapters.base import BaseAdapter
from agentgit.adapters.generic_adapter import GenericAdapter
from agentgit.adapters.openai_adapter import OpenAIAdapter

__all__ = [
    "BaseAdapter",
    "GenericAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "detect_framework",
    "get_adapter",
]


def detect_framework(obj: object) -> str:
    """Detect which AI framework *obj* belongs to.

    Returns one of ``"openai"``, ``"anthropic"``, ``"langchain"``, ``"generic"``.
    """
    module = getattr(type(obj), "__module__", "") or ""

    if "openai" in module:
        return "openai"
    if "anthropic" in module:
        return "anthropic"
    if "langchain" in module:
        return "langchain"
    return "generic"


def get_adapter(framework: str) -> BaseAdapter:
    """Return an adapter instance for the given framework name."""
    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "generic": GenericAdapter,
    }
    cls = adapters.get(framework, GenericAdapter)
    return cls()
