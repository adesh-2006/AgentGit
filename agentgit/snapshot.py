"""Behavioral Snapshot Engine.

A *snapshot* captures a statistical profile of how an agent behaves across
a set of tasks at a specific point in time.  Comparing snapshots lets you
see exactly what changed when you modify a prompt, upgrade a model, or
tweak a tool.

Usage::

    from agentgit import track, snapshot

    agent = track(my_agent)
    snap = snapshot(agent, "v1.0", tasks=["Summarize X", "Find Y"])
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from agentgit.tracker import InvocationRecord, TrackedAgent


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BehavioralMetrics(BaseModel):
    """Aggregated behavioral metrics for a snapshot."""

    task_completion_rate: float = 0.0
    avg_steps_per_task: float = 0.0
    avg_latency_ms: float = 0.0
    avg_tokens_per_task: float = 0.0
    avg_cost_per_task: float = 0.0
    total_cost_usd: float = 0.0
    error_rate: float = 0.0
    tool_usage: Dict[str, int] = Field(default_factory=dict)
    models_used: Dict[str, int] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Result of a single task execution."""

    task_input: Any = None
    output: Any = None
    success: bool = True
    steps: int = 1
    tools_called: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
    model: str = ""


class BehavioralSnapshot(BaseModel):
    """A complete behavioral profile of an agent at a point in time."""

    version: str
    agent_name: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    num_tasks: int = 0
    metrics: BehavioralMetrics = Field(default_factory=BehavioralMetrics)
    task_results: List[TaskResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------

def create_snapshot(
    agent: TrackedAgent,
    version: str,
    tasks: List[Any],
    *,
    task_runner: Optional[Callable] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> BehavioralSnapshot:
    """Run *agent* on *tasks* and build a :class:`BehavioralSnapshot`.

    Parameters
    ----------
    agent : TrackedAgent
        A tracked agent (created via ``track()``).
    version : str
        Version label, e.g. ``"v1.0"``.
    tasks : list
        Inputs to feed the agent.
    task_runner : callable, optional
        Custom function ``(agent, task) -> result``.  Defaults to calling
        ``agent(task)`` directly.
    metadata : dict, optional
        Extra metadata to attach to the snapshot.
    """
    agent.clear_records()
    task_results: List[TaskResult] = []

    for task in tasks:
        try:
            if task_runner:
                task_runner(agent, task)
            else:
                agent(task)

            rec: InvocationRecord = agent.last  # type: ignore[assignment]
            task_results.append(TaskResult(
                task_input=task,
                output=rec.output,
                success=rec.success,
                steps=rec.steps,
                tools_called=[t.name for t in rec.tools_called],
                latency_ms=rec.latency_ms,
                tokens=rec.total_tokens,
                cost_usd=rec.cost_usd,
                error=rec.error,
                model=rec.model,
            ))
        except Exception as exc:
            task_results.append(TaskResult(
                task_input=task,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            ))

    metrics = _compute_metrics(task_results)

    return BehavioralSnapshot(
        version=version,
        agent_name=agent.name,
        num_tasks=len(tasks),
        metrics=metrics,
        task_results=task_results,
        metadata=metadata or {},
    )


def _compute_metrics(results: List[TaskResult]) -> BehavioralMetrics:
    """Compute aggregate metrics from individual task results."""
    if not results:
        return BehavioralMetrics()

    n = len(results)
    successes = sum(1 for r in results if r.success)
    tool_usage: Dict[str, int] = {}
    models_used: Dict[str, int] = {}

    for r in results:
        for t in r.tools_called:
            tool_usage[t] = tool_usage.get(t, 0) + 1
        if r.model:
            models_used[r.model] = models_used.get(r.model, 0) + 1

    latencies = [r.latency_ms for r in results]
    tokens = [r.tokens for r in results]
    costs = [r.cost_usd for r in results]
    steps = [r.steps for r in results]

    return BehavioralMetrics(
        task_completion_rate=successes / n if n else 0,
        avg_steps_per_task=statistics.mean(steps) if steps else 0,
        avg_latency_ms=statistics.mean(latencies) if latencies else 0,
        avg_tokens_per_task=statistics.mean(tokens) if tokens else 0,
        avg_cost_per_task=statistics.mean(costs) if costs else 0,
        total_cost_usd=sum(costs),
        error_rate=1 - (successes / n) if n else 0,
        tool_usage=tool_usage,
        models_used=models_used,
    )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_snapshot(snapshot: BehavioralSnapshot, directory: str | Path) -> Path:
    """Serialize *snapshot* to a JSON file under *directory*."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{snapshot.version}.json"
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_snapshot(version: str, directory: str | Path) -> BehavioralSnapshot:
    """Load a snapshot from *directory*."""
    path = Path(directory) / f"{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"Snapshot '{version}' not found at {path}")
    return BehavioralSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def list_snapshots(directory: str | Path) -> List[BehavioralSnapshot]:
    """List all snapshots in *directory*, sorted by timestamp."""
    d = Path(directory)
    if not d.exists():
        return []
    snapshots = []
    for f in sorted(d.glob("*.json")):
        try:
            snapshots.append(BehavioralSnapshot.model_validate_json(
                f.read_text(encoding="utf-8")
            ))
        except Exception:
            continue
    return sorted(snapshots, key=lambda s: s.timestamp)
