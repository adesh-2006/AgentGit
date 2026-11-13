"""Trajectory & Metrics Exporter (agentgit export).

Exports snapshot records to CSV, JSONL, or JSON for data science,
Jupyter Notebooks, Pandas, or BI dashboards.

Usage::

    from agentgit.export import export_snapshot
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    export_snapshot(store, "v1.0", format="csv", output_path="results.csv")
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Literal

from agentgit.storage import AgentGitStore


def export_snapshot(
    store: AgentGitStore,
    version: str,
    format: Literal["csv", "jsonl", "json"] = "csv",
    output_path: str | Path | None = None,
) -> Path:
    """Export snapshot *version* to *format* at *output_path*."""
    snap = store.load(version)

    target_path = Path(output_path) if output_path else Path(f"{version}.{format}")

    if format == "csv":
        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "task_index",
                "success",
                "steps",
                "latency_ms",
                "tokens",
                "cost_usd",
                "model",
                "tools_called",
                "task_input",
                "output",
                "error",
            ])
            for i, r in enumerate(snap.task_results):
                writer.writerow([
                    i + 1,
                    r.success,
                    r.steps,
                    r.latency_ms,
                    r.tokens,
                    r.cost_usd,
                    r.model,
                    ";".join(r.tools_called),
                    str(r.task_input).replace("\n", " "),
                    str(r.output).replace("\n", " "),
                    str(r.error or ""),
                ])

    elif format == "jsonl":
        with open(target_path, "w", encoding="utf-8") as f:
            for i, r in enumerate(snap.task_results):
                row = {
                    "version": version,
                    "task_index": i + 1,
                    **r.model_dump(),
                }
                f.write(json.dumps(row, default=str) + "\n")

    elif format == "json":
        target_path.write_text(snap.model_dump_json(indent=2), encoding="utf-8")

    return target_path
