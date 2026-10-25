"""File text extraction service supporting .txt, .md, .csv, .json, and .pdf.
Enforces strict size limits, validates extensions, and handles errors cleanly without vector DB dependencies.
"""
import io
import json
import logging
from pathlib import Path
from typing import Set
from pydantic import BaseModel
from fastapi import HTTPException, UploadFile, status
import pypdf

logger = logging.getLogger("genius.file_extractor")

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 Megabytes
MAX_TEXT_CHARACTERS = 50_000            # Prevent LLM context saturation
SUPPORTED_EXTENSIONS: Set[str] = {".txt", ".md", ".csv", ".json", ".pdf"}

class ExtractedFileResult(BaseModel):
    filename: str
    file_type: str
    size_bytes: int
    char_count: int
    text_content: str
    truncated: bool

async def extract_text_from_upload(upload_file: UploadFile) -> ExtractedFileResult:
    """Reads and extracts clean plain-text from an uploaded file.
    
    Raises:
        HTTPException(400): If the file format is unsupported, exceeds limits, is empty, or is unreadable.
    """
    raw_filename = upload_file.filename or "unknown"
    ext = Path(raw_filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    # Read binary content
    try:
        content_bytes = await upload_file.read()
    except Exception as exc:
        logger.error(f"Failed to read uploaded file '{raw_filename}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file data."
        )

    size = len(content_bytes)
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{raw_filename}' is empty."
        )

    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of 5 MB (received {size / (1024 * 1024):.2f} MB)."
        )

    extracted_text = ""

    # 1. Plain text formats (.txt, .md, .csv)
    if ext in (".txt", ".md", ".csv"):
        try:
            extracted_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                extracted_text = content_bytes.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{raw_filename}' contains invalid text encoding."
                )

    # 2. JSON files (.json)
    elif ext == ".json":
        try:
            decoded = content_bytes.decode("utf-8", errors="replace")
            parsed = json.loads(decoded)
            extracted_text = json.dumps(parsed, indent=2)
        except json.JSONDecodeError as jde:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{raw_filename}' contains malformed JSON: {jde.msg}."
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse JSON file '{raw_filename}': {str(exc)}."
            )

    # 3. PDF files (.pdf)
    elif ext == ".pdf":
        try:
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            if reader.is_encrypted:
                try:
                    # Attempt empty password decrypt
                    reader.decrypt("")
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"PDF '{raw_filename}' is password-protected or encrypted."
                    )

            page_texts = []
            for idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    page_texts.append(f"--- Page {idx + 1} ---\n{text}")

            extracted_text = "\n\n".join(page_texts).strip()
            if not extracted_text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF '{raw_filename}' contains no readable text (scanned image or empty document)."
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"PyPDF extraction error on '{raw_filename}': {exc}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to read PDF '{raw_filename}'. File may be corrupted."
            )

    cleaned_text = extracted_text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{raw_filename}' contains no readable text."
        )

    truncated = False
    if len(cleaned_text) > MAX_TEXT_CHARACTERS:
        cleaned_text = cleaned_text[:MAX_TEXT_CHARACTERS] + "\n\n... [Content truncated at 50,000 characters]"
        truncated = True

    return ExtractedFileResult(
        filename=raw_filename,
        file_type=ext[1:].upper(),
        size_bytes=size,
        char_count=len(cleaned_text),
        text_content=cleaned_text,
        truncated=truncated
    )
