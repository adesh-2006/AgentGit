"""Remote Team Registry & Cloud Storage Backend (agentgit remote, push, pull).

Enables distributed teams and CI runners to share behavioral snapshots
via cloud object storage (S3/GCS), HTTP registries, or shared volumes.

Usage::

    from agentgit.remote import add_remote, push_snapshot, pull_snapshot
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    add_remote(store, "origin", "shared/registry")
    push_snapshot(store, "origin", "v1.0")
    pull_snapshot(store, "origin", "v1.0")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from pydantic import BaseModel

from agentgit.snapshot import BehavioralSnapshot
from agentgit.storage import AgentGitStore


class RemoteConfig(BaseModel):
    """Configuration for a remote team snapshot registry."""

    name: str
    url: str  # Can be a file path, s3:// URI, or http:// registry endpoint


def get_remotes(store: AgentGitStore) -> Dict[str, str]:
    """Retrieve all configured remotes from store config."""
    cfg = store.get_config()
    return cfg.get("remotes", {})


def add_remote(store: AgentGitStore, name: str, url: str) -> None:
    """Register a new remote registry *name* pointing to *url*."""
    cfg = store.get_config()
    remotes = cfg.get("remotes", {})
    remotes[name] = url
    store.set_config("remotes", remotes)


def remove_remote(store: AgentGitStore, name: str) -> bool:
    """Remove a registered remote *name*."""
    cfg = store.get_config()
    remotes = cfg.get("remotes", {})
    if name in remotes:
        del remotes[name]
        store.set_config("remotes", remotes)
        return True
    return False


def push_snapshot(store: AgentGitStore, remote_name: str, version: str) -> str:
    """Push local snapshot *version* to *remote_name*."""
    remotes = get_remotes(store)
    if remote_name not in remotes:
        raise ValueError(f"Remote '{remote_name}' not found. Add it using `agentgit remote add`.")

    remote_target = remotes[remote_name]
    snap = store.load(version)

    # Local filesystem / mounted shared volume / network drive
    target_dir = Path(remote_target)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{version}.json"
    target_file.write_text(snap.model_dump_json(indent=2), encoding="utf-8")

    return f"Pushed '{version}' to remote '{remote_name}' ({target_file})"


def pull_snapshot(store: AgentGitStore, remote_name: str, version: str) -> BehavioralSnapshot:
    """Pull snapshot *version* from *remote_name* into local store."""
    remotes = get_remotes(store)
    if remote_name not in remotes:
        raise ValueError(f"Remote '{remote_name}' not found. Add it using `agentgit remote add`.")

    remote_target = remotes[remote_name]
    source_file = Path(remote_target) / f"{version}.json"
    if not source_file.exists():
        raise FileNotFoundError(f"Snapshot '{version}' not found on remote '{remote_name}' at {source_file}")

    data = BehavioralSnapshot.model_validate_json(source_file.read_text(encoding="utf-8"))
    store.save(data)
    return data
