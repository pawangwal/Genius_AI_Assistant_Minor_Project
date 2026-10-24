"""Live integration tests for OpenRouter using configured free model and tool execution."""
import pytest
from backend.app.core.config import settings
from backend.app.services.openrouter_provider import OpenRouterProvider, LLMError
from backend.app.tools.schemas import TOOL_SCHEMAS

# Skip live tests if running in headless CI without OPENROUTER_API_KEY
pytestmark = pytest.mark.skipif(
    not settings.OPENROUTER_API_KEY or not settings.OPENROUTER_API_KEY.strip(),
    reason="Live OpenRouter tests require OPENROUTER_API_KEY to be set in .env"
)

@pytest.mark.asyncio
async def test_openrouter_free_model_enforcement():
    """Verifies that the configured OpenRouter model strictly uses a free tier model."""
    provider = OpenRouterProvider()
    assert provider.model.endswith(":free"), f"Configured model '{provider.model}' must be an OpenRouter :free model"

@pytest.mark.asyncio
async def test_openrouter_live_availability_and_authentication():
    """Live probe to OpenRouter verifying key authenticity and connectivity."""
    provider = OpenRouterProvider()
    status = await provider.check_availability(force_refresh=True)
    assert status["configured"] is True
    assert status["reachable"] is True
    assert status["authenticated"] is True
    assert "authenticated" in status["detail"].lower()

@pytest.mark.asyncio
async def test_openrouter_live_tool_calling_execution():
    """Live test verifying that OpenRouter free model emits tool call and processes multi-turn result."""
    provider = OpenRouterProvider()

    # Turn 1: User asks to list tasks
    messages = [
        {"role": "system", "content": "You are Genius AI Assistant. Use tools when requested."},
        {"role": "user", "content": "Please retrieve my current tasks."}
    ]

    response = await provider.chat(messages=messages, tools=TOOL_SCHEMAS)
    message = response.get("message", {})
    tool_calls = message.get("tool_calls", [])

    assert bool(tool_calls), "Model should have called a tool for task listing"
    tool_name = tool_calls[0]["function"]["name"]
    assert tool_name in ("list_tasks", "create_task")

    # Turn 2: Provide simulated tool output back to model
    messages.append(message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_calls[0].get("id", "call_123"),
        "name": tool_name,
        "content": '{"tasks": [{"id": 1, "title": "Buy milk", "completed": false}]}'
    })

    followup_resp = await provider.chat(messages=messages, tools=TOOL_SCHEMAS)
    followup_msg = followup_resp.get("message", {})
    # Either returns direct answer or another tool call
    assert followup_msg.get("content") is not None or followup_msg.get("tool_calls") is not None

@pytest.mark.asyncio
async def test_agent_orchestrator_live_complete_tool_execution(test_db):
    """End-to-end live test verifying that AgentOrchestrator invokes real local tool registry
    against real PostgreSQL session and streams SSE events to completion.
    """
    from backend.app.services.agent import agent_orchestrator
    from backend.app.tools.handlers import handle_create_task

    # Pre-seed a harmless task into PostgreSQL for user-live-test
    await handle_create_task({"title": "Live E2E Verification Task", "category": "test"}, test_db, "user-live-test")

    messages = [
        {"role": "user", "content": "Please retrieve my current tasks."}
    ]

    events = []
    async for chunk in agent_orchestrator.run_stream(messages, test_db, "user-live-test"):
        events.append(chunk)

    full_stream = "".join(events)
    # 1. Verify SSE event: tool_call was emitted
    assert "event: tool_call" in full_stream, f"Expected event: tool_call in stream, got:\n{full_stream}"
    # 2. Verify SSE event: tool_result was emitted by local tool registry
    assert "event: tool_result" in full_stream, f"Expected event: tool_result in stream, got:\n{full_stream}"
    assert "Live E2E Verification Task" in full_stream or "list_tasks" in full_stream
    # 3. Verify final answer was streamed via SSE token events
    assert "event: token" in full_stream
    # 4. Verify stream concluded with done event
    assert "event: done" in full_stream

@pytest.mark.asyncio
async def test_openrouter_invalid_api_key_error_handling():
    """Verifies that an invalid API key returns a structured LLMError without exposing raw exception traces."""
    bad_provider = OpenRouterProvider(api_key="invalid_dummy_key_for_testing")
    with pytest.raises(LLMError) as exc_info:
        await bad_provider.chat(messages=[{"role": "user", "content": "Hi"}])
    assert "error" in str(exc_info.value).lower() or "authentication" in str(exc_info.value).lower()

