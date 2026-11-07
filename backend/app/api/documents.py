"""
AICTE Deposit Manager — Documents Streaming & Inspection API
Serves securely stored PDF and image documents with byte streaming,
extracted fields, and MIME-type enforcement.
"""

import os
import json
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InstrumentDocument, DepositInstrument, Institution
from app.schemas import InstrumentDocumentDetailResponse
from app.api.auth import get_current_user, UserInfo

router = APIRouter(tags=["Documents"])


@router.get("/documents/{id}", response_model=InstrumentDocumentDetailResponse)
@router.get("/instruments/{instrument_id}/documents/{id}", response_model=InstrumentDocumentDetailResponse)
def get_document_details(
    id: int,
    instrument_id: int = None,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Returns metadata, extracted text preview, and parsed fields for an instrument document.
    """
    query = db.query(InstrumentDocument).filter(InstrumentDocument.id == id)
    if instrument_id is not None:
        query = query.filter(InstrumentDocument.instrument_id == instrument_id)
    doc = query.first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Access control
    if current_user.role == "APPLICANT" and current_user.institution_id:
        if doc.instrument.institution.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to access documents from another institution."
            )

    preview = (doc.extracted_text[:200] + "...") if doc.extracted_text and len(doc.extracted_text) > 200 else doc.extracted_text

    return {
        "id": doc.id,
        "instrument_id": doc.instrument_id,
        "document_category": doc.document_category,
        "original_filename": doc.original_filename,
        "file_size_bytes": doc.file_size_bytes,
        "mime_type": doc.mime_type,
        "sha256_hash": doc.sha256_hash,
        "phash_value": doc.phash_value,
        "upload_timestamp": doc.upload_timestamp,
        "uploaded_by": doc.uploaded_by,
        "extraction_status": doc.extraction_status,
        "ocr_performed": doc.ocr_performed,
        "version": doc.version,
        "status": doc.status,
        "extracted_text_preview": preview,
        "extracted_text": doc.extracted_text,
        "extracted_fields_json": doc.extracted_fields_json,
        "stream_url": f"/api/documents/{doc.id}/stream"
    }


@router.get("/documents/{id}/stream")
@router.get("/documents/{id}/raw")
@router.get("/instruments/{instrument_id}/documents/{id}/stream")
@router.get("/instruments/{instrument_id}/documents/{id}/raw")
def stream_document(
    id: int,
    instrument_id: int = None,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Streams the raw binary document (PDF or image) from the storage vault.
    Never returns JSON errors inside an iframe/embed viewer.
    """
    query = db.query(InstrumentDocument).filter(InstrumentDocument.id == id)
    if instrument_id is not None:
        query = query.filter(InstrumentDocument.instrument_id == instrument_id)
    doc = query.first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if current_user.role == "APPLICANT" and current_user.institution_id:
        if doc.instrument.institution.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to access documents from another institution."
            )

    file_path = Path(doc.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file missing from vault")

    media_type = doc.mime_type
    if not media_type or media_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(doc.original_filename)
        media_type = guessed or ("application/pdf" if doc.original_filename.lower().endswith(".pdf") else "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=doc.original_filename,
        headers={"Content-Disposition": f"inline; filename=\"{doc.original_filename}\""}
    )
