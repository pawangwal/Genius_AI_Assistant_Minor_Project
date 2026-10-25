"""Unit and integration tests for CricAPI cricket score proxy endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
import httpx

from backend.app.main import app
from backend.app.core.config import settings

MOCK_CRICAPI_SUCCESS = {
    "apikey": "secret-key-12345",
    "data": [
        {
            "id": "match-uuid-001",
            "name": "India vs Australia, 1st T20I",
            "matchType": "t20",
            "status": "India won by 5 wickets",
            "venue": "Wankhede Stadium, Mumbai",
            "date": "2026-10-25",
            "dateTimeGMT": "2026-10-25T14:00:00",
            "teams": ["India", "Australia"],
            "score": [
                {"r": 178, "w": 6, "o": 20.0, "inning": "Australia Inning 1"},
                {"r": 182, "w": 5, "o": 19.2, "inning": "India Inning 1"}
            ],
            "matchEnded": True
        }
    ],
    "status": "success",
    "info": {"hitsToday": 5, "hitsUsed": 5}
}

MOCK_CRICAPI_EMPTY = {
    "apikey": "secret-key-12345",
    "data": [],
    "status": "success"
}

MOCK_CRICAPI_FAILURE = {
    "apikey": "secret-key-12345",
    "status": "failure",
    "reason": "Invalid API key"
}

@pytest.mark.asyncio
async def test_cricket_scores_missing_key():
    """When CRICAPI_KEY is unset, the endpoint returns a safe error message without crashing."""
    with patch.object(settings, "CRICAPI_KEY", None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/cricket/scores")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "error"
            assert "CricAPI key is not configured" in data["message"]
            assert data["matches"] == []

@pytest.mark.asyncio
async def test_cricket_scores_success_parsed():
    """When CricAPI returns matches, fields are sanitized and structured properly."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = MOCK_CRICAPI_SUCCESS

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/cricket/scores")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                assert len(data["matches"]) == 1
                match = data["matches"][0]
                assert match["id"] == "match-uuid-001"
                assert match["name"] == "India vs Australia, 1st T20I"
                assert match["teams"] == ["India", "Australia"]
                assert match["match_type"] == "T20"
                assert match["match_ended"] is True
                assert len(match["scores"]) == 2
                assert match["scores"][0]["runs"] == 178
                assert match["scores"][0]["wickets"] == 6
                # Verify secret key never leaks into response JSON
                assert "secret-key-12345" not in res.text
                assert "mock-valid-key" not in res.text

@pytest.mark.asyncio
async def test_cricket_scores_alias_route():
    """Verify that the /api/cricket/scores alias route functions identically."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = MOCK_CRICAPI_SUCCESS

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cricket/scores")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                assert len(data["matches"]) == 1

@pytest.mark.asyncio
async def test_cricket_scores_empty_matches():
    """When no matches are in progress, status is 'empty' with user-friendly message."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = MOCK_CRICAPI_EMPTY

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/cricket/scores")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "empty"
                assert "No live matches" in data["message"]
                assert data["matches"] == []

@pytest.mark.asyncio
async def test_cricket_scores_upstream_timeout():
    """Network timeout gracefully returns error status without crashing."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", side_effect=httpx.TimeoutException("Timeout")):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/cricket/scores")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "error"
                assert "timed out" in data["message"].lower()

@pytest.mark.asyncio
async def test_cricket_scores_upstream_failure_response():
    """Upstream API failure returns graceful error and doesn't leak internal details."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = MOCK_CRICAPI_FAILURE

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/cricket/scores")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "error"
                assert "secret-key-12345" not in res.text
