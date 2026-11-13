"""Generic adapter — fallback for plain callables."""

from __future__ import annotations

from typing import Any, Dict

from agentgit.adapters.base import BaseAdapter


class GenericAdapter(BaseAdapter):
    """Fallback adapter that extracts no framework-specific metrics."""

    def extract_metrics(self, result: Any) -> Dict[str, Any]:
        return {}
