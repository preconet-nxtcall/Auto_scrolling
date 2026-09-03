import uuid
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import Document, User
from app.auth import get_current_user
from app.schemas import DocumentResponse, DocumentUpdate, BatchConfigUpdate, UserSettingsResponse, UserSettingsUpdate
from app.security import validate_upload_metadata, validate_file_integrity, sanitize_filename
from app.services.conversion_service import execute_conversion_job

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

@router.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "uploads_dir": str(settings.UPLOADS_DIR),
        "temp_dir": str(settings.TEMP_DIR),
        "converted_dir": str(settings.CONVERTED_DIR)
    }

@router.get("/settings", response_model=UserSettingsResponse, tags=["Settings"])
def get_user_settings(current_user: User = Depends(get_current_user)):
    """Retrieve global default auto-scroll settings for current authenticated user."""
    return current_user

@router.put("/settings", response_model=UserSettingsResponse, tags=["Settings"])
def update_user_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update global default auto-scroll settings for current user."""
    if payload.global_scroll_speed is not None:
        current_user.global_scroll_speed = payload.global_scroll_speed
    if payload.global_repeat_count is not None:
        current_user.global_repeat_count = payload.global_repeat_count
    if payload.global_interaction_pause is not None:
        current_user.global_interaction_pause = payload.global_interaction_pause
    if payload.global_start_delay is not None:
        current_user.global_start_delay = payload.global_start_delay
    if payload.global_between_repeats_delay is not None:
        current_user.global_between_repeats_delay = payload.global_between_repeats_delay
    if payload.global_between_documents_delay is not None:
        current_user.global_between_documents_delay = payload.global_between_documents_delay

    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/documents/upload", response_model=List[DocumentResponse], status_code=status.HTTP_201_CREATED, tags=["Documents"])
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    scroll_speed: Optional[int] = Form(None),
    repeat_count: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Secure multi-file document upload API.
    - Validates file extension, MIME type, file size limit (50MB), and file corruption.
    - Sanitizes filenames and uses cryptographically secure UUID storage.
    - Enqueues conversion background tasks (uploaded -> processing -> completed / failed).
    - Binds uploaded documents strictly to the authenticated user.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided for upload.")

    created_documents = []

    for file in files:
        contents = await file.read()
        file_size = len(contents)
        mime_type = file.content_type or "application/octet-stream"

        # 1. Validate Extension, MIME type, and File Size
        stem, ext = validate_upload_metadata(file.filename, mime_type, file_size)

        # 2. Validate File Corruption / Binary Integrity
        is_valid, corruption_error = validate_file_integrity(contents, ext)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed for '{file.filename}': {corruption_error}"
            )

        # 3. Secure File Naming
        unique_id = uuid.uuid4().hex
        saved_original_filename = f"{unique_id}_{stem}{ext}"
        saved_pdf_filename = f"{unique_id}_{stem}.pdf"

        original_file_path = settings.UPLOADS_DIR / saved_original_filename
        converted_pdf_path = settings.CONVERTED_DIR / saved_pdf_filename
        temp_file_path = settings.TEMP_DIR / saved_original_filename

        # Save to both temporary buffer and permanent uploads directory
        with open(original_file_path, "wb") as f:
            f.write(contents)
        with open(temp_file_path, "wb") as f:
            f.write(contents)

        # Create Database Record bound to current_user.id with status "uploaded" and database binary data
        doc = Document(
            user_id=current_user.id,
            title=stem,
            original_filename=file.filename or f"document{ext}",
            original_extension=ext,
            original_mime_type=mime_type,
            original_file_size=file_size,
            original_file_path=str(original_file_path),
            original_file_data=contents,
            pdf_file_path=str(converted_pdf_path),
            scroll_speed=scroll_speed,
            repeat_count=repeat_count,
            conversion_status="uploaded"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Enqueue conversion background task
        background_tasks.add_task(execute_conversion_job, doc.id)
        doc.effective_settings = doc.get_effective_settings(current_user)

        created_documents.append(doc)

    return created_documents

@router.get("/documents", response_model=List[DocumentResponse], tags=["Documents"])
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all documents belonging exclusively to the current authenticated user."""
    docs = db.query(Document).filter(
        Document.user_id == current_user.id
    ).order_by(
        Document.sequence_order.asc(), 
        Document.created_at.desc()
    ).all()
    
    for doc in docs:
        doc.effective_settings = doc.get_effective_settings(current_user)
    return docs

@router.get("/documents/{document_id}", response_model=DocumentResponse, tags=["Documents"])
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve details for a single document owned by the current user."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )
    doc.effective_settings = doc.get_effective_settings(current_user)
    return doc

@router.patch("/documents/{document_id}", response_model=DocumentResponse, tags=["Documents"])
@router.patch("/documents/{document_id}/settings", response_model=DocumentResponse, include_in_schema=False, tags=["Documents"])
def update_document_settings(
    document_id: int,
    update_data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update document auto-scroll overrides and title settings."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)

    db.commit()
    db.refresh(doc)
    doc.effective_settings = doc.get_effective_settings(current_user)
    return doc

@router.get("/documents/{document_id}/status", tags=["Documents"])
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve conversion status and progress for polling."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    return {
        "id": doc.id,
        "conversion_status": doc.conversion_status,
        "page_count": doc.page_count,
        "conversion_error": doc.conversion_error
    }

@router.post("/documents/{document_id}/retry", response_model=DocumentResponse, tags=["Documents"])
def retry_document_conversion(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-enqueue a failed document conversion job."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    # Ensure source file is present in TEMP_DIR for reprocessing
    original_path = Path(doc.original_file_path)
    temp_path = settings.TEMP_DIR / original_path.name

    if original_path.exists() and not temp_path.exists():
        shutil.copy(str(original_path), str(temp_path))

    doc.conversion_status = "uploaded"
    doc.conversion_error = None
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(execute_conversion_job, doc.id)
    doc.effective_settings = doc.get_effective_settings(current_user)
    return doc

@router.get("/documents/{document_id}/pdf", tags=["Documents"])
@router.get("/documents/{document_id}/stream", include_in_schema=False, tags=["Documents"])
def stream_pdf(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stream converted PDF file for PDF.js frontend viewer.
    Enforces user ownership authorization. Supports HTTP range requests.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    if doc.conversion_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not ready for viewing. Status: {doc.conversion_status}. Error: {doc.conversion_error}"
        )

    # 1. Prefer database binary blob stream if available
    if doc.pdf_file_data:
        from fastapi.responses import Response
        return Response(
            content=doc.pdf_file_data,
            media_type="application/pdf",
            headers={
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
                "Content-Disposition": f'inline; filename="{doc.title}.pdf"'
            }
        )

    # 2. Fallback to disk file if present
    if doc.pdf_file_path:
        pdf_file = Path(doc.pdf_file_path)
        if pdf_file.exists():
            return FileResponse(
                path=str(pdf_file),
                media_type="application/pdf",
                filename=f"{doc.title}.pdf",
                headers={
                    "Accept-Ranges": "bytes",
                    "Access-Control-Allow-Origin": "*"
                }
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Converted PDF file data missing."
    )

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Documents"])
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document record and purge files from disk for current user."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    # Purge physical files safely
    try:
        if doc.original_file_path and Path(doc.original_file_path).exists():
            Path(doc.original_file_path).unlink()
        if doc.pdf_file_path and Path(doc.pdf_file_path).exists():
            Path(doc.pdf_file_path).unlink()
        temp_path = settings.TEMP_DIR / Path(doc.original_file_path).name
        if temp_path.exists():
            temp_path.unlink()
    except Exception as e:
        logger.warning(f"File cleanup error during deletion of document {document_id}: {e}")

    db.delete(doc)
    db.commit()
    return None

@router.patch("/documents/{document_id}", response_model=DocumentResponse, tags=["Documents"])
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update settings for a single document owned by current user."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    fields_set = payload.model_fields_set

    if payload.title is not None:
        doc.title = payload.title
    if 'scroll_speed' in fields_set:
        doc.scroll_speed = payload.scroll_speed
    if 'repeat_count' in fields_set:
        doc.repeat_count = payload.repeat_count
    if 'interaction_pause' in fields_set:
        doc.interaction_pause = payload.interaction_pause
    if 'start_delay' in fields_set:
        doc.start_delay = payload.start_delay
    if 'between_repeats_delay' in fields_set:
        doc.between_repeats_delay = payload.between_repeats_delay
    if 'between_documents_delay' in fields_set:
        doc.between_documents_delay = payload.between_documents_delay
    if payload.sequence_order is not None:
        doc.sequence_order = payload.sequence_order

    db.commit()
    db.refresh(doc)
    doc.effective_settings = doc.get_effective_settings(current_user)
    return doc

@router.post("/documents/batch-config", tags=["Documents"])
def batch_update_config(
    payload: BatchConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk update scroll speed or repeat count across user's documents."""
    docs = db.query(Document).filter(
        Document.id.in_(payload.document_ids),
        Document.user_id == current_user.id
    ).all()
    
    for doc in docs:
        if payload.scroll_speed is not None:
            doc.scroll_speed = max(5, min(500, payload.scroll_speed))
        if payload.repeat_count is not None:
            doc.repeat_count = max(1, min(100, payload.repeat_count))
    db.commit()
    return {"status": "success", "updated_count": len(docs)}

@router.post("/documents/reorder", tags=["Documents"])
def reorder_playlist(
    document_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reorder sequence order for user's playlist execution."""
    for idx, doc_id in enumerate(document_ids):
        db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == current_user.id
        ).update({"sequence_order": idx})
    db.commit()
    return {"status": "success", "total_reordered": len(document_ids)}
