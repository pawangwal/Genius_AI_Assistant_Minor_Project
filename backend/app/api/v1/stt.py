"""Speech-to-Text (STT) file upload API endpoint with streaming bounds and error sanitization."""
import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from backend.app.services.stt import stt_service
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stt", tags=["Speech Recognition"])

ALLOWED_AUDIO_EXTENSIONS = {".webm", ".wav", ".mp3", ".ogg", ".m4a"}
UPLOAD_CHUNK_SIZE = 64 * 1024  # 64 KB chunks

@router.post("", status_code=status.HTTP_200_OK)
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribes client-recorded audio entirely offline using local Whisper.
    
    Enforces bounded streaming chunk reads to prevent memory exhaustion DoS attacks,
    validates audio format, and delegates to the bounded LocalSTTService.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext and ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
        )

    # 1. Stream file in chunks, enforcing hard upper bounds without buffering excessive data
    total_bytes = 0
    chunks = []
    max_bytes = settings.STT_MAX_UPLOAD_BYTES

    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            logger.warning(f"Upload rejected: streamed payload exceeded limit of {max_bytes} bytes.")
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Audio payload exceeds maximum limit of {max_bytes // (1024 * 1024)} MB."
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio payload received."
        )

    content = b"".join(chunks)

    # 2. Execute local transcription under concurrency semaphore and duration checks
    try:
        result = await stt_service.transcribe_audio_bytes(content, filename=file.filename or "audio.webm")
        return result
    except ValueError as e:
        logger.warning(f"Validation failure during STT processing: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"STT engine runtime error: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error during audio transcription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech transcription failed due to an internal server error."
        )
