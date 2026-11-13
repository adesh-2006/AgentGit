"""CI/CD gate — fail a pipeline if agent behavior regresses.

Usage::

    # In a script or GitHub Actions step:
    agentgit ci-check v2.0 --rules "task_completion >= 0.85 AND error_rate < 0.10"

    # Programmatic:
    from agentgit.ci import parse_rules, ci_check
    rules = parse_rules("task_completion_rate >= 0.85 AND error_rate < 0.10")
    passed, results = ci_check(snapshot, rules)
"""

from __future__ import annotations

import operator
import re
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel

from agentgit.snapshot import BehavioralSnapshot


class CIRule(BaseModel):
    """A single CI check rule."""

    metric: str
    op: str  # ">=", "<=", ">", "<", "=="
    threshold: float
    raw: str = ""


_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

# Accept common aliases
_METRIC_ALIASES = {
    "task_completion": "task_completion_rate",
    "completion": "task_completion_rate",
    "completion_rate": "task_completion_rate",
    "errors": "error_rate",
    "latency": "avg_latency_ms",
    "cost": "avg_cost_per_task",
    "tokens": "avg_tokens_per_task",
    "steps": "avg_steps_per_task",
    "total_cost": "total_cost_usd",
}


def parse_rules(rule_string: str) -> List[CIRule]:
    """Parse a rule string like ``"task_completion >= 0.85 AND error_rate < 0.10"``.

    Returns a list of :class:`CIRule` objects.
    """
    # Split on AND / and / , / ;
    parts = re.split(r"\s+(?:AND|and|&)\s+|;\s*|,\s*", rule_string.strip())
    rules: List[CIRule] = []

    pattern = re.compile(
        r"(?P<metric>\w+)\s*(?P<op>>=|<=|!=|>|<|==)\s*(?P<value>[\d.]+)"
    )

    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = pattern.match(part)
        if not m:
            raise ValueError(f"Cannot parse CI rule: {part!r}")

        metric = m.group("metric")
        metric = _METRIC_ALIASES.get(metric, metric)

        rules.append(CIRule(
            metric=metric,
            op=m.group("op"),
            threshold=float(m.group("value")),
            raw=part,
        ))

    return rules


def ci_check(
    snapshot: BehavioralSnapshot,
    rules: List[CIRule],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Evaluate *rules* against *snapshot*.

    Returns
    -------
    (passed, details)
        ``passed`` is ``True`` only when every rule passes.
        ``details`` is a list of dicts with ``rule``, ``actual``, ``passed``.
    """
    details: List[Dict[str, Any]] = []
    all_passed = True

    for rule in rules:
        actual = getattr(snapshot.metrics, rule.metric, None)
        if actual is None:
            details.append({
                "rule": rule.raw or f"{rule.metric} {rule.op} {rule.threshold}",
                "actual": None,
                "passed": False,
                "reason": f"Unknown metric: {rule.metric}",
            })
            all_passed = False
            continue

        op_fn = _OPS.get(rule.op)
        if op_fn is None:
            details.append({
                "rule": rule.raw,
                "actual": actual,
                "passed": False,
                "reason": f"Unknown operator: {rule.op}",
            })
            all_passed = False
            continue

        passed = op_fn(actual, rule.threshold)
        details.append({
            "rule": rule.raw or f"{rule.metric} {rule.op} {rule.threshold}",
            "actual": actual,
            "passed": passed,
        })
        if not passed:
            all_passed = False

    return all_passed, details
