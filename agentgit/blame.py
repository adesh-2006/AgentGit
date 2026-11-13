"""Behavioral Attribution Engine (agentgit blame).

Analyzes the history of snapshots to identify which version, commit,
or update introduced a regression or behavioral shift in a specific metric.

Usage::

    from agentgit.blame import blame_metric
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    report = blame_metric(store, "error_rate")
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from agentgit.diff import ChangeStatus, _determine_status
from agentgit.storage import AgentGitStore


class BlameEntry(BaseModel):
    """A single version step in the metric's evolution."""

    version: str
    timestamp: str
    value: float
    delta: float = 0.0
    delta_pct: float = 0.0
    status: ChangeStatus = ChangeStatus.NEUTRAL
    agent_name: str = ""
    is_shift_point: bool = False


class BlameReport(BaseModel):
    """Full blame attribution report for a given metric."""

    metric: str
    entries: List[BlameEntry] = Field(default_factory=list)
    primary_culprit: Optional[str] = None
    shift_magnitude: float = 0.0
    summary: str = ""


def blame_metric(store: AgentGitStore, metric: str) -> BlameReport:
    """Trace *metric* across all recorded snapshots in chronological order."""
    snapshots = store.list()
    if not snapshots:
        return BlameReport(metric=metric, summary="No snapshots recorded yet.")

    # Canonicalize metric name
    from agentgit.ci import _METRIC_ALIASES
    canonical = _METRIC_ALIASES.get(metric, metric)

    entries: List[BlameEntry] = []
    prev_val: Optional[float] = None
    max_regression = 0.0
    culprit_version: Optional[str] = None

    for snap in snapshots:
        val = getattr(snap.metrics, canonical, None)
        if val is None:
            # Check tool_usage if metric has format 'tool:name'
            if canonical.startswith("tool:") or canonical.startswith("tool_"):
                tool_name = canonical.split(":", 1)[-1].replace("tool_", "")
                val = float(snap.metrics.tool_usage.get(tool_name, 0))
            else:
                continue

        delta = (val - prev_val) if prev_val is not None else 0.0
        delta_pct = (delta / prev_val * 100) if (prev_val and prev_val != 0) else 0.0
        status = _determine_status(canonical, delta) if prev_val is not None else ChangeStatus.NEUTRAL

        # Detect the biggest regression
        if status == ChangeStatus.REGRESSED and abs(delta) > max_regression:
            max_regression = abs(delta)
            culprit_version = snap.version

        entries.append(BlameEntry(
            version=snap.version,
            timestamp=snap.timestamp.isoformat()[:19],
            value=round(val, 4),
            delta=round(delta, 4),
            delta_pct=round(delta_pct, 1),
            status=status,
            agent_name=snap.agent_name,
            is_shift_point=False,
        ))
        prev_val = val

    # Mark the biggest shift point
    if culprit_version:
        for e in entries:
            if e.version == culprit_version:
                e.is_shift_point = True

    if culprit_version:
        summary = f"⚠️ Major regression in '{canonical}' first introduced in version '{culprit_version}'."
    else:
        summary = f"✅ No regressions detected for '{canonical}' across {len(entries)} snapshot(s)."

    return BlameReport(
        metric=canonical,
        entries=entries,
        primary_culprit=culprit_version,
        shift_magnitude=round(max_regression, 4),
        summary=summary,
    )
