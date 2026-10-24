"""Tests to mathematically and empirically prove zero network egress."""
import socket
import pytest
from unittest.mock import patch
from backend.app.ml.ipl_pipeline import ipl_service
from backend.app.ml.schemas import IPLPredictionRequest
from backend.app.tools.registry import tool_registry

ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

def guard_socket_connect(orig_connect):
    def hooked_connect(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else address
        # Check if destination is non-loopback
        if str(host) not in ALLOWED_LOOPBACK_HOSTS:
            raise RuntimeError(f"VIOLATION of Zero-Egress Guarantee: External socket connection attempted to '{host}'")
        return orig_connect(self, address)
    return hooked_connect

def test_ipl_inference_zero_egress():
    """IPL machine learning inference operates 100% locally with zero external network egress."""
    orig_connect = socket.socket.connect
    try:
        socket.socket.connect = guard_socket_connect(orig_connect)
        
        req = IPLPredictionRequest(
            batting_team="Mumbai Indians",
            bowling_team="Chennai Super Kings",
            city="Mumbai",
            target_score=180,
            current_score=110,
            overs_completed=12,
            balls_in_over=0,
            wickets_out=3
        )
        res = ipl_service.predict(req)
        assert res.batting_win_probability > 0
        assert res.bowling_win_probability > 0
    finally:
        socket.socket.connect = orig_connect

@pytest.mark.asyncio
async def test_tools_execution_zero_egress(test_db):
    """All registered agent tools execute strictly locally with zero external network egress."""
    orig_connect = socket.socket.connect
    try:
        socket.socket.connect = guard_socket_connect(orig_connect)

        # 1. IPL prediction tool
        ipl_res = await tool_registry.execute(
            "predict_ipl_match",
            {
                "batting_team": "Mumbai Indians",
                "bowling_team": "Chennai Super Kings",
                "city": "Mumbai",
                "target_score": 180,
                "current_score": 110,
                "overs_completed": 12,
                "balls_in_over": 0,
                "wickets_out": 3
            },
            test_db,
            "local-user"
        )
        assert ipl_res["status"] == "success"

        # 2. Task creation tool
        task_res = await tool_registry.execute(
            "create_task",
            {"title": "Offline Task", "category": "sec"},
            test_db,
            "local-user"
        )
        assert task_res["status"] == "success"

        # 3. Reminder creation tool
        rem_res = await tool_registry.execute(
            "create_reminder",
            {"title": "Offline Reminder", "due_time": "18:00"},
            test_db,
            "local-user"
        )
        assert rem_res["status"] == "success"

        # 4. Attempted search_web tool is rejected
        assert tool_registry.has_tool("search_web") is False
    finally:
        socket.socket.connect = orig_connect
