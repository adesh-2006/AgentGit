"""LangChain adapter — extracts metrics from LangChain AIMessage and Run outputs."""

from __future__ import annotations

from typing import Any, Dict, List

from agentgit.adapters.base import BaseAdapter
from agentgit.tracker import ToolCall


class LangChainAdapter(BaseAdapter):
    """Extract behavioral data from LangChain and LangGraph responses."""

    def extract_metrics(self, result: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        # 1. Token usage from response_metadata / usage_metadata
        resp_meta = getattr(result, "response_metadata", {}) or {}
        usage = getattr(result, "usage_metadata", {}) or resp_meta.get("token_usage", {}) or {}

        if usage:
            data["input_tokens"] = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
            data["output_tokens"] = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
            data["total_tokens"] = usage.get("total_tokens", data["input_tokens"] + data["output_tokens"])

        if "model_name" in resp_meta or "model" in resp_meta:
            data["model"] = resp_meta.get("model_name") or resp_meta.get("model") or ""

        # 2. Tool calls from AIMessage.tool_calls
        tools: List[ToolCall] = []
        raw_tools = getattr(result, "tool_calls", None)
        if raw_tools and isinstance(raw_tools, list):
            for tc in raw_tools:
                if isinstance(tc, dict):
                    tools.append(ToolCall(
                        id=str(tc.get("id", "")),
                        name=str(tc.get("name", "")),
                        arguments=tc.get("args", {}) or {},
                    ))

        # Check intermediate_steps (AgentAction tuples)
        intermediate = getattr(result, "intermediate_steps", None)
        if intermediate and isinstance(intermediate, list):
            for step in intermediate:
                if isinstance(step, tuple) and len(step) >= 1:
                    action = step[0]
                    tools.append(ToolCall(
                        name=getattr(action, "tool", "unknown"),
                        arguments={"input": getattr(action, "tool_input", "")},
                    ))

        data["tools_called"] = tools
        return data
