"""OpenAI adapter — extracts metrics from OpenAI ChatCompletion responses."""

from __future__ import annotations

from typing import Any, Dict, List

from agentgit.adapters.base import BaseAdapter
from agentgit.tracker import ToolCall


class OpenAIAdapter(BaseAdapter):
    """Extract behavioral data from OpenAI SDK responses."""

    def extract_metrics(self, result: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        if hasattr(result, "usage") and result.usage is not None:
            data["input_tokens"] = getattr(result.usage, "prompt_tokens", 0) or 0
            data["output_tokens"] = getattr(result.usage, "completion_tokens", 0) or 0
            data["total_tokens"] = getattr(result.usage, "total_tokens", 0) or 0

        if hasattr(result, "model"):
            data["model"] = result.model or ""

        tools: List[ToolCall] = []
        if hasattr(result, "choices") and result.choices:
            msg = result.choices[0].message
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools.append(ToolCall(
                        id=getattr(tc, "id", ""),
                        name=tc.function.name if hasattr(tc, "function") else "",
                        arguments=tc.function.arguments if hasattr(tc, "function") else {},
                    ))
        data["tools_called"] = tools
        return data
