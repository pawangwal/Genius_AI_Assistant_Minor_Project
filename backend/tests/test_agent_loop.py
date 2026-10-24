"""Tests for bounded agent orchestrator loop, tool execution, and SSE event streaming."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.app.services.agent import AgentOrchestrator
from backend.app.services.openrouter_provider import LLMConnectionError

@pytest.mark.asyncio
async def test_agent_direct_response():
    """Agent yields text tokens and completes when model returns no tool calls."""
    orchestrator = AgentOrchestrator(max_iterations=5)
    mock_response = {
        "message": {
            "role": "assistant",
            "content": "Hello! I am Genius, your AI assistant."
        }
    }

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.agent.get_active_llm_provider", return_value=mock_provider):
        events = []
        async for chunk in orchestrator.run_stream([{"role": "user", "content": "Hi"}], None, "user-test"):
            events.append(chunk)

        full_output = "".join(events)
        assert "event: token" in full_output
        assert "event: done" in full_output
        assert "Hello! I am Genius" in full_output

@pytest.mark.asyncio
async def test_agent_tool_calling_and_summary():
    """Agent executes tool call and uses result in subsequent reasoning iteration."""
    orchestrator = AgentOrchestrator(max_iterations=5)

    # Iteration 1: Model calls create_task tool
    step1_response = {
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "list_tasks",
                        "arguments": {}
                    }
                }
            ]
        }
    }

    # Iteration 2: Model returns natural language summary
    step2_response = {
        "message": {
            "role": "assistant",
            "content": "Here are your current active tasks."
        }
    }

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(side_effect=[step1_response, step2_response])

    with patch("backend.app.services.agent.get_active_llm_provider", return_value=mock_provider):
        events = []
        async for chunk in orchestrator.run_stream([{"role": "user", "content": "Show my tasks"}], None, "user-test"):
            events.append(chunk)

        full_output = "".join(events)
        assert "event: tool_call" in full_output
        assert "event: tool_result" in full_output
        assert "event: token" in full_output
        assert "event: done" in full_output
        assert "list_tasks" in full_output

@pytest.mark.asyncio
async def test_agent_iteration_limit_enforced():
    """Agent terminates strictly when reaching max_iterations without infinite looping."""
    orchestrator = AgentOrchestrator(max_iterations=2)

    # Model continuously requests tool calls
    infinite_tool_response = {
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_loop",
                    "function": {
                        "name": "list_tasks",
                        "arguments": {}
                    }
                }
            ]
        }
    }

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(return_value=infinite_tool_response)

    with patch("backend.app.services.agent.get_active_llm_provider", return_value=mock_provider):
        events = []
        async for chunk in orchestrator.run_stream([{"role": "user", "content": "Loop"}], None, "user-test"):
            events.append(chunk)

        full_output = "".join(events)
        assert "max_iterations_reached" in full_output

@pytest.mark.asyncio
async def test_agent_ollama_unreachable_emits_error():
    """Agent yields error event if AI provider is unreachable."""
    orchestrator = AgentOrchestrator(max_iterations=5)

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(side_effect=LLMConnectionError("AI service endpoint unreachable."))

    with patch("backend.app.services.agent.get_active_llm_provider", return_value=mock_provider):
        events = []
        async for chunk in orchestrator.run_stream([{"role": "user", "content": "Hello"}], None, "user-test"):
            events.append(chunk)

        full_output = "".join(events)
        assert "event: error" in full_output
        assert "unreachable" in full_output.lower()
