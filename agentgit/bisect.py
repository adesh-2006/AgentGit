"""Automated Regression Bisect Engine (agentgit bisect).

Pinpoints the exact snapshot or transition point where a metric degraded
between a known-good version and a known-bad version.

Usage::

    from agentgit.bisect import bisect_metric
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    result = bisect_metric(store, "v1.0", "v3.0", metric="error_rate")
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from agentgit.storage import AgentGitStore


class BisectStep(BaseModel):
    """A step in the bisect traversal."""

    version: str
    value: float
    is_regression_boundary: bool = False


class BisectResult(BaseModel):
    """Result of bisecting an agent regression."""

    metric: str
    good_version: str
    bad_version: str
    good_value: float
    bad_value: float
    culprit_version: Optional[str] = None
    steps: List[BisectStep]
    explanation: str = ""


def bisect_metric(
    store: AgentGitStore,
    good_version: str,
    bad_version: str,
    metric: str = "error_rate",
) -> BisectResult:
    """Find the exact snapshot between good and bad versions where *metric* regressed."""
    from agentgit.ci import _METRIC_ALIASES
    canonical = _METRIC_ALIASES.get(metric, metric)

    all_snapshots = store.list()
    all_versions = [s.version for s in all_snapshots]

    if good_version not in all_versions:
        raise ValueError(f"Good version '{good_version}' not found.")
    if bad_version not in all_versions:
        raise ValueError(f"Bad version '{bad_version}' not found.")

    idx_good = all_versions.index(good_version)
    idx_bad = all_versions.index(bad_version)

    # Slice the snapshots between good and bad
    start, end = min(idx_good, idx_bad), max(idx_good, idx_bad) + 1
    sub_snaps = all_snapshots[start:end]

    good_snap = store.load(good_version)
    bad_snap = store.load(bad_version)
    good_val = getattr(good_snap.metrics, canonical, 0.0)
    bad_val = getattr(bad_snap.metrics, canonical, 0.0)

    steps: List[BisectStep] = []
    culprit: Optional[str] = None

    for snap in sub_snaps:
        val = getattr(snap.metrics, canonical, 0.0)
        # Check if this snapshot is where the regression first appeared
        # (Assuming bad_val is worse than good_val)
        is_culprit = False
        if culprit is None and snap.version != good_version:
            if bad_val > good_val and val > good_val:
                is_culprit = True
                culprit = snap.version
            elif bad_val < good_val and val < good_val:
                is_culprit = True
                culprit = snap.version

        steps.append(BisectStep(
            version=snap.version,
            value=round(val, 4),
            is_regression_boundary=is_culprit,
        ))

    if culprit:
        explanation = (
            f"🎯 Regression in '{canonical}' first introduced in version '{culprit}' "
            f"(jumped from {good_val:.4f} to {getattr(store.load(culprit).metrics, canonical, 0.0):.4f})."
        )
    else:
        explanation = f"No intermediate regression step found between '{good_version}' and '{bad_version}'."

    return BisectResult(
        metric=canonical,
        good_version=good_version,
        bad_version=bad_version,
        good_value=good_val,
        bad_value=bad_val,
        culprit_version=culprit,
        steps=steps,
        explanation=explanation,
    )
