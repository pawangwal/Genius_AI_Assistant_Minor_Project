"""Tests for file upload validation, text extraction, and size limits."""
import pytest
import io
from httpx import AsyncClient, ASGITransport
import pypdf

from backend.app.main import app

def create_sample_pdf_bytes(text: str) -> bytes:
    """Generates a valid in-memory PDF containing the given text."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream_content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
    s = pypdf.generic.DecodedStreamObject()
    s.set_data(stream_content)
    page[pypdf.generic.NameObject("/Contents")] = writer._add_object(s)
    font_dict = pypdf.generic.DictionaryObject({
        pypdf.generic.NameObject("/Type"): pypdf.generic.NameObject("/Font"),
        pypdf.generic.NameObject("/Subtype"): pypdf.generic.NameObject("/Type1"),
        pypdf.generic.NameObject("/BaseFont"): pypdf.generic.NameObject("/Helvetica"),
    })
    resources = pypdf.generic.DictionaryObject({
        pypdf.generic.NameObject("/Font"): pypdf.generic.DictionaryObject({
            pypdf.generic.NameObject("/F1"): writer._add_object(font_dict)
        })
    })
    page[pypdf.generic.NameObject("/Resources")] = writer._add_object(resources)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

@pytest.mark.asyncio
async def test_upload_txt_success():
    """Text files extract cleanly with accurate metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("notes.txt", b"Hello world! This is a test file for Genius AI.", "text/plain")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["filename"] == "notes.txt"
        assert data["file_type"] == "TXT"
        assert "Hello world! This is a test file for Genius AI." in data["text_content"]
        assert data["truncated"] is False

@pytest.mark.asyncio
async def test_upload_markdown_success():
    """Markdown files extract and preserve content."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("doc.md", b"# Architecture\n\n- Component A\n- Component B", "text/markdown")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["file_type"] == "MD"
        assert "# Architecture" in data["text_content"]

@pytest.mark.asyncio
async def test_upload_json_formatting():
    """Valid JSON is parsed and pretty-printed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        json_bytes = b'{"name": "Genius", "version": 1, "status": "active"}'
        files = {"file": ("config.json", json_bytes, "application/json")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["file_type"] == "JSON"
        assert '"name": "Genius"' in data["text_content"]

@pytest.mark.asyncio
async def test_upload_csv_success():
    """CSV tabular data is extracted as plain text."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        csv_bytes = b"id,team,runs\n1,MI,180\n2,CSK,184\n"
        files = {"file": ("matches.csv", csv_bytes, "text/csv")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["file_type"] == "CSV"
        assert "1,MI,180" in data["text_content"]

@pytest.mark.asyncio
async def test_upload_pdf_success():
    """PDF text content is extracted page by page."""
    pdf_bytes = create_sample_pdf_bytes("Cricket match analysis report 2026")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("report.pdf", pdf_bytes, "application/pdf")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["file_type"] == "PDF"
        assert "Cricket match analysis report 2026" in data["text_content"]

@pytest.mark.asyncio
async def test_upload_unsupported_extension():
    """Unsupported extension is rejected with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("script.exe", b"binary content", "application/octet-stream")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 400
        assert "Unsupported file type" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_empty_file():
    """Empty 0-byte file is rejected with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("empty.txt", b"", "text/plain")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 400
        assert "is empty" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_oversized_file():
    """Files exceeding 5MB are rejected with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        large_bytes = b"A" * (5 * 1024 * 1024 + 100)
        files = {"file": ("large.txt", large_bytes, "text/plain")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 400
        assert "exceeds maximum allowed size" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_malformed_json():
    """Malformed JSON returns descriptive error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        bad_json = b'{"unclosed": "brace"'
        files = {"file": ("bad.json", bad_json, "application/json")}
        res = await ac.post("/api/v1/chat/upload", files=files)
        assert res.status_code == 400
        assert "malformed JSON" in res.json()["detail"]
