"""Tests for the core AgentGit functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agentgit.tracker import track, TrackedAgent, InvocationRecord
from agentgit.snapshot import create_snapshot, BehavioralSnapshot, save_snapshot, load_snapshot
from agentgit.diff import create_diff, ChangeStatus
from agentgit.report import diff_to_markdown, diff_to_html
from agentgit.ci import parse_rules, ci_check
from agentgit.storage import AgentGitStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dummy_agent(task: str) -> str:
    """A simple agent that echoes."""
    return f"Result for: {task}"


def _flaky_agent(task: str) -> str:
    """Agent that fails on certain inputs."""
    if "fail" in task.lower():
        raise ValueError("Simulated failure")
    return f"OK: {task}"


# ---------------------------------------------------------------------------
# Tracker tests
# ---------------------------------------------------------------------------

class TestTracker:
    def test_track_wrapper(self):
        agent = track(_dummy_agent, name="test-bot")
        assert isinstance(agent, TrackedAgent)
        assert agent.name == "test-bot"

    def test_track_records_invocation(self):
        agent = track(_dummy_agent)
        result = agent("hello")
        assert result == "Result for: hello"
        assert len(agent.records) == 1
        assert agent.last is not None
        assert agent.last.success

    def test_track_records_error(self):
        agent = track(_flaky_agent)
        try:
            agent("please fail")
        except ValueError:
            pass
        assert len(agent.records) == 1
        assert not agent.last.success
        assert "Simulated failure" in agent.last.error

    def test_track_latency(self):
        agent = track(_dummy_agent)
        agent("test")
        assert agent.last.latency_ms > 0

    def test_track_as_decorator(self):
        @track
        def my_agent(task: str) -> str:
            return task.upper()

        result = my_agent("hello")
        assert result == "HELLO"
        assert len(my_agent.records) == 1

    def test_clear_records(self):
        agent = track(_dummy_agent)
        agent("a")
        agent("b")
        assert len(agent.records) == 2
        agent.clear_records()
        assert len(agent.records) == 0


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_create_snapshot(self):
        agent = track(_dummy_agent, name="snap-test")
        snap = create_snapshot(agent, "v1.0", ["task1", "task2", "task3"])
        assert snap.version == "v1.0"
        assert snap.num_tasks == 3
        assert snap.metrics.task_completion_rate == 1.0
        assert snap.metrics.error_rate == 0.0
        assert len(snap.task_results) == 3

    def test_snapshot_with_errors(self):
        agent = track(_flaky_agent, name="flaky")
        snap = create_snapshot(agent, "v1.0", ["ok task", "fail task", "another ok"])
        assert abs(snap.metrics.task_completion_rate - 2 / 3) < 1e-9
        assert abs(snap.metrics.error_rate - 1 / 3) < 1e-9

    def test_save_load_snapshot(self):
        agent = track(_dummy_agent)
        snap = create_snapshot(agent, "v-test", ["a", "b"])

        with tempfile.TemporaryDirectory() as tmpdir:
            save_snapshot(snap, tmpdir)
            loaded = load_snapshot("v-test", tmpdir)
            assert loaded.version == "v-test"
            assert loaded.num_tasks == 2
            assert loaded.metrics.task_completion_rate == snap.metrics.task_completion_rate


# ---------------------------------------------------------------------------
# Diff tests
# ---------------------------------------------------------------------------

class TestDiff:
    def test_diff_improved(self):
        agent = track(_dummy_agent)
        snap_a = create_snapshot(agent, "v1", ["a", "b"])

        # Create a "better" snapshot manually
        snap_b = snap_a.model_copy(deep=True)
        snap_b.version = "v2"
        snap_b.metrics.task_completion_rate = 1.0
        snap_b.metrics.error_rate = 0.0
        snap_b.metrics.avg_latency_ms = snap_a.metrics.avg_latency_ms * 0.5  # faster

        diff = create_diff(snap_a, snap_b)
        assert diff.from_version == "v1"
        assert diff.to_version == "v2"
        # Latency improvement
        latency_change = [c for c in diff.changes if c.metric == "avg_latency_ms"][0]
        assert latency_change.status == ChangeStatus.IMPROVED

    def test_diff_regressed(self):
        agent = track(_dummy_agent)
        snap_a = create_snapshot(agent, "v1", ["a", "b", "c"])
        snap_b = snap_a.model_copy(deep=True)
        snap_b.version = "v2"
        snap_b.metrics.error_rate = 0.5  # worse

        diff = create_diff(snap_a, snap_b)
        error_change = [c for c in diff.changes if c.metric == "error_rate"][0]
        assert error_change.status == ChangeStatus.REGRESSED

    def test_diff_verdict(self):
        agent = track(_dummy_agent)
        snap_a = create_snapshot(agent, "v1", ["a"])
        snap_b = snap_a.model_copy(deep=True)
        snap_b.version = "v2"

        diff = create_diff(snap_a, snap_b)
        assert "No significant" in diff.verdict

    def test_diff_markdown_export(self):
        agent = track(_dummy_agent)
        snap_a = create_snapshot(agent, "v1", ["a"])
        snap_b = create_snapshot(agent, "v2", ["a", "b"])
        diff = create_diff(snap_a, snap_b)
        md = diff_to_markdown(diff)
        assert "AgentGit Behavioral Diff" in md
        assert "| Metric | `v1` | `v2` |" in md
        assert "Verdict:" in md

    def test_diff_html_export(self):
        agent = track(_dummy_agent)
        snap_a = create_snapshot(agent, "v1", ["a"])
        snap_b = create_snapshot(agent, "v2", ["a", "b"])
        diff = create_diff(snap_a, snap_b)
        html = diff_to_html(diff)
        assert "<!DOCTYPE html>" in html
        assert "AgentGit Behavioral Diff" in html
        assert "kpi-card" in html


# ---------------------------------------------------------------------------
# CI tests
# ---------------------------------------------------------------------------

class TestCI:
    def test_parse_rules(self):
        rules = parse_rules("task_completion >= 0.85 AND error_rate < 0.10")
        assert len(rules) == 2
        assert rules[0].metric == "task_completion_rate"  # alias resolved
        assert rules[0].op == ">="
        assert rules[0].threshold == 0.85

    def test_ci_check_pass(self):
        agent = track(_dummy_agent)
        snap = create_snapshot(agent, "v1", ["a", "b", "c"])
        rules = parse_rules("task_completion >= 0.85")
        passed, details = ci_check(snap, rules)
        assert passed

    def test_ci_check_fail(self):
        agent = track(_flaky_agent)
        snap = create_snapshot(agent, "v1", ["ok", "fail", "ok"])
        rules = parse_rules("task_completion >= 0.90")
        passed, details = ci_check(snap, rules)
        assert not passed


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

class TestStorage:
    def test_init_and_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir, name="test-agent")
            assert store.is_initialised
            assert store.get_config()["agent_name"] == "test-agent"

            agent = track(_dummy_agent)
            snap = create_snapshot(agent, "v1.0", ["a", "b"])
            store.save(snap)

            assert store.exists("v1.0")
            assert store.get_current_version() == "v1.0"

            loaded = store.load("v1.0")
            assert loaded.version == "v1.0"

    def test_list_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            agent = track(_dummy_agent)

            store.save(create_snapshot(agent, "v1", ["a"]))
            store.save(create_snapshot(agent, "v2", ["a", "b"]))

            summaries = store.list_summary()
            assert len(summaries) == 2
