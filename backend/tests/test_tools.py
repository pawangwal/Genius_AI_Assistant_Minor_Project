"""Tests for Tool Registry schemas and concrete tool handler execution."""
import pytest
import pytest_asyncio
from backend.app.tools.registry import tool_registry

@pytest.mark.asyncio
async def test_tool_registry_schemas():
    """All required tools are defined in the schema registry."""
    names = [s["function"]["name"] for s in tool_registry.schemas]
    assert "predict_ipl_match" in names
    assert "create_task" in names
    assert "list_tasks" in names
    assert "create_reminder" in names
    assert "list_reminders" in names
    assert "search_web" not in names

@pytest.mark.asyncio
async def test_tool_execute_predict_ipl(test_db):
    """predict_ipl_match tool executes safely via registry."""
    args = {
        "batting_team": "Chennai Super Kings",
        "bowling_team": "Mumbai Indians",
        "city": "Chennai",
        "target_score": 170,
        "current_score": 110,
        "overs_completed": 13,
        "balls_in_over": 0,
        "wickets_out": 2
    }
    result = await tool_registry.execute("predict_ipl_match", args, test_db, "user-test")
    assert result["status"] == "success"
    assert "batting_win_probability" in result
    assert result["batting_team"] == "Chennai Super Kings"

@pytest.mark.asyncio
async def test_tool_execute_task_crud(test_db):
    """create_task and list_tasks tools persist and retrieve correctly."""
    # Create task
    create_res = await tool_registry.execute(
        "create_task",
        {"title": "Review match data", "category": "ml"},
        test_db,
        "user-test"
    )
    assert create_res["status"] == "success"
    assert "task_id" in create_res

    # List tasks
    list_res = await tool_registry.execute("list_tasks", {}, test_db, "user-test")
    assert list_res["status"] == "success"
    assert list_res["count"] == 1
    assert list_res["tasks"][0]["title"] == "Review match data"

@pytest.mark.asyncio
async def test_tool_execute_search_web_rejected(test_db):
    """search_web is rejected to guarantee zero egress policy."""
    result = await tool_registry.execute(
        "search_web",
        {"query": "IPL 2026 points table"},
        test_db,
        "user-test"
    )
    assert result["status"] == "error"
    assert "not recognized or permitted" in result["message"]

@pytest.mark.asyncio
async def test_tool_execute_unknown_tool(test_db):
    """Unknown or unpermitted tools fail safely without throwing exceptions."""
    result = await tool_registry.execute("arbitrary_command", {}, test_db, "user-test")
    assert result["status"] == "error"
    assert "not recognized" in result["message"]

@pytest.mark.asyncio
async def test_tool_execute_database_exception_sanitized():
    """Database exceptions in tool handlers return generic client-safe messages with zero SQL leak."""
    from unittest.mock import AsyncMock
    from sqlalchemy.exc import OperationalError

    failing_db = AsyncMock()
    failing_db.get = AsyncMock(
        side_effect=OperationalError("SELECT failed", {}, Exception("Database connection lost! Host=10.0.0.1, User=secret_admin"))
    )
    failing_db.rollback = AsyncMock()

    # Create task failure
    task_res = await tool_registry.execute(
        "create_task",
        {"title": "Confidential Task"},
        failing_db,
        "user-test"
    )
    assert task_res["status"] == "error"
    assert task_res["message"] == "Failed to persist task due to a storage error. Please retry."
    # Assert zero internal exception leak
    assert "Database connection lost" not in task_res["message"]
    assert "secret_admin" not in task_res["message"]
    assert "OperationalError" not in task_res["message"]

    # List tasks failure
    failing_db.execute = AsyncMock(
        side_effect=OperationalError("SELECT failed", {}, Exception("Internal query failure"))
    )
    list_res = await tool_registry.execute(
        "list_tasks",
        {},
        failing_db,
        "user-test"
    )
    assert list_res["status"] == "error"
    assert list_res["message"] == "Failed to query tasks due to a storage error. Please retry."
    assert "Internal query failure" not in list_res["message"]
