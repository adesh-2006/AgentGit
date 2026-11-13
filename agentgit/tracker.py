"""Core tracker — wraps any callable to record behavioral data.

The ``track()`` function is framework-agnostic.  It wraps any callable —
an OpenAI chat completion call, an Anthropic message call, a LangChain
Runnable, a CrewAI crew, or a plain Python function — and silently records
every invocation's input, output, tool calls, tokens, latency, cost, and
errors.  The recorded data feeds into behavioral snapshots.

Usage::

    from agentgit import track

    # As a wrapper
    agent = track(my_function, name="support-bot")
    result = agent("What is my order status?")

    # As a decorator
    @track
    def my_agent(task: str) -> str:
        return call_llm(task)
"""

from __future__ import annotations

import functools
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    """A single tool/function call made by the agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None


class InvocationRecord(BaseModel):
    """One recorded invocation of the tracked agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input: Any = None
    output: Any = None
    tools_called: List[ToolCall] = Field(default_factory=list)
    steps: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    error: Optional[str] = None
    model: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Cost estimation (rough, used when exact cost unknown)
# ---------------------------------------------------------------------------

_MODEL_COST_PER_1K: Dict[str, tuple] = {
    # (input_cost, output_cost) per 1K tokens
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-4": (0.03, 0.06),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku": (0.0008, 0.004),
    "claude-3-opus": (0.015, 0.075),
    "gemini-2.5-pro": (0.00125, 0.01),
    "gemini-2.5-flash": (0.00015, 0.0006),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return a rough USD cost estimate for the given usage."""
    for key, (inp, out) in _MODEL_COST_PER_1K.items():
        if key in model.lower():
            return (input_tokens / 1000) * inp + (output_tokens / 1000) * out
    return 0.0


# ---------------------------------------------------------------------------
# Result extraction helpers
# ---------------------------------------------------------------------------

def _extract_openai(result: Any) -> Dict[str, Any]:
    """Extract metrics from an OpenAI ChatCompletion-like response."""
    data: Dict[str, Any] = {}
    # openai >=1.0 returns pydantic-like objects
    if hasattr(result, "usage") and result.usage is not None:
        data["input_tokens"] = getattr(result.usage, "prompt_tokens", 0) or 0
        data["output_tokens"] = getattr(result.usage, "completion_tokens", 0) or 0
        data["total_tokens"] = getattr(result.usage, "total_tokens", 0) or 0
    if hasattr(result, "model"):
        data["model"] = result.model or ""
    # Extract tool calls from first choice
    tools: List[ToolCall] = []
    if hasattr(result, "choices") and result.choices:
        msg = result.choices[0].message
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools.append(ToolCall(
                    id=tc.id or "",
                    name=tc.function.name if hasattr(tc, "function") else "",
                    arguments=tc.function.arguments if hasattr(tc, "function") else {},
                ))
    data["tools_called"] = tools
    return data


def _extract_anthropic(result: Any) -> Dict[str, Any]:
    """Extract metrics from an Anthropic Message-like response."""
    data: Dict[str, Any] = {}
    if hasattr(result, "usage") and result.usage is not None:
        data["input_tokens"] = getattr(result.usage, "input_tokens", 0) or 0
        data["output_tokens"] = getattr(result.usage, "output_tokens", 0) or 0
        data["total_tokens"] = data.get("input_tokens", 0) + data.get("output_tokens", 0)
    if hasattr(result, "model"):
        data["model"] = result.model or ""
    tools: List[ToolCall] = []
    if hasattr(result, "content"):
        for block in result.content:
            if getattr(block, "type", None) == "tool_use":
                tools.append(ToolCall(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    arguments=getattr(block, "input", {}),
                ))
    data["tools_called"] = tools
    return data


def _extract_generic(result: Any) -> Dict[str, Any]:
    """Fallback extractor for plain return values."""
    return {}


def _auto_extract(result: Any) -> Dict[str, Any]:
    """Detect the framework from the result object and extract metrics."""
    cls_name = type(result).__name__.lower()
    module = type(result).__module__ or ""

    # OpenAI
    if "openai" in module or "chatcompletion" in cls_name:
        return _extract_openai(result)
    # Anthropic
    if "anthropic" in module or cls_name == "message":
        return _extract_anthropic(result)
    return _extract_generic(result)


# ---------------------------------------------------------------------------
# TrackedAgent
# ---------------------------------------------------------------------------

class TrackedAgent:
    """A wrapper around an agent callable that records every invocation.

    Parameters
    ----------
    fn : Callable
        The original agent function/callable to wrap.
    name : str, optional
        Human-readable name for this agent.
    """

    def __init__(self, fn: Callable, name: Optional[str] = None) -> None:
        self._fn = fn
        self.name = name or getattr(fn, "__name__", "agent")
        self.records: List[InvocationRecord] = []
        functools.update_wrapper(self, fn)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the wrapped agent, recording behavioral data."""
        record = InvocationRecord(input=args[0] if args else kwargs)

        start = time.perf_counter()
        try:
            result = self._fn(*args, **kwargs)
            record.output = _safe_serialize(result)
            extracted = _auto_extract(result)
            record.input_tokens = extracted.get("input_tokens", 0)
            record.output_tokens = extracted.get("output_tokens", 0)
            record.total_tokens = extracted.get(
                "total_tokens",
                record.input_tokens + record.output_tokens,
            )
            record.model = extracted.get("model", "")
            record.tools_called = extracted.get("tools_called", [])
            record.steps = max(1, len(record.tools_called))
        except Exception as exc:
            record.error = f"{type(exc).__name__}: {exc}"
            record.output = None
            raise
        finally:
            record.latency_ms = (time.perf_counter() - start) * 1000
            record.cost_usd = _estimate_cost(
                record.model, record.input_tokens, record.output_tokens
            )
            self.records.append(record)

        return result

    def clear_records(self) -> None:
        """Discard all recorded invocations."""
        self.records.clear()

    @property
    def last(self) -> Optional[InvocationRecord]:
        """Return the most recent invocation record, or *None*."""
        return self.records[-1] if self.records else None

    def __repr__(self) -> str:
        return f"TrackedAgent(name={self.name!r}, records={len(self.records)})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def track(
    fn: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
) -> Union[TrackedAgent, Callable]:
    """Wrap *fn* so every call is recorded for behavioral analysis.

    Can be used as a simple wrapper or as a decorator::

        # Wrapper
        agent = track(my_fn, name="researcher")

        # Decorator
        @track
        def my_agent(task):
            ...

        # Decorator with args
        @track(name="researcher")
        def my_agent(task):
            ...
    """
    if fn is None:
        # Called with keyword args: @track(name="x")
        def _decorator(f: Callable) -> TrackedAgent:
            return TrackedAgent(f, name=name)
        return _decorator

    return TrackedAgent(fn, name=name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_serialize(obj: Any) -> Any:
    """Best-effort conversion to a JSON-safe representation."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    # Pydantic model
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    return str(obj)
