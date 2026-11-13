"""Zero-Cost Offline VCR Replay & Fixture Caching (agentgit mock).

Records real LLM and tool responses to local disk fixtures, allowing
offline, instantaneous, $0-cost regression testing in CI/CD pipelines.

Usage::

    from agentgit.mock import record_fixtures, create_mock_agent
    from agentgit.storage import AgentGitStore

    # Record once:
    record_fixtures(agent, tasks=["task1", "task2"], fixture_name="v1-fixtures")

    # Replay offline (0ms, $0 token cost):
    mock_agent = create_mock_agent("v1-fixtures")
    result = mock_agent("task1")
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from agentgit.tracker import InvocationRecord, track


class RecordedInteraction(BaseModel):
    """A cached input-output pair for offline playback."""

    input_hash: str
    task_input: Any
    output: Any
    tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    steps: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    error: Optional[str] = None


class FixtureFile(BaseModel):
    """A collection of recorded interactions for an agent."""

    name: str
    created_at: str
    interactions: Dict[str, RecordedInteraction] = Field(default_factory=dict)


def _hash_input(task_input: Any) -> str:
    """Generate deterministic SHA256 for a given input."""
    raw = json.dumps(task_input, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def record_fixtures(
    agent: Callable,
    tasks: List[Any],
    fixture_name: str,
    storage_dir: str = ".agentgit/fixtures",
) -> Path:
    """Run *agent* on *tasks* and record responses into *storage_dir*/*fixture_name*.json."""
    from datetime import datetime, timezone

    d = Path(storage_dir)
    d.mkdir(parents=True, exist_ok=True)
    out_file = d / f"{fixture_name}.json"

    interactions: Dict[str, RecordedInteraction] = {}
    tracked = track(agent, name=getattr(agent, "name", "agent"))

    for task in tasks:
        try:
            tracked(task)
            rec: InvocationRecord = tracked.last  # type: ignore[assignment]
            h = _hash_input(task)
            interactions[h] = RecordedInteraction(
                input_hash=h,
                task_input=task,
                output=rec.output,
                tools_called=[t.model_dump() for t in rec.tools_called],
                steps=rec.steps,
                input_tokens=rec.input_tokens,
                output_tokens=rec.output_tokens,
                total_tokens=rec.total_tokens,
                model=rec.model,
                error=rec.error,
            )
        except Exception as exc:
            h = _hash_input(task)
            interactions[h] = RecordedInteraction(
                input_hash=h,
                task_input=task,
                output=None,
                error=f"{type(exc).__name__}: {exc}",
            )

    ff = FixtureFile(
        name=fixture_name,
        created_at=datetime.now(timezone.utc).isoformat(),
        interactions=interactions,
    )

    out_file.write_text(ff.model_dump_json(indent=2), encoding="utf-8")
    return out_file


def create_mock_agent(
    fixture_name: str,
    storage_dir: str = ".agentgit/fixtures",
) -> Callable:
    """Load a fixture file and return a mock agent that replays recorded responses."""
    path = Path(storage_dir) / f"{fixture_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture '{fixture_name}' not found at {path}")

    data = FixtureFile.model_validate_json(path.read_text(encoding="utf-8"))

    def mock_agent(task_input: Any) -> Any:
        h = _hash_input(task_input)
        if h not in data.interactions:
            raise KeyError(
                f"No mock response recorded for input: {task_input!r} (hash {h})"
            )
        interaction = data.interactions[h]
        if interaction.error:
            raise RuntimeError(f"Mocked error: {interaction.error}")
        return interaction.output

    mock_agent.__name__ = f"mock_{fixture_name}"
    return mock_agent
