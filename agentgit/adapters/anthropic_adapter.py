"""Anthropic adapter — extracts metrics from Anthropic Message responses."""

from __future__ import annotations

from typing import Any, Dict, List

from agentgit.adapters.base import BaseAdapter
from agentgit.tracker import ToolCall


class AnthropicAdapter(BaseAdapter):
    """Extract behavioral data from Anthropic SDK responses."""

    def extract_metrics(self, result: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        if hasattr(result, "usage") and result.usage is not None:
            data["input_tokens"] = getattr(result.usage, "input_tokens", 0) or 0
            data["output_tokens"] = getattr(result.usage, "output_tokens", 0) or 0
            data["total_tokens"] = data["input_tokens"] + data["output_tokens"]

        if hasattr(result, "model"):
            data["model"] = result.model or ""

        tools: List[ToolCall] = []
        if hasattr(result, "content"):
            for block in result.content:
                if getattr(block, "type", None) == "tool_use":
                    tools.append(ToolCall(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        arguments=getattr(block, "input", {}),
                    ))
        data["tools_called"] = tools
        return data
