"""Local storage manager for AgentGit snapshots and configuration.

Manages the ``.agentgit/`` directory tree::

    .agentgit/
    ├── config.json
    ├── snapshots/
    │   ├── v1.0.json
    │   └── v2.0.json
    └── db.sqlite   (metadata index — reserved for future use)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentgit.snapshot import (
    BehavioralSnapshot,
    load_snapshot,
    list_snapshots,
    save_snapshot,
)


_AGENTGIT_DIR = ".agentgit"
_CONFIG_FILE = "config.json"
_SNAPSHOTS_DIR = "snapshots"

_DEFAULT_CONFIG = {
    "agent_name": "my-agent",
    "created_at": "",
    "current_version": None,
}


class AgentGitStore:
    """Manages AgentGit project state on the local filesystem.

    Parameters
    ----------
    project_path : str or Path
        Root directory of the project (where ``.agentgit/`` lives).
    """

    def __init__(self, project_path: str | Path = ".") -> None:
        self.root = Path(project_path).resolve()
        self.agdir = self.root / _AGENTGIT_DIR
        self.snapshots_dir = self.agdir / _SNAPSHOTS_DIR
        self.config_path = self.agdir / _CONFIG_FILE

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    @classmethod
    def init(cls, project_path: str | Path = ".", name: str = "my-agent") -> "AgentGitStore":
        """Create a new ``.agentgit/`` directory tree.

        Returns the initialised store.
        """
        store = cls(project_path)
        store.agdir.mkdir(parents=True, exist_ok=True)
        store.snapshots_dir.mkdir(exist_ok=True)

        config = {
            **_DEFAULT_CONFIG,
            "agent_name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return store

    @property
    def is_initialised(self) -> bool:
        return self.agdir.exists() and self.config_path.exists()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def get_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return dict(_DEFAULT_CONFIG)
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def set_config(self, key: str, value: Any) -> None:
        cfg = self.get_config()
        cfg[key] = value
        self.config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Snapshot CRUD
    # ------------------------------------------------------------------

    def save(self, snapshot: BehavioralSnapshot) -> Path:
        """Persist a snapshot and update ``current_version``."""
        path = save_snapshot(snapshot, self.snapshots_dir)
        self.set_config("current_version", snapshot.version)
        return path

    def load(self, version: str) -> BehavioralSnapshot:
        return load_snapshot(version, self.snapshots_dir)

    def list(self) -> List[BehavioralSnapshot]:
        return list_snapshots(self.snapshots_dir)

    def list_summary(self) -> List[Dict[str, Any]]:
        """Return lightweight summary dicts for every snapshot."""
        return [
            {
                "version": s.version,
                "timestamp": s.timestamp.isoformat(),
                "num_tasks": s.num_tasks,
                "completion": f"{s.metrics.task_completion_rate:.0%}",
                "error_rate": f"{s.metrics.error_rate:.0%}",
                "avg_cost": f"${s.metrics.avg_cost_per_task:.4f}",
            }
            for s in self.list()
        ]

    def delete(self, version: str) -> bool:
        path = self.snapshots_dir / f"{version}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def get_current_version(self) -> Optional[str]:
        return self.get_config().get("current_version")

    def exists(self, version: str) -> bool:
        return (self.snapshots_dir / f"{version}.json").exists()
