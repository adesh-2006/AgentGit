"""Tests for OpenTelemetry export and Remote Team Registry."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agentgit.otel import export_otel_json, export_to_otel_spans
from agentgit.remote import add_remote, get_remotes, pull_snapshot, push_snapshot
from agentgit.snapshot import create_snapshot
from agentgit.storage import AgentGitStore
from agentgit.tracker import track


def _agent_fn(task: str) -> str:
    return f"Done: {task}"


class TestFutureHorizons:
    def test_otel_span_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentGitStore.init(tmpdir)
            agent = track(_agent_fn, name="otel-bot")
            snap = create_snapshot(agent, "v1.0", ["test task"])
            store.save(snap)

            spans = export_to_otel_spans(store, "v1.0")
            assert len(spans) >= 1
            root = spans[0]
            assert "trace_id" in root
            assert root["attributes"]["openinference.span.kind"] == "AGENT"
            assert "cost.usd" in root["attributes"]

            # Test JSON export
            out_file = Path(tmpdir) / "traces.json"
            export_otel_json(store, "v1.0", out_file)
            assert out_file.exists()
            content = json.loads(out_file.read_text(encoding="utf-8"))
            assert "resource_spans" in content

    def test_remote_push_and_pull(self):
        with tempfile.TemporaryDirectory() as local_dir, tempfile.TemporaryDirectory() as remote_dir:
            local_store = AgentGitStore.init(local_dir, name="local-agent")
            agent = track(_agent_fn)
            snap = create_snapshot(agent, "v1.0", ["shared task"])
            local_store.save(snap)

            # Register remote
            add_remote(local_store, "team-registry", remote_dir)
            assert "team-registry" in get_remotes(local_store)

            # Push to remote
            msg = push_snapshot(local_store, "team-registry", "v1.0")
            assert "Pushed" in msg
            assert (Path(remote_dir) / "v1.0.json").exists()

            # Create another fresh local store and pull from remote
            with tempfile.TemporaryDirectory() as new_local:
                another_store = AgentGitStore.init(new_local, name="teammate-agent")
                add_remote(another_store, "team-registry", remote_dir)
                pulled = pull_snapshot(another_store, "team-registry", "v1.0")
                assert pulled.version == "v1.0"
                assert another_store.exists("v1.0")
