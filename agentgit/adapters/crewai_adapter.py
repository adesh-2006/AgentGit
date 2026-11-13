"""CrewAI adapter — extracts metrics from CrewOutput and Agent runs."""

from __future__ import annotations

from typing import Any, Dict, List

from agentgit.adapters.base import BaseAdapter
from agentgit.tracker import ToolCall


class CrewAIAdapter(BaseAdapter):
    """Extract behavioral data from CrewAI crew and agent execution outputs."""

    def extract_metrics(self, result: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        # 1. Extract token usage from CrewOutput.token_usage
        usage = getattr(result, "token_usage", None)
        if usage:
            data["total_tokens"] = getattr(usage, "total_tokens", 0) or 0
            data["input_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
            data["output_tokens"] = getattr(usage, "completion_tokens", 0) or 0

        # 2. Extract tools and tasks
        tools: List[ToolCall] = []
        tasks = getattr(result, "tasks_output", None)
        if tasks and isinstance(tasks, list):
            for task in tasks:
                task_tools = getattr(task, "tools", []) or []
                for t in task_tools:
                    tools.append(ToolCall(
                        name=str(getattr(t, "name", t)),
                        arguments={},
                    ))

        data["tools_called"] = tools
        return data
