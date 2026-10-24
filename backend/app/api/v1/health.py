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
