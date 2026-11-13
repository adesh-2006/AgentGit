"""Advanced features tests: blame, replay, matrix, and bisect."""

from __future__ import annotations

import tempfile

import pytest

from agentgit.bisect import bisect_metric
from agentgit.blame import blame_metric
from agentgit.matrix import build_comparison_matrix
from agentgit.replay import get_task_trace
from agentgit.report import (
    print_bisect_report,
    print_blame_report,
    print_matrix_report,
    print_replay_report,
)
from agentgit.snapshot import create_snapshot
from agentgit.storage import AgentGitStore
from agentgit.tracker import track


def _agent_fast(task: str) -> str:
    return f"fast: {task}"


def _agent_slow(task: str) -> str:
    import time
    time.sleep(0.005)
    return f"slow: {task}"


def _agent_error(task: str) -> str:
    raise RuntimeError("Intentional error")


class TestAdvancedFeatures:
    def test_blame_attribution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            agent1 = track(_agent_fast)
            agent2 = track(_agent_slow)

            snap1 = create_snapshot(agent1, "v1", ["t1", "t2"])
            snap2 = create_snapshot(agent2, "v2", ["t1", "t2"])

            store.save(snap1)
            store.save(snap2)

            blame = blame_metric(store, "avg_latency_ms")
            assert len(blame.entries) == 2
            assert blame.primary_culprit == "v2"
            print_blame_report(blame)

    def test_replay_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            agent = track(_agent_fast)
            snap = create_snapshot(agent, "v1", ["task 1", "task 2"])
            store.save(snap)

            trace = get_task_trace(store, "v1", task_index=0)
            assert trace.task_input == "task 1"
            assert trace.success
            print_replay_report(trace)

            with pytest.raises(IndexError):
                get_task_trace(store, "v1", task_index=99)

    def test_comparison_matrix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            agent1 = track(_agent_fast)
            agent2 = track(_agent_slow)

            store.save(create_snapshot(agent1, "v1", ["a", "b"]))
            store.save(create_snapshot(agent2, "v2", ["a", "b"]))

            matrix = build_comparison_matrix(store, ["v1", "v2"])
            assert matrix.versions == ["v1", "v2"]
            assert len(matrix.rows) > 0
            assert matrix.winner_speed == "v1"
            print_matrix_report(matrix)

    def test_bisect_regression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            agent_good = track(_agent_fast)
            agent_bad = track(_agent_error)

            store.save(create_snapshot(agent_good, "v1.0", ["a"]))
            store.save(create_snapshot(agent_bad, "v2.0", ["a"]))
            store.save(create_snapshot(agent_bad, "v3.0", ["a"]))

            res = bisect_metric(store, "v1.0", "v3.0", metric="error_rate")
            assert res.culprit_version == "v2.0"
            assert res.good_value == 0.0
            assert res.bad_value == 1.0
            print_bisect_report(res)
