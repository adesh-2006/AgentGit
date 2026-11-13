"""Behavioral Diff Engine.

Compares two :class:`BehavioralSnapshot` objects and produces a structured
diff that shows exactly which metrics improved, regressed, or stayed neutral.

Usage::

    from agentgit.diff import create_diff

    result = create_diff(snapshot_v1, snapshot_v2)
    for change in result.changes:
        print(change.metric, change.status, change.delta_pct)
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field

from agentgit.snapshot import BehavioralSnapshot


class ChangeStatus(str, Enum):
    """Direction of a behavioral change."""

    IMPROVED = "improved"
    REGRESSED = "regressed"
    NEUTRAL = "neutral"


class Change(BaseModel):
    """A single metric change between two snapshots."""

    metric: str
    old_value: float = 0.0
    new_value: float = 0.0
    delta: float = 0.0
    delta_pct: float = 0.0
    status: ChangeStatus = ChangeStatus.NEUTRAL
    description: str = ""


class ToolChange(BaseModel):
    """Change in a single tool's usage count."""

    tool: str
    old_count: int = 0
    new_count: int = 0
    delta: int = 0
    delta_pct: float = 0.0


class BehavioralDiff(BaseModel):
    """Complete behavioral diff between two snapshots."""

    from_version: str
    to_version: str
    changes: List[Change] = Field(default_factory=list)
    tool_changes: List[ToolChange] = Field(default_factory=list)
    improvements: int = 0
    regressions: int = 0
    neutral: int = 0
    verdict: str = ""


# ---------------------------------------------------------------------------
# Metric polarity: which direction is "better"?
# ---------------------------------------------------------------------------

_HIGHER_IS_BETTER = {"task_completion_rate"}
_LOWER_IS_BETTER = {
    "avg_steps_per_task",
    "avg_latency_ms",
    "avg_tokens_per_task",
    "avg_cost_per_task",
    "total_cost_usd",
    "error_rate",
}

_METRIC_LABELS = {
    "task_completion_rate": "Task Completion",
    "avg_steps_per_task": "Avg Steps / Task",
    "avg_latency_ms": "Avg Latency (ms)",
    "avg_tokens_per_task": "Avg Tokens / Task",
    "avg_cost_per_task": "Avg Cost / Task",
    "total_cost_usd": "Total Cost",
    "error_rate": "Error Rate",
}


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def create_diff(
    snapshot_a: BehavioralSnapshot,
    snapshot_b: BehavioralSnapshot,
) -> BehavioralDiff:
    """Compute the behavioral diff from *snapshot_a* → *snapshot_b*.

    Parameters
    ----------
    snapshot_a : BehavioralSnapshot
        The baseline (older) snapshot.
    snapshot_b : BehavioralSnapshot
        The comparison (newer) snapshot.

    Returns
    -------
    BehavioralDiff
        Structured diff with per-metric changes and a verdict.
    """
    changes: List[Change] = []

    ma = snapshot_a.metrics
    mb = snapshot_b.metrics

    for field in (
        "task_completion_rate",
        "avg_steps_per_task",
        "avg_latency_ms",
        "avg_tokens_per_task",
        "avg_cost_per_task",
        "total_cost_usd",
        "error_rate",
    ):
        old_val = getattr(ma, field, 0.0)
        new_val = getattr(mb, field, 0.0)
        delta = new_val - old_val
        delta_pct = (delta / old_val * 100) if old_val else (100.0 if delta else 0.0)

        status = _determine_status(field, delta)

        changes.append(Change(
            metric=field,
            old_value=round(old_val, 6),
            new_value=round(new_val, 6),
            delta=round(delta, 6),
            delta_pct=round(delta_pct, 2),
            status=status,
            description=_METRIC_LABELS.get(field, field),
        ))

    # Tool usage diff
    all_tools = set(ma.tool_usage) | set(mb.tool_usage)
    tool_changes: List[ToolChange] = []
    for tool in sorted(all_tools):
        old_c = ma.tool_usage.get(tool, 0)
        new_c = mb.tool_usage.get(tool, 0)
        d = new_c - old_c
        d_pct = (d / old_c * 100) if old_c else (100.0 if d else 0.0)
        tool_changes.append(ToolChange(
            tool=tool,
            old_count=old_c,
            new_count=new_c,
            delta=d,
            delta_pct=round(d_pct, 2),
        ))

    improvements = sum(1 for c in changes if c.status == ChangeStatus.IMPROVED)
    regressions = sum(1 for c in changes if c.status == ChangeStatus.REGRESSED)
    neutral = sum(1 for c in changes if c.status == ChangeStatus.NEUTRAL)
    verdict = _generate_verdict(changes, improvements, regressions)

    return BehavioralDiff(
        from_version=snapshot_a.version,
        to_version=snapshot_b.version,
        changes=changes,
        tool_changes=tool_changes,
        improvements=improvements,
        regressions=regressions,
        neutral=neutral,
        verdict=verdict,
    )


def _determine_status(metric: str, delta: float) -> ChangeStatus:
    """Determine whether a delta is an improvement or regression."""
    if abs(delta) < 1e-9:
        return ChangeStatus.NEUTRAL
    if metric in _HIGHER_IS_BETTER:
        return ChangeStatus.IMPROVED if delta > 0 else ChangeStatus.REGRESSED
    if metric in _LOWER_IS_BETTER:
        return ChangeStatus.IMPROVED if delta < 0 else ChangeStatus.REGRESSED
    return ChangeStatus.NEUTRAL


def _generate_verdict(
    changes: List[Change],
    improvements: int,
    regressions: int,
) -> str:
    """Auto-generate a human-readable verdict string."""
    if regressions == 0 and improvements > 0:
        return f"✅ All clear — {improvements} metric(s) improved, no regressions."
    if improvements == 0 and regressions > 0:
        regressed = [c.description for c in changes if c.status == ChangeStatus.REGRESSED]
        return f"🔴 Regression detected in {regressions} metric(s): {', '.join(regressed)}."
    if improvements > 0 and regressions > 0:
        regressed = [c.description for c in changes if c.status == ChangeStatus.REGRESSED]
        return (
            f"⚠️  Mixed results — {improvements} improved, {regressions} regressed "
            f"({', '.join(regressed)})."
        )
    return "➖ No significant behavioral changes detected."
