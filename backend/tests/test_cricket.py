"""Unit and integration tests for CricAPI cricket score proxy endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
import httpx

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.api.v1.cricket import reset_cricket_cache

@pytest.fixture(autouse=True)
def clean_cricket_cache():
    reset_cricket_cache()
    with patch.object(settings, "CRICAPI_KEY1", None), \
         patch.object(settings, "CRICAPI_KEY2", None), \
         patch.object(settings, "CRICAPI_KEY3", None), \
         patch.object(settings, "CRICAPI_KEYS", None):
        yield
    reset_cricket_cache()

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

@pytest.mark.asyncio
async def test_cricket_all_and_matches_endpoints():
    """Both /api/v1/cricket/all and /api/v1/cricket/matches return full match list."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = MOCK_CRICAPI_SUCCESS

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # Test /api/v1/cricket/all
                res_all = await ac.get("/api/v1/cricket/all")
                assert res_all.status_code == 200
                data_all = res_all.json()
                assert data_all["status"] == "success"
                assert len(data_all["matches"]) == 1

                # Test /api/v1/cricket/matches
                res_matches = await ac.get("/api/v1/cricket/matches")
                assert res_matches.status_code == 200
                data_matches = res_matches.json()
                assert data_matches["status"] == "success"
                assert len(data_matches["matches"]) == 1

                # Test root alias /api/cricket/all
                res_alias = await ac.get("/api/cricket/all")
                assert res_alias.status_code == 200
                assert res_alias.json()["status"] == "success"

@pytest.mark.asyncio
async def test_cricket_force_refresh_and_rate_limit_fallback():
    """Verify forced refresh bypasses cache and rate limit 'Blocked for 15 minutes' falls back gracefully."""
    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            # First call populates cache
            mock_query.return_value = MOCK_CRICAPI_SUCCESS
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res1 = await ac.get("/api/v1/cricket/scores?force=true")
                assert res1.status_code == 200
                assert res1.json()["status"] == "success"

                # Second call encounters CricAPI rate limit
                mock_query.return_value = {
                    "apikey": "key",
                    "status": "failure",
                    "reason": "Blocked for 15 minutes"
                }
                res2 = await ac.get("/api/v1/cricket/scores?force=true")
                assert res2.status_code == 200
                data2 = res2.json()
                # Returns cached matches so UI doesn't break
                assert data2["status"] == "success"
                assert len(data2["matches"]) == 1
                assert "rate-limit" in data2["message"].lower()

@pytest.mark.asyncio
async def test_cricket_match_scorecard_endpoints():
    """Detailed match scorecard can be retrieved by path and query parameters."""
    mock_scorecard_data = {
        "status": "success",
        "data": {
            "id": "match-uuid-001",
            "name": "India vs Australia, 1st T20I",
            "status": "India won by 5 wickets",
            "venue": "Wankhede Stadium, Mumbai",
            "date": "2026-10-25",
            "teams": ["India", "Australia"],
            "scorecard": [
                {
                    "inning": "Australia Inning 1",
                    "r": 178,
                    "w": 6,
                    "o": 20.0,
                    "batting": [
                        {
                            "batsman": {"name": "David Warner"},
                            "r": 54,
                            "b": 38,
                            "4s": 6,
                            "6s": 2,
                            "sr": 142.1,
                            "dismissal-text": "c Rohit b Bumrah"
                        }
                    ],
                    "bowling": [
                        {
                            "bowler": {"name": "Jasprit Bumrah"},
                            "o": 4.0,
                            "m": 1,
                            "r": 24,
                            "w": 3,
                            "eco": 6.0
                        }
                    ]
                }
            ]
        }
    }

    with patch.object(settings, "CRICAPI_KEY", "mock-valid-key"):
        with patch("backend.app.api.v1.cricket.query_cricapi_raw", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_scorecard_data
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # 1. By path
                res_path = await ac.get("/api/v1/cricket/scorecard/match-uuid-001")
                assert res_path.status_code == 200
                data = res_path.json()
                assert data["status"] == "success"
                assert data["match_id"] == "match-uuid-001"
                assert len(data["innings"]) == 1
                assert data["innings"][0]["batsmen"][0]["name"] == "David Warner"
                assert data["innings"][0]["bowlers"][0]["name"] == "Jasprit Bumrah"

                # 2. By query parameter
                res_query = await ac.get("/api/v1/cricket/scorecard?id=match-uuid-001")
                assert res_query.status_code == 200
                assert res_query.json()["match_id"] == "match-uuid-001"

@pytest.mark.asyncio
async def test_cricket_key_rotation_on_rate_limit():
    """When a CricAPI key is rate-limited, the system automatically rotates to the next available key."""
    # Configure 3 keys
    with patch.object(settings, "CRICAPI_KEY1", "key-one-alpha"), \
         patch.object(settings, "CRICAPI_KEY2", "key-two-beta"), \
         patch.object(settings, "CRICAPI_KEY3", "key-three-gamma"):

        calls = []

        async def mock_query(url, params):
            key = params.get("apikey")
            calls.append(key)
            if key == "key-one-alpha":
                # First key encounters CricAPI rate limit
                return {
                    "apikey": key,
                    "status": "failure",
                    "reason": "Blocked for 15 minutes"
                }
            elif key == "key-two-beta":
                # Second key succeeds
                return MOCK_CRICAPI_SUCCESS
            return {"status": "failure", "reason": "unexpected key"}

        with patch("backend.app.api.v1.cricket.query_cricapi_raw", side_effect=mock_query):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # 1. First call should attempt key-one, detect block, and rotate to key-two
                res = await ac.get("/api/v1/cricket/scores?force=true")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                assert len(data["matches"]) == 1
                assert calls == ["key-one-alpha", "key-two-beta"]

                # 2. Subsequent call within cooldown should skip key-one and use key-two directly
                calls.clear()
                res2 = await ac.get("/api/v1/cricket/scores?force=true")
                assert res2.status_code == 200
                assert calls == ["key-two-beta"]

@pytest.mark.asyncio
async def test_cricket_key_rotation_all_keys_exhausted():
    """When all configured keys are rate-limited, endpoint returns safe notice or fallback."""
    with patch.object(settings, "CRICAPI_KEY1", "key-one-exhausted"), \
         patch.object(settings, "CRICAPI_KEY2", "key-two-exhausted"):

        async def mock_exhausted_query(url, params):
            return {
                "apikey": params.get("apikey"),
                "status": "failure",
                "reason": "Blocked for 15 minutes"
            }

        with patch("backend.app.api.v1.cricket.query_cricapi_raw", side_effect=mock_exhausted_query):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/cricket/scores?force=true")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "error"
                assert "rate-limited" in data["message"]
                assert data["matches"] == []



