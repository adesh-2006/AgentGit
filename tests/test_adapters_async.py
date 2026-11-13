"""Tests for async tracking, prompt hashing, and LangChain/CrewAI adapters."""

from __future__ import annotations

import asyncio

import pytest

from agentgit.adapters.crewai_adapter import CrewAIAdapter
from agentgit.adapters.langchain_adapter import LangChainAdapter
from agentgit.tracker import AsyncTrackedAgent, compute_prompt_hash, track


@pytest.mark.asyncio
async def test_async_agent_tracking():
    @track(name="async-agent")
    async def my_async_agent(task: str) -> str:
        await asyncio.sleep(0.005)
        return f"async output: {task}"

    assert isinstance(my_async_agent, AsyncTrackedAgent)
    result = await my_async_agent("analyze data")
    assert result == "async output: analyze data"
    assert len(my_async_agent.records) == 1
    assert my_async_agent.last.latency_ms > 0
    assert my_async_agent.last.success


def test_prompt_hash_tracking():
    system_prompt = "You are an expert security researcher."
    expected_hash = compute_prompt_hash(system_prompt)

    @track(name="secure-agent", prompt=system_prompt)
    def my_agent(task: str) -> str:
        return f"reviewed: {task}"

    my_agent("audit code")
    assert my_agent.last.metadata.get("prompt_hash") == expected_hash


def test_langchain_adapter():
    class MockAIMessage:
        def __init__(self):
            self.content = "I reviewed the query."
            self.response_metadata = {
                "token_usage": {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165},
                "model_name": "gpt-4o",
            }
            self.tool_calls = [
                {"id": "call_1", "name": "sql_query", "args": {"query": "SELECT * FROM users"}}
            ]

    adapter = LangChainAdapter()
    metrics = adapter.extract_metrics(MockAIMessage())
    assert metrics["input_tokens"] == 120
    assert metrics["output_tokens"] == 45
    assert metrics["model"] == "gpt-4o"
    assert len(metrics["tools_called"]) == 1
    assert metrics["tools_called"][0].name == "sql_query"


def test_crewai_adapter():
    class MockCrewOutput:
        def __init__(self):
            class TokenUsage:
                total_tokens = 300
                prompt_tokens = 200
                completion_tokens = 100

            class TaskOut:
                tools = ["web_search", "document_reader"]

            self.token_usage = TokenUsage()
            self.tasks_output = [TaskOut()]

    adapter = CrewAIAdapter()
    metrics = adapter.extract_metrics(MockCrewOutput())
    assert metrics["total_tokens"] == 300
    assert metrics["input_tokens"] == 200
    assert len(metrics["tools_called"]) == 2
