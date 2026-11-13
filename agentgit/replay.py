"""Task Trajectory Replay (agentgit replay).

Allows time-travel inspection of recorded agent tasks, showing
the exact thought loop, tool executions, arguments, and responses.

Usage::

    from agentgit.replay import get_task_trace
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    trace = get_task_trace(store, "v1.0", task_index=0)
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from agentgit.snapshot import TaskResult
from agentgit.storage import AgentGitStore


class TaskTrace(BaseModel):
    """Detailed trace for replaying a specific task execution."""

    version: str
    task_index: int
    task_input: Any
    output: Any
    success: bool
    steps: int
    tools_called: List[str] = Field(default_factory=list)
    latency_ms: float
    tokens: int
    cost_usd: float
    error: Optional[str] = None
    model: str = ""


def get_task_trace(store: AgentGitStore, version: str, task_index: int) -> TaskTrace:
    """Retrieve the full execution trace for a task from *version*."""
    snap = store.load(version)
    if task_index < 0 or task_index >= len(snap.task_results):
        raise IndexError(
            f"Task index {task_index} out of bounds (version '{version}' has {len(snap.task_results)} tasks)"
        )

    res: TaskResult = snap.task_results[task_index]
    return TaskTrace(
        version=version,
        task_index=task_index,
        task_input=res.task_input,
        output=res.output,
        success=res.success,
        steps=res.steps,
        tools_called=res.tools_called,
        latency_ms=round(res.latency_ms, 2),
        tokens=res.tokens,
        cost_usd=round(res.cost_usd, 6),
        error=res.error,
        model=res.model,
    )
