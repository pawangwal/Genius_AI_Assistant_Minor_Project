"""Chat completions endpoint with Server-Sent Events (SSE) streaming."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user_id
from backend.app.services.agent import agent_orchestrator
from backend.app.services.file_extractor import extract_text_from_upload, ExtractedFileResult

router = APIRouter(prefix="/chat", tags=["Agent Chat"])

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text")

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    stream: bool = Field(True, description="Whether to stream response tokens via SSE")

@router.post("/upload", response_model=ExtractedFileResult)
async def upload_chat_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id)
) -> ExtractedFileResult:
    """Uploads and extracts plain text from a supported attachment (.txt, .md, .csv, .json, .pdf)."""
    return await extract_text_from_upload(file)

@router.post("/completions")
async def chat_completions(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Executes the local agent loop and streams tokens and tool events via SSE."""
    raw_messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    return StreamingResponse(
        agent_orchestrator.run_stream(raw_messages, db, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
