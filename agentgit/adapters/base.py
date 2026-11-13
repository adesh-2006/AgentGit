"""Base adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAdapter(ABC):
    """Abstract base for framework-specific result extraction."""

    @abstractmethod
    def extract_metrics(self, result: Any) -> Dict[str, Any]:
        """Extract behavioral metrics from a framework-specific result.

        Should return a dict that may contain:
        - ``input_tokens``, ``output_tokens``, ``total_tokens``
        - ``model``
        - ``tools_called`` (list of ToolCall)
        """
        ...
