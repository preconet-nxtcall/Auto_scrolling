import io
import re
import os
import uuid
import zipfile
import logging
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger("uvicorn.error")

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit

ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/x-zip-compressed"},
    ".doc": {"application/msword", "application/x-msword"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip", "application/x-zip-compressed"},
    ".ppt": {"application/vnd.ms-powerpoint"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/x-zip-compressed"},
    ".xls": {"application/vnd.ms-excel"},
    ".csv": {"text/csv", "text/plain", "application/csv", "text/x-csv", "application/vnd.ms-excel"},
    ".html": {"text/html", "application/xhtml+xml", "text/plain"},
    ".htm": {"text/html", "application/xhtml+xml", "text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg", "image/pjpeg"},
    ".jpeg": {"image/jpeg", "image/pjpeg"},
    ".webp": {"image/webp"},
    ".tiff": {"image/tiff", "image/x-tiff"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
    ".gif": {"image/gif"}
}

def sanitize_filename(filename: str) -> tuple[str, str]:
    """
    Never trust user-provided filenames.
    Strips directory traversal, illegal characters, and extracts safe basename & extension.
    """
    if not filename:
        filename = "unnamed_document.bin"

    # Remove path components
    clean_name = os.path.basename(filename)
    clean_name = re.sub(r'[\/\:\*\?\"\<\>\|]', '_', clean_name)
    clean_name = re.sub(r'\.\.+', '.', clean_name).strip(' .')

    path_obj = Path(clean_name)
    stem = path_obj.stem[:100]  # truncate stem length
    ext = path_obj.suffix.lower()

    if not stem:
        stem = "document"

    return stem, ext

def validate_upload_metadata(filename: str, content_type: str, file_size: int) -> tuple[str, str]:
    """Validates extension, MIME type, and file size before saving."""
    stem, ext = sanitize_filename(filename)

    # 1. Extension Validation
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{ext}'. Allowed extensions: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )

    # 2. File Size Validation
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum limit of {max_mb} MB."
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    # 3. MIME Type Validation
    valid_mimes = ALLOWED_MIME_TYPES.get(ext, set())
    # If client passed generic octet-stream or mime in valid set, accept
    normalized_mime = (content_type or "").lower().split(";")[0].strip()
    
    if normalized_mime and normalized_mime != "application/octet-stream" and valid_mimes:
        if normalized_mime not in valid_mimes:
            logger.warning(f"MIME type warning for '{filename}': received '{normalized_mime}', expected one of {valid_mimes}")

    return stem, ext

def validate_file_integrity(file_bytes: bytes, ext: str) -> tuple[bool, str]:
    """
    Checks binary integrity to detect corrupted or malformed files.
    """
    ext = ext.lower()

    # PDF Integrity
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            return False, "Corrupted PDF file header (missing '%PDF-' signature)."
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            if len(reader.pages) == 0:
                return False, "PDF contains 0 pages."
        except Exception as e:
            return False, f"Corrupted or password-protected PDF structure: {str(e)}"

    # Image Integrity
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".tiff"):
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
        except Exception as e:
            return False, f"Corrupted or invalid image file: {str(e)}"

    # OpenXML Office Files (.docx, .pptx, .xlsx)
    elif ext in (".docx", ".pptx", ".xlsx"):
        if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
            return False, f"Corrupted Office file format '{ext}' (not a valid OpenXML ZIP package)."
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                if zf.testzip() is not None:
                    return False, "Corrupted internal zip archives in Office file."
        except Exception as e:
            return False, f"Corrupted Office archive: {str(e)}"

    # Text / CSV / HTML Integrity
    elif ext in (".csv", ".html", ".htm"):
        try:
            sample = file_bytes[:1024].decode("utf-8", errors="replace")
            if "\0" in sample:
                return False, f"Binary corruption detected in text file '{ext}'."
        except Exception as e:
            return False, f"Invalid file encoding for '{ext}': {str(e)}"

    return True, ""
