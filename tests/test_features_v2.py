"""Tests for V2 flagship features: mock/fixtures, lint, drift, cost, and export."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agentgit.cost import predict_production_cost
from agentgit.drift import analyze_drift
from agentgit.export import export_snapshot
from agentgit.lint import lint_prompt
from agentgit.mock import create_mock_agent, record_fixtures
from agentgit.snapshot import create_snapshot
from agentgit.storage import AgentGitStore
from agentgit.tracker import track


def _simple_agent(task: str) -> str:
    if "refund" in task.lower():
        return "Yes, your refund is approved and processed."
    return f"Processed task: {task}"


def _drifted_agent(task: str) -> str:
    if "refund" in task.lower():
        return "No, your refund is rejected and cancelled due to policy."
    return f"This is an extraordinarily long, verbose, and detailed response explaining every possible nuance of: {task}"


class TestFeaturesV2:
    def test_mock_fixtures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = track(_simple_agent)
            tasks = ["What is the refund status?", "General inquiry"]

            fixture_file = record_fixtures(agent, tasks, "test-fixture", storage_dir=tmpdir)
            assert fixture_file.exists()

            # Create mock agent from fixture
            mock = create_mock_agent("test-fixture", storage_dir=tmpdir)
            res1 = mock("What is the refund status?")
            assert "approved" in res1

            res2 = mock("General inquiry")
            assert "General inquiry" in res2

    def test_lint_prompt(self):
        bad_prompt = "You are a bot. Output only valid JSON. Include markdown bullet points and headers."
        report = lint_prompt(bad_prompt)
        assert report.warnings > 0
        assert any(i.code == "PROMPT_CONTRADICTION" for i in report.issues)
        assert report.score < 100

        good_prompt = "You are an order support bot. Keep responses under 50 words. Output JSON only."
        good_report = lint_prompt(good_prompt)
        assert good_report.score >= 80

    def test_drift_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            tasks = ["Refund request #123", "Product question"]

            snap1 = create_snapshot(track(_simple_agent), "v1.0", tasks)
            snap2 = create_snapshot(track(_drifted_agent), "v2.0", tasks)

            store.save(snap1)
            store.save(snap2)

            drift = analyze_drift(store, "v1.0", "v2.0")
            assert drift.contradiction_count >= 1
            assert len(drift.tasks) == 2
            assert any(t.contradiction_risk for t in drift.tasks)

    def test_cost_prediction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            snap = create_snapshot(track(_simple_agent), "v1.0", ["t1", "t2"])
            store.save(snap)

            forecast = predict_production_cost(store, "v1.0", dau=5000, requests_per_user=4)
            assert forecast.monthly_requests == 5000 * 4 * 30
            assert len(forecast.alternative_models) > 0
            assert forecast.recommendation != ""

    def test_export_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            snap = create_snapshot(track(_simple_agent), "v1.0", ["task A", "task B"])
            store.save(snap)

            csv_file = Path(tmpdir) / "out.csv"
            export_snapshot(store, "v1.0", format="csv", output_path=csv_file)
            assert csv_file.exists()
            assert "task_index" in csv_file.read_text(encoding="utf-8")

            jsonl_file = Path(tmpdir) / "out.jsonl"
            export_snapshot(store, "v1.0", format="jsonl", output_path=jsonl_file)
            assert jsonl_file.exists()
            assert "task_input" in jsonl_file.read_text(encoding="utf-8")
