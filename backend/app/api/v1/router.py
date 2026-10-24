"""API v1 master router aggregating all sub-routers."""
from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.predictions import router as predictions_router
from backend.app.api.v1.tasks import router as tasks_router
from backend.app.api.v1.reminders import router as reminders_router
from backend.app.api.v1.chat import router as chat_router
from backend.app.api.v1.stt import router as stt_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(predictions_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(reminders_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(stt_router)
