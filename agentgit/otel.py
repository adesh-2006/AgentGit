"""OpenTelemetry & OpenInference Trace Exporter (agentgit otel).

Exports snapshot trajectories and tool calls into standard OpenTelemetry (OTel)
and OpenInference semantic convention span hierarchies for ingestion by
Jaeger, Datadog, Honeycomb, Arize Phoenix, or any OTLP collector.

Usage::

    from agentgit.otel import export_to_otel_spans
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    spans = export_to_otel_spans(store, "v1.0")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agentgit.storage import AgentGitStore


class OTelSpan(BaseModel):
    """An OpenTelemetry-compliant trace span for an agent step."""

    trace_id: str
    span_id: str
    parent_span_id: str = ""
    name: str
    kind: str = "SPAN_KIND_INTERNAL"
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: Dict[str, Any] = Field(default_factory=dict)
    status: Dict[str, str] = Field(default_factory=lambda: {"code": "STATUS_CODE_OK"})


def export_to_otel_spans(store: AgentGitStore, version: str) -> List[Dict[str, Any]]:
    """Convert snapshot *version* into OpenInference/OTel trace spans."""
    snap = store.load(version)

    spans: List[OTelSpan] = []
    base_nano = int(snap.timestamp.timestamp() * 1_000_000_000)

    for idx, task in enumerate(snap.task_results):
        trace_id = f"trace_{version}_{idx + 1:04d}".replace(".", "_")
        root_span_id = f"span_root_{idx + 1:04d}"

        duration_nano = int(task.latency_ms * 1_000_000)
        start_nano = base_nano + (idx * 2_000_000_000)
        end_nano = start_nano + duration_nano

        status_code = "STATUS_CODE_OK" if task.success else "STATUS_CODE_ERROR"

        # Root Agent Span
        root_span = OTelSpan(
            trace_id=trace_id,
            span_id=root_span_id,
            name=f"agent.run:{snap.agent_name or 'agent'}",
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            status={"code": status_code, "message": task.error or ""},
            attributes={
                "openinference.span.kind": "AGENT",
                "agent.version": version,
                "agent.task_index": idx + 1,
                "input.value": json.dumps(task.task_input, default=str),
                "output.value": json.dumps(task.output, default=str),
                "llm.token_count.total": task.tokens,
                "llm.model_name": task.model or "unknown",
                "cost.usd": task.cost_usd,
            },
        )
        spans.append(root_span)

        # Child Tool Spans
        for tool_idx, tool_name in enumerate(task.tools_called):
            tool_start = start_nano + (tool_idx * 50_000_000)
            tool_end = tool_start + 40_000_000
            child_span = OTelSpan(
                trace_id=trace_id,
                span_id=f"span_tool_{idx + 1}_{tool_idx + 1}",
                parent_span_id=root_span_id,
                name=f"tool.call:{tool_name}",
                start_time_unix_nano=tool_start,
                end_time_unix_nano=tool_end,
                attributes={
                    "openinference.span.kind": "TOOL",
                    "tool.name": tool_name,
                    "tool.execution_order": tool_idx + 1,
                },
            )
            spans.append(child_span)

    return [s.model_dump() for s in spans]


def export_otel_json(store: AgentGitStore, version: str, output_path: str | Path) -> Path:
    """Save OTel spans to JSON file at *output_path*."""
    spans = export_to_otel_spans(store, version)
    out = Path(output_path)
    out.write_text(json.dumps({"resource_spans": spans}, indent=2), encoding="utf-8")
    return out
