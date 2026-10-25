"""Tests for Speech-to-Text (STT) upload validation, streaming limits, duration bounds, and transcription."""
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_stt_unsupported_format(async_client):
    """Uploading unsupported media types returns HTTP 400."""
    files = {"file": ("malicious.exe", b"not-audio-content", "application/octet-stream")}
    resp = await async_client.post("/api/v1/stt", files=files)
    assert resp.status_code == 400
    assert "Unsupported audio format" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_stt_empty_payload(async_client):
    """Uploading empty audio bytes returns HTTP 400."""
    files = {"file": ("empty.wav", b"", "audio/wav")}
    resp = await async_client.post("/api/v1/stt", files=files)
    assert resp.status_code == 400
    assert "Empty audio payload" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_stt_oversized_payload_streaming_rejection(async_client):
    """Uploading audio exceeding 10MB limit triggers streaming HTTP 413 Payload Too Large."""
    large_audio = b"0" * (11 * 1024 * 1024)
    files = {"file": ("huge.webm", large_audio, "audio/webm")}
    resp = await async_client.post("/api/v1/stt", files=files)
    assert resp.status_code == 413
    assert "exceeds maximum limit" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_stt_duration_exceeded(async_client):
    """Audio exceeding max allowed duration (120s) returns HTTP 400."""
    with patch("backend.app.api.v1.stt.stt_service.transcribe_audio_bytes", new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.side_effect = ValueError("Audio duration (150.0s) exceeds maximum allowed limit of 120s.")
        files = {"file": ("long.wav", b"dummy_audio_bytes", "audio/wav")}
        resp = await async_client.post("/api/v1/stt", files=files)
        assert resp.status_code == 400
        assert "exceeds maximum allowed limit" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_stt_successful_transcription(async_client):
    """Valid audio returns transcribed text, duration, and detected language."""
    mock_result = {
        "status": "success",
        "text": "नमस्ते Genius IPL स्कोर बताओ",
        "language": "hi",
        "duration_seconds": 3.4
    }

    with patch("backend.app.api.v1.stt.stt_service.transcribe_audio_bytes", new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = mock_result
        files = {"file": ("query.webm", b"RIFF....audio_bytes", "audio/webm")}
        resp = await async_client.post("/api/v1/stt", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "नमस्ते Genius IPL स्कोर बताओ"
        assert data["language"] == "hi"
        assert data["duration_seconds"] == 3.4

def test_stt_load_offline_strictly_enforced():
    """STT loader strictly fails closed if model is missing, with zero network download fallback."""
    from backend.app.services.stt import LocalSTTService
    from unittest.mock import patch, MagicMock

    service = LocalSTTService()
    # Mock faster_whisper to raise exception simulating missing offline model files
    with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
        import sys
        mock_fw = sys.modules["faster_whisper"]
        mock_fw.WhisperModel.side_effect = RuntimeError("Model files not found locally.")

        loaded = service.load(local_files_only=True)
        assert loaded is False
        assert service.is_ready is False
        # Verify WhisperModel was called ONLY with local_files_only=True and never with False
        for call_args in mock_fw.WhisperModel.call_args_list:
            assert call_args.kwargs.get("local_files_only") is True

@pytest.mark.asyncio
async def test_stt_pre_inference_duration_rejection():
    """Audio exceeding max allowed duration is rejected before calling transcribe."""
    from backend.app.services.stt import LocalSTTService
    from unittest.mock import patch, MagicMock

    service = LocalSTTService()
    service.model = MagicMock()
    service._is_loaded = True

    # Mock media probing to return 150 seconds (exceeding 120s limit)
    with patch("backend.app.services.stt.probe_audio_duration", return_value=150.0):
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            await service.transcribe_audio_bytes(b"dummy_bytes", "test.wav")
        # Ensure model.transcribe was NEVER called
        service.model.transcribe.assert_not_called()

@pytest.mark.asyncio
async def test_stt_unestablished_duration_rejected_before_inference():
    """Audio whose duration cannot be established is rejected before running expensive inference."""
    from backend.app.services.stt import LocalSTTService
    from unittest.mock import MagicMock

    service = LocalSTTService()
    service.model = MagicMock()
    service._is_loaded = True

    # Raw corrupted/unparseable bytes
    corrupt_bytes = b"CORRUPT_NOT_A_VALID_AUDIO_HEADER" * 10
    with pytest.raises(ValueError, match="Unable to establish media duration prior to inference"):
        await service.transcribe_audio_bytes(corrupt_bytes, "corrupt.wav")
    service.model.transcribe.assert_not_called()

def test_stt_real_wav_fixture_duration_probing(tmp_path):
    """Verifies duration probing against a real byte-level WAV audio fixture."""
    import io
    import wave
    from backend.app.services.stt import probe_audio_duration

    # Create real 2.5 second valid PCM WAV file
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * 2.5))

    wav_file = tmp_path / "valid_sample.wav"
    wav_file.write_bytes(buf.getvalue())

    duration = probe_audio_duration(str(wav_file))
    assert duration is not None
    assert round(duration, 1) == 2.5

def test_stt_browser_streaming_webm_duration_probing(tmp_path):
    """Verifies duration probing against streaming WebM audio fixtures as generated by browser MediaRecorder."""
    import av
    from backend.app.services.stt import probe_audio_duration

    webm_path = tmp_path / "browser_stream.webm"
    # Create 2.0 second Opus-encoded WebM stream
    container = av.open(str(webm_path), mode="w", format="webm")
    stream = container.add_stream("opus", rate=16000)
    for i in range(100):  # 100 * 320 = 32000 samples = 2.0s
        frame = av.AudioFrame(format="s16", layout="mono", samples=320)
        frame.rate = 16000
        frame.pts = i * 320
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    duration = probe_audio_duration(str(webm_path))
    assert duration is not None
    assert round(duration, 1) == 2.0


