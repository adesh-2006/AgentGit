"""Tests for easy installation and onboarding CLI commands (demo, quickstart, diagnose)."""

import os

from click.testing import CliRunner

from agentgit.cli import cli
from agentgit.snapshot import BehavioralMetrics, BehavioralSnapshot, TaskResult
from agentgit.storage import AgentGitStore


def test_cli_demo():
    runner = CliRunner()
    result = runner.invoke(cli, ["demo"])
    assert result.exit_code == 0
    assert "Welcome to AgentGit Demo" in result.output
    assert "Behavioral Diff" in result.output
    assert "Solving the Regression Errors" in result.output
    assert "Demo finished" in result.output


def test_cli_quickstart_python():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["quickstart", "--framework", "python"])
        assert result.exit_code == 0
        assert "Generated agent_eval.py" in result.output
        assert os.path.exists("agent_eval.py")
        content = open("agent_eval.py", encoding="utf-8").read()
        assert "track" in content
        assert "snapshot" in content


def test_cli_quickstart_langchain():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["quickstart", "--framework", "langchain"])
        assert result.exit_code == 0
        assert os.path.exists("agent_eval.py")
        content = open("agent_eval.py", encoding="utf-8").read()
        assert "my_langchain_agent" in content


def test_cli_diagnose():
    runner = CliRunner()
    with runner.isolated_filesystem():
        store = AgentGitStore(".")
        store.init("diagnose-test")

        snap1 = BehavioralSnapshot(
            version="v1.0",
            num_tasks=2,
            metrics=BehavioralMetrics(task_completion_rate=1.0, error_rate=0.0),
            task_results=[
                TaskResult(task_input="q1", success=True),
                TaskResult(task_input="q2", success=True),
            ],
        )
        snap2 = BehavioralSnapshot(
            version="v2.0",
            num_tasks=2,
            metrics=BehavioralMetrics(task_completion_rate=0.5, error_rate=0.5),
            task_results=[
                TaskResult(task_input="q1", success=True),
                TaskResult(task_input="q2", success=False, error="Gateway timeout 504"),
            ],
        )
        store.save(snap1)
        store.save(snap2)

        # Single version diagnosis
        res_single = runner.invoke(cli, ["diagnose", "v2.0"])
        assert res_single.exit_code == 0
        assert "Failure Diagnosis" in res_single.output
        assert "Gateway timeout 504" in res_single.output
        assert "Fix:" in res_single.output

        # Diff diagnosis
        res_diff = runner.invoke(cli, ["diagnose", "v2.0", "v1.0"])
        assert res_diff.exit_code == 0
        assert "Regression Diagnosis" in res_diff.output
        assert "Gateway timeout 504" in res_diff.output
