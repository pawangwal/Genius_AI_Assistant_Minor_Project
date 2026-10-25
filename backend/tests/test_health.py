"""Tests for liveness and readiness health probes."""
import pytest
from unittest.mock import patch
from backend.app.ml.ipl_pipeline import ipl_service

@pytest.mark.asyncio
async def test_liveness_probe(async_client):
    """Liveness probe must return 200 OK unconditionally."""
    resp = await async_client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}

@pytest.mark.asyncio
async def test_readiness_probe_all_healthy(async_client):
    """Readiness probe returns 200 when database and model are healthy."""
    with patch("backend.app.api.v1.health.check_database_health", return_value=(True, "connected")):
        resp = await async_client.get("/api/v1/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["database"] == "connected"
        assert data["dependencies"]["ipl_model"] == "loaded"

@pytest.mark.asyncio
async def test_readiness_probe_db_failure(async_client):
    """Readiness probe must fail-fast with HTTP 503 if database is unreachable (no silent fallback)."""
    with patch("backend.app.api.v1.health.check_database_health", return_value=(False, "Connection refused")):
        resp = await async_client.get("/api/v1/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unready"
        assert "unreachable" in data["dependencies"]["database"]

@pytest.mark.asyncio
async def test_readiness_probe_schema_unmigrated(async_client):
    """Readiness probe returns 503 if database is online but Alembic migrations are missing."""
    with patch(
        "backend.app.api.v1.health.check_database_health",
        return_value=(False, "Uninitialized schema (missing tables: reminders, tasks, users). Run alembic upgrade head.")
    ):
        resp = await async_client.get("/api/v1/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unready"
        assert "Uninitialized schema" in data["dependencies"]["database"]

@pytest.mark.asyncio
async def test_readiness_probe_model_unloaded(async_client):
    """Readiness probe must return 503 if ML model artifact is unloaded."""
    with patch("backend.app.api.v1.health.check_database_health", return_value=(True, "connected")):
        with patch.object(ipl_service, "_is_loaded", False):
            resp = await async_client.get("/api/v1/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unready"
            assert data["dependencies"]["ipl_model"] == "unloaded"

@pytest.mark.asyncio
async def test_network_health_probe_openrouter_connected(async_client):
    """Network probe returns connected status when OpenRouter is authenticated."""
    mock_avail = {
        "configured": True,
        "reachable": True,
        "authenticated": True,
        "model": "nvidia/nemotron-3.5-lightning:free",
        "detail": "OpenRouter authenticated and available."
    }
    with patch("backend.app.services.openrouter_provider.openrouter_provider.check_availability", return_value=mock_avail):
        resp = await async_client.get("/api/v1/health/network")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fastapi"] == "online"
        assert data["provider"] == "openrouter"
        assert data["status"] == "connected"
        assert "OpenRouter connected" in data["detail"]

@pytest.mark.asyncio
async def test_network_health_probe_ollama_offline(async_client):
    """Network probe returns offline status when Ollama daemon is unreachable."""
    with patch("backend.app.core.config.settings.LLM_PROVIDER", "ollama"):
        with patch("backend.app.services.ollama_provider.ollama_provider.check_health", return_value=False):
            resp = await async_client.get("/api/v1/health/network")
            assert resp.status_code == 200
            data = resp.json()
            assert data["fastapi"] == "online"
            assert data["provider"] == "ollama"
            assert data["status"] == "offline"
            assert "unreachable" in data["detail"].lower()

