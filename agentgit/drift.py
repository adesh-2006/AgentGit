"""Semantic & Behavioral Drift Analyzer (agentgit drift).

Compares free-form text responses across snapshots to detect:
- Verbosity shifts (answers suddenly ballooning or collapsing)
- Lexical & content divergence (Jaccard similarity)
- Sentiment & contradiction flips (e.g. v1 says "Yes/Approved", v2 says "No/Rejected")

Usage::

    from agentgit.drift import analyze_drift
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    drift = analyze_drift(store, "v1.0", "v2.0")
"""

from __future__ import annotations

import re
from typing import Any, List, Set

from pydantic import BaseModel, Field

from agentgit.storage import AgentGitStore


class TaskDrift(BaseModel):
    """Drift analysis for a single task output."""

    task_index: int
    task_input: Any
    old_output: str
    new_output: str
    length_ratio: float
    lexical_similarity: float  # 0.0 to 1.0 Jaccard
    contradiction_risk: bool
    description: str = ""


class DriftReport(BaseModel):
    """Full semantic drift report between two snapshot versions."""

    from_version: str
    to_version: str
    avg_similarity: float
    avg_length_change_pct: float
    contradiction_count: int
    tasks: List[TaskDrift] = Field(default_factory=list)
    verdict: str = ""


_AFFIRMATIVES = {"yes", "approved", "confirmed", "success", "resolved", "completed", "allowed"}
_NEGATIVES = {"no", "rejected", "denied", "failed", "cancelled", "refused", "error", "unable"}


def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric words."""
    return set(re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower()))


def _detect_polarity_flip(text_a: str, text_b: str) -> bool:
    """Check if one text affirms while the other negates."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    has_aff_a = bool(tokens_a & _AFFIRMATIVES)
    has_neg_a = bool(tokens_a & _NEGATIVES)
    has_aff_b = bool(tokens_b & _AFFIRMATIVES)
    has_neg_b = bool(tokens_b & _NEGATIVES)

    # Flip from positive to negative
    if has_aff_a and not has_neg_a and has_neg_b and not has_aff_b:
        return True
    # Flip from negative to positive
    if has_neg_a and not has_aff_a and has_aff_b and not has_neg_b:
        return True
    return False


def analyze_drift(store: AgentGitStore, version_a: str, version_b: str) -> DriftReport:
    """Compute semantic drift between outputs of *version_a* and *version_b*."""
    snap_a = store.load(version_a)
    snap_b = store.load(version_b)

    tasks_a = {i: r for i, r in enumerate(snap_a.task_results)}
    tasks_b = {i: r for i, r in enumerate(snap_b.task_results)}

    common_indices = sorted(set(tasks_a.keys()) & set(tasks_b.keys()))
    if not common_indices:
        return DriftReport(
            from_version=version_a,
            to_version=version_b,
            avg_similarity=1.0,
            avg_length_change_pct=0.0,
            contradiction_count=0,
            verdict="No common task indices to compare.",
        )

    task_drifts: List[TaskDrift] = []
    similarities: List[float] = []
    length_changes: List[float] = []
    contradictions = 0

    for idx in common_indices:
        out_a = str(tasks_a[idx].output or "")
        out_b = str(tasks_b[idx].output or "")

        toks_a = _tokenize(out_a)
        toks_b = _tokenize(out_b)

        # Jaccard similarity
        union = toks_a | toks_b
        intersection = toks_a & toks_b
        jaccard = (len(intersection) / len(union)) if union else 1.0
        similarities.append(jaccard)

        # Length ratio
        len_a = len(out_a.split())
        len_b = len(out_b.split())
        ratio = (len_b / len_a) if len_a > 0 else 1.0
        len_change_pct = ((len_b - len_a) / len_a * 100) if len_a > 0 else 0.0
        length_changes.append(len_change_pct)

        # Contradiction detection
        is_flip = _detect_polarity_flip(out_a, out_b)
        if is_flip:
            contradictions += 1

        desc = []
        if is_flip:
            desc.append("⚠️ Polar contradiction detected")
        if abs(len_change_pct) > 50:
            direction = "expanded" if len_change_pct > 0 else "shrunk"
            desc.append(f"Length {direction} by {abs(len_change_pct):.0f}%")
        if jaccard < 0.3:
            desc.append("High vocabulary divergence")

        task_drifts.append(TaskDrift(
            task_index=idx,
            task_input=tasks_a[idx].task_input,
            old_output=out_a[:100] + ("..." if len(out_a) > 100 else ""),
            new_output=out_b[:100] + ("..." if len(out_b) > 100 else ""),
            length_ratio=round(ratio, 2),
            lexical_similarity=round(jaccard, 3),
            contradiction_risk=is_flip,
            description="; ".join(desc) if desc else "Consistent",
        ))

    avg_sim = sum(similarities) / len(similarities) if similarities else 1.0
    avg_len_change = sum(length_changes) / len(length_changes) if length_changes else 0.0

    if contradictions > 0:
        verdict = f"⚠️ High Drift: {contradictions} contradictory response(s) detected!"
    elif avg_sim < 0.5:
        verdict = f"⚠️ Moderate Drift: Average lexical similarity dropped to {avg_sim:.0%}."
    else:
        verdict = f"✅ Low Drift: Outputs remain semantically consistent ({avg_sim:.0%} similarity)."

    return DriftReport(
        from_version=version_a,
        to_version=version_b,
        avg_similarity=round(avg_sim, 3),
        avg_length_change_pct=round(avg_len_change, 1),
        contradiction_count=contradictions,
        tasks=task_drifts,
        verdict=verdict,
    )
