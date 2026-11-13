"""Tests for easy installation and onboarding CLI commands (demo, quickstart)."""

import os

from click.testing import CliRunner

from agentgit.cli import cli


def test_cli_demo():
    runner = CliRunner()
    result = runner.invoke(cli, ["demo"])
    assert result.exit_code == 0
    assert "Welcome to AgentGit Demo" in result.output
    assert "Behavioral Diff" in result.output
    assert "Demo finished!" in result.output


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
