"""Multi-Variant Benchmark Matrix (agentgit matrix).

Compares 3 or more snapshots side-by-side (e.g. testing GPT-4o vs Claude 3.5 Sonnet
vs Llama 3.3 on the same benchmark suite).

Usage::

    from agentgit.matrix import build_comparison_matrix
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    matrix = build_comparison_matrix(store, ["v-gpt4o", "v-claude", "v-llama"])
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agentgit.storage import AgentGitStore


class MatrixRow(BaseModel):
    """A row in the comparison matrix."""

    metric: str
    display_name: str
    values: Dict[str, Any] = Field(default_factory=dict)
    best_version: str = ""


class ComparisonMatrix(BaseModel):
    """Complete multi-variant comparison matrix."""

    versions: List[str]
    snapshots: List[Dict[str, Any]]
    rows: List[MatrixRow] = Field(default_factory=list)
    winner_completion: str = ""
    winner_cost: str = ""
    winner_speed: str = ""


_DISPLAY_NAMES = {
    "task_completion_rate": "Task Completion Rate",
    "avg_latency_ms": "Avg Latency (ms)",
    "avg_tokens_per_task": "Avg Tokens / Task",
    "avg_cost_per_task": "Avg Cost / Task ($)",
    "error_rate": "Error Rate",
    "avg_steps_per_task": "Avg Steps / Task",
}


def build_comparison_matrix(store: AgentGitStore, versions: List[str]) -> ComparisonMatrix:
    """Generate a multi-version comparison matrix across *versions*."""
    if len(versions) < 2:
        raise ValueError("Matrix comparison requires at least 2 versions.")

    snapshots = [store.load(v) for v in versions]

    # Metrics to compare
    target_metrics = [
        "task_completion_rate",
        "avg_latency_ms",
        "avg_tokens_per_task",
        "avg_cost_per_task",
        "error_rate",
        "avg_steps_per_task",
    ]

    rows: List[MatrixRow] = []

    for metric in target_metrics:
        vals: Dict[str, Any] = {}
        for snap in snapshots:
            val = getattr(snap.metrics, metric, 0.0)
            vals[snap.version] = round(val, 4)

        # Determine winner for this metric
        if metric == "task_completion_rate":
            best = max(vals, key=lambda v: vals[v])
        else:  # Lower is better
            best = min(vals, key=lambda v: vals[v])

        rows.append(MatrixRow(
            metric=metric,
            display_name=_DISPLAY_NAMES.get(metric, metric),
            values=vals,
            best_version=best,
        ))

    # Determine overall category winners
    completion_vals = {s.version: s.metrics.task_completion_rate for s in snapshots}
    cost_vals = {s.version: s.metrics.avg_cost_per_task for s in snapshots}
    speed_vals = {s.version: s.metrics.avg_latency_ms for s in snapshots}

    winner_completion = max(completion_vals, key=lambda v: completion_vals[v])
    winner_cost = min(cost_vals, key=lambda v: cost_vals[v])
    winner_speed = min(speed_vals, key=lambda v: speed_vals[v])

    return ComparisonMatrix(
        versions=versions,
        snapshots=[
            {
                "version": s.version,
                "agent_name": s.agent_name,
                "num_tasks": s.num_tasks,
                "timestamp": s.timestamp.isoformat()[:19],
            }
            for s in snapshots
        ],
        rows=rows,
        winner_completion=winner_completion,
        winner_cost=winner_cost,
        winner_speed=winner_speed,
    )
