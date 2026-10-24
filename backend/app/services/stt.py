"""Local Speech-to-Text (STT) service providing bounded, offline transcription using faster-whisper."""
import os
import asyncio
import tempfile
import logging
from typing import Dict, Any, Optional
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

def probe_audio_duration(file_path: str) -> Optional[float]:
    """Probes media duration before running expensive ML inference using PyAV, Mutagen, and wave."""
    # 1. Primary: PyAV (FFmpeg C-bindings, handles all audio containers including WebM, Opus, MP3, WAV, FLAC, OGG)
    try:
        import av
        with av.open(file_path) as container:
            if container.duration is not None and container.duration > 0:
                return float(container.duration) / 1_000_000.0
            for stream in container.streams.audio:
                if stream.duration is not None and stream.time_base is not None:
                    return float(stream.duration * stream.time_base)
    except Exception as e:
        logger.debug(f"PyAV duration probe failed for {file_path}: {e}")

    # 2. Secondary: Mutagen (pure Python tags and stream inspection)
    try:
        import mutagen
        audio = mutagen.File(file_path)
        if audio is not None and hasattr(audio, "info") and audio.info is not None:
            if hasattr(audio.info, "length") and audio.info.length:
                return float(audio.info.length)
    except Exception as e:
        logger.debug(f"Mutagen duration probing failed for {file_path}: {e}")

    # 3. Tertiary: Standard library wave module for WAV RIFF containers
    try:
        import wave
        with wave.open(file_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames) / float(rate)
    except Exception:
        pass

    return None

class LocalSTTService:
    def __init__(self):
        self.model = None
        self._is_loaded = False
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.STT_MAX_CONCURRENT_JOBS)
        return self._semaphore

    def load(self, local_files_only: bool = True) -> bool:
        """Initializes the local Whisper model strictly offline with zero network egress.
        
        Strictly enforces local_files_only=True. Never falls back to network download.
        """
        try:
            from faster_whisper import WhisperModel
            logger.info(
                f"Loading faster-whisper model '{settings.STT_MODEL_SIZE}' on {settings.STT_DEVICE} "
                f"({settings.STT_COMPUTE_TYPE}, local_files_only=True)..."
            )
            # Fail closed: strictly require local files and reject network downloads
            self.model = WhisperModel(
                settings.STT_MODEL_SIZE,
                device=settings.STT_DEVICE,
                compute_type=settings.STT_COMPUTE_TYPE,
                local_files_only=True
            )
            self._is_loaded = True
            logger.info("Local faster-whisper model successfully initialized.")
            return True
        except ImportError:
            logger.warning("faster-whisper library is not installed in the active environment.")
            self._is_loaded = False
            return False
        except Exception as e:
            logger.error(f"Failed to load local faster-whisper model (zero-egress strictly enforced): {e}")
            self._is_loaded = False
            return False

    @property
    def is_ready(self) -> bool:
        return self._is_loaded and self.model is not None

    async def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str = "audio.webm") -> Dict[str, Any]:
        """Transcribes raw audio bytes locally under concurrency limits and pre-inference duration bounds."""
        if len(audio_bytes) > settings.STT_MAX_UPLOAD_BYTES:
            raise ValueError(
                f"Audio file exceeds maximum allowed size ({settings.STT_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
            )

        semaphore = self._get_semaphore()
        async with semaphore:
            suffix = os.path.splitext(filename)[1] or ".webm"
            temp_path = None

            try:
                # Write to temporary file for Whisper processing
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name

                # Pre-inference duration validation: probe media duration before running expensive inference
                probed_duration = probe_audio_duration(temp_path)
                if probed_duration is None:
                    raise ValueError(
                        "Unable to establish media duration prior to inference. "
                        "Please provide valid audio with standard container headers (WAV, WebM, MP3, OGG, FLAC)."
                    )
                if probed_duration > settings.STT_MAX_DURATION_SECONDS:
                    raise ValueError(
                        f"Audio duration ({probed_duration:.1f}s) exceeds maximum allowed limit of "
                        f"{settings.STT_MAX_DURATION_SECONDS}s."
                    )

                # Load model if not already in memory
                if not self.is_ready:
                    loaded = self.load()
                    if not loaded:
                        raise RuntimeError("Local speech-to-text model is unavailable.")

                # Run transcription in threadpool to avoid blocking the async event loop
                loop = asyncio.get_running_loop()
                segments, info = await loop.run_in_executor(
                    None,
                    lambda: self.model.transcribe(
                        temp_path,
                        beam_size=5,
                        language=None,  # Auto-detect language (Hindi or English)
                        vad_filter=True
                    )
                )

                # Duration bounds validation (post-inference defense-in-depth)
                duration = round(float(info.duration), 2)
                if duration > settings.STT_MAX_DURATION_SECONDS:
                    raise ValueError(
                        f"Audio duration ({duration}s) exceeds maximum allowed limit of "
                        f"{settings.STT_MAX_DURATION_SECONDS}s."
                    )

                # Collect segment text
                transcribed_text = " ".join([segment.text.strip() for segment in segments]).strip()
                detected_lang = info.language

                return {
                    "status": "success",
                    "text": transcribed_text,
                    "language": detected_lang,
                    "duration_seconds": duration
                }

            finally:
                # Guaranteed cleanup of temporary audio files
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError as e:
                        logger.warning(f"Failed to clean up temporary audio file {temp_path}: {e}")

stt_service = LocalSTTService()
