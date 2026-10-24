"""FastAPI modular monolith application entry point with lifespan management and CORS."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.app.core.config import settings
from backend.app.core.database import engine
from backend.app.ml.ipl_pipeline import ipl_service
from backend.app.api.v1.router import api_v1_router

# Configure root logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("genius.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initializes ML models and performs startup validation."""
    logger.info("Initializing Genius AI Assistant backend...")
    
    # 1. Enforce security profile rules
    settings.validate_security_profile()
    logger.info(f"Active Environment: {settings.APP_ENV} | Auth Required: {settings.AUTH_REQUIRED}")

    # 2. Load ML Pipeline
    model_loaded = ipl_service.load()
    if not model_loaded:
        logger.warning("IPL Model failed to load on startup. Inference routes will return 503.")
    else:
        logger.info("IPL Model successfully loaded and ready for inference.")

    # 3. Database connectivity and schema verification (managed via Alembic migrations)
    from backend.app.core.database import check_database_health, AsyncSessionLocal
    from backend.app.models.entities import UserEntity
    from sqlalchemy import select

    db_ok, db_msg = await check_database_health()
    if not db_ok:
        logger.error(f"Startup database probe warning: {db_msg}")
        if settings.is_production:
            logger.critical("Production startup halted: database schema not ready.")
    else:
        logger.info("Database connectivity and schema tables verified.")
        # In local development profile, ensure local seed user exists
        if not settings.AUTH_REQUIRED:
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(UserEntity).where(UserEntity.id == "local-user"))
                    if not result.scalar_one_or_none():
                        session.add(UserEntity(id="local-user", username="local_developer"))
                        await session.commit()
                        logger.info("Local development seed user initialized.")
            except Exception as seed_err:
                logger.warning(f"Failed to seed local-user: {seed_err}")

    yield

    # Teardown
    logger.info("Shutting down Genius AI Assistant backend...")
    await engine.dispose()
    logger.info("Database engine connections closed.")

app = FastAPI(
    title="Genius AI Assistant API",
    description="Production-grade, local-first multimodal assistant API with IPL ML prediction and offline agent tools.",
    version="1.0.0",
    lifespan=lifespan
)

# Strict CORS policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database failure encountered: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service unavailable. Downstream storage is degraded."}
    )

# Master API v1 Router
app.include_router(api_v1_router)

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Genius AI Assistant API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "api_v1": "/api/v1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=(settings.APP_ENV == "development")
    )
