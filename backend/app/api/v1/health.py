"""Health check endpoints: liveness and dependency readiness probes."""
from fastapi import APIRouter, status, Response
from backend.app.core.database import check_database_health
from backend.app.ml.ipl_pipeline import ipl_service

router = APIRouter(prefix="/health", tags=["Health & Readiness"])

@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Liveness probe: returns 200 OK as long as the application process is running."""
    return {"status": "alive"}

@router.get("/ready")
async def readiness_probe(response: Response):
    """Readiness probe: validates downstream dependencies (PostgreSQL and ML artifact).
    
    Returns HTTP 200 if all components are ready, or HTTP 503 if any required
    dependency is degraded or unreachable.
    """
    db_ok, db_msg = await check_database_health()
    model_ok = ipl_service.is_ready

    all_ready = db_ok and model_ok

    payload = {
        "status": "ready" if all_ready else "unready",
        "dependencies": {
            "database": "connected" if db_ok else f"unreachable ({db_msg})",
            "ipl_model": "loaded" if model_ok else "unloaded"
        }
    }

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return payload


@router.get("/network", status_code=status.HTTP_200_OK)
async def network_health_probe():
    """Returns real-time network and active LLM provider connectivity status.
    
    Safe payload containing provider name, connection state (connected, checking, degraded, offline),
    and descriptive message. Never leaks keys, tokens, or raw response headers.
    """
    from backend.app.core.config import settings
    from backend.app.services.ollama_provider import ollama_provider
    from backend.app.services.openrouter_provider import openrouter_provider

    provider_name = settings.LLM_PROVIDER.lower()
    
    if provider_name == "ollama":
        is_up = await ollama_provider.check_health()
        if is_up:
            return {
                "fastapi": "online",
                "provider": "ollama",
                "status": "connected",
                "detail": f"Local Ollama online ({settings.OLLAMA_CHAT_MODEL})",
                "model": settings.OLLAMA_CHAT_MODEL,
            }
        else:
            return {
                "fastapi": "online",
                "provider": "ollama",
                "status": "offline",
                "detail": f"Ollama unreachable at {settings.OLLAMA_BASE_URL}",
                "model": settings.OLLAMA_CHAT_MODEL,
            }
    else:
        avail = await openrouter_provider.check_availability(force_refresh=False)
        if not avail.get("configured"):
            return {
                "fastapi": "online",
                "provider": "openrouter",
                "status": "degraded",
                "detail": "OPENROUTER_API_KEY is not configured",
                "model": settings.OPENROUTER_MODEL,
            }
        elif avail.get("authenticated") and avail.get("reachable"):
            return {
                "fastapi": "online",
                "provider": "openrouter",
                "status": "connected",
                "detail": f"OpenRouter connected ({settings.OPENROUTER_MODEL})",
                "model": settings.OPENROUTER_MODEL,
            }
        elif avail.get("reachable") and not avail.get("authenticated"):
            return {
                "fastapi": "online",
                "provider": "openrouter",
                "status": "degraded",
                "detail": "OpenRouter authentication failed (invalid key)",
                "model": settings.OPENROUTER_MODEL,
            }
        else:
            return {
                "fastapi": "online",
                "provider": "openrouter",
                "status": "offline",
                "detail": "OpenRouter unreachable (network offline)",
                "model": settings.OPENROUTER_MODEL,
            }

