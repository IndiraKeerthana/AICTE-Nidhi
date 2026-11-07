"""
AICTE Deposit Manager — Security Deposits & FDRs API
Provides instrument register, search, filtering, detail inspection, and document upload.
"""

import os
import json
import datetime
from decimal import Decimal
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.config import settings
from app.models import (
    DepositInstrument, Institution, InstrumentDocument, VerificationRecord,
    RenewalRecord, ReleaseRefundRequest, AuditEvent
)
from app.schemas import (
    DepositInstrumentCreate, DepositInstrumentUpdate, DepositInstrumentResponse,
    DepositInstrumentDetailResponse, InstrumentDocumentResponse
)
from app.services.instrument_service import (
    calculate_validity_status, format_inr, update_instrument_lifecycle,
    DEFAULT_WARNING_WINDOW_DAYS
)
from app.services.fdr_verification_service import run_instrument_verification
from app.services.storage import calculate_sha256
from app.services.document_parser import extract_document_content
from app.api.auth import get_current_user, require_role, UserInfo

router = APIRouter(prefix="/instruments", tags=["Security Deposits & FDRs"])


def _hydrate_instrument_dto(inst: DepositInstrument) -> dict:
    v_status, remaining = calculate_validity_status(inst.maturity_date, DEFAULT_WARNING_WINDOW_DAYS)
    return {
        "id": inst.id,
        "instrument_number": inst.instrument_number,
        "institution_id": inst.institution_id,
        "instrument_type": inst.instrument_type,
        "issuing_bank": inst.issuing_bank,
        "branch_name": inst.branch_name,
        "branch_ifsc": inst.branch_ifsc,
        "account_number": inst.account_number,
        "amount": inst.amount,
        "currency": inst.currency or "INR",
        "issue_date": inst.issue_date,
        "maturity_date": inst.maturity_date,
        "submission_date": inst.submission_date,
        "lifecycle_status": inst.lifecycle_status,
        "validity_status": v_status,
        "verification_status": inst.verification_status,
        "original_instrument_id": inst.original_instrument_id,
        "renewal_count": inst.renewal_count,
        "lien_marked_to": inst.lien_marked_to,
        "joint_holder_name": inst.joint_holder_name,
        "purpose": inst.purpose,
        "notes": inst.notes,
        "remaining_days": remaining,
        "formatted_amount": format_inr(inst.amount),
        "institution": inst.institution,
        "created_at": inst.created_at,
        "updated_at": inst.updated_at,
        "documents_count": len([d for d in inst.documents if d.status == "ACTIVE"])
    }


@router.get("", response_model=List[DepositInstrumentResponse])
def list_instruments(
    search: Optional[str] = Query(None, description="Search instrument number, institution, or bank"),
    instrument_type: Optional[str] = Query(None),
    lifecycle_status: Optional[str] = Query(None),
    validity_status: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    issuing_bank: Optional[str] = Query(None),
    sort_by: str = Query("maturity_date", regex="^(maturity_date|amount|submission_date|institution)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Searchable and filterable FDR/deposit register.
    Restricts to user's institution if APPLICANT role.
    """
    query = db.query(DepositInstrument).join(DepositInstrument.institution)

    if current_user.role == "APPLICANT" and current_user.institution_id:
        query = query.filter(Institution.aicte_permanent_id == current_user.institution_id)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                DepositInstrument.instrument_number.ilike(s),
                Institution.name.ilike(s),
                Institution.aicte_permanent_id.ilike(s),
                DepositInstrument.issuing_bank.ilike(s)
            )
        )

    if instrument_type and instrument_type != "ALL":
        query = query.filter(DepositInstrument.instrument_type == instrument_type)
    if lifecycle_status and lifecycle_status != "ALL":
        query = query.filter(DepositInstrument.lifecycle_status == lifecycle_status)
    if verification_status and verification_status != "ALL":
        query = query.filter(DepositInstrument.verification_status == verification_status)
    if issuing_bank and issuing_bank != "ALL":
        query = query.filter(DepositInstrument.issuing_bank == issuing_bank)

    # Database sorting
    if sort_by == "amount":
        query = query.order_by(DepositInstrument.amount.desc() if sort_order == "desc" else DepositInstrument.amount.asc())
    elif sort_by == "submission_date":
        query = query.order_by(DepositInstrument.submission_date.desc() if sort_order == "desc" else DepositInstrument.submission_date.asc())
    elif sort_by == "institution":
        query = query.order_by(Institution.name.desc() if sort_order == "desc" else Institution.name.asc())
    else:  # maturity_date default
        query = query.order_by(DepositInstrument.maturity_date.desc() if sort_order == "desc" else DepositInstrument.maturity_date.asc())

    all_matched = query.all()

    # Hydrate DTOs with dynamic validity and filter in memory if validity_status was specified
    results = []
    for inst in all_matched:
        dto = _hydrate_instrument_dto(inst)
        if validity_status and validity_status != "ALL" and dto["validity_status"] != validity_status:
            continue
        results.append(dto)

    return results[offset: offset + limit]


@router.post("", response_model=DepositInstrumentResponse, status_code=status.HTTP_201_CREATED)
def create_instrument(
    payload: DepositInstrumentCreate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN", "APPLICANT"))
):
    """
    Registers a new security deposit / FDR record in the portal.
    """
    inst = db.query(Institution).filter(Institution.id == payload.institution_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    if current_user.role == "APPLICANT" and current_user.institution_id:
        if inst.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create instrument for another institution.")

    existing = db.query(DepositInstrument).filter(
        DepositInstrument.instrument_number == payload.instrument_number
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Instrument number '{payload.instrument_number}' is already registered.")

    v_status, _ = calculate_validity_status(payload.maturity_date)

    instrument = DepositInstrument(
        instrument_number=payload.instrument_number,
        institution_id=payload.institution_id,
        instrument_type=payload.instrument_type,
        issuing_bank=payload.issuing_bank,
        branch_name=payload.branch_name,
        branch_ifsc=payload.branch_ifsc,
        account_number=payload.account_number,
        amount=payload.amount,
        currency=payload.currency,
        issue_date=payload.issue_date,
        maturity_date=payload.maturity_date,
        submission_date=datetime.datetime.now(datetime.timezone.utc).date(),
        lifecycle_status="SUBMITTED",
        validity_status=v_status,
        verification_status="UNVERIFIED",
        lien_marked_to=payload.lien_marked_to or "Regional Officer, AICTE",
        joint_holder_name=payload.joint_holder_name,
        purpose=payload.purpose or "Establishment of Technical Institution Corpus Deposit",
        notes=payload.notes
    )
    db.add(instrument)
    db.flush()

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="INSTRUMENT",
        event_type="INSTRUMENT_REGISTERED",
        details={
            "instrument_number": instrument.instrument_number,
            "bank": instrument.issuing_bank,
            "amount": float(instrument.amount),
            "maturity_date": str(instrument.maturity_date)
        },
        actor=current_user.username
    )

    db.commit()
    db.refresh(instrument)
    return _hydrate_instrument_dto(instrument)


@router.get("/{id}", response_model=DepositInstrumentDetailResponse)
def get_instrument_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Returns full details for a deposit instrument including attached documents,
    verification records, renewal history, and release requests.
    """
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == id).first()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

    if current_user.role == "APPLICANT" and current_user.institution_id:
        if instrument.institution.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    dto = _hydrate_instrument_dto(instrument)
    dto["documents"] = [d for d in instrument.documents if d.status != "REPLACED_ARCHIVED"]
    dto["verification_records"] = instrument.verification_records
    dto["renewals_as_original"] = instrument.renewals_as_original
    dto["release_requests"] = instrument.release_requests

    return dto


@router.put("/{id}", response_model=DepositInstrumentResponse)
def update_instrument(
    id: int,
    payload: DepositInstrumentUpdate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN"))
):
    """Updates permitted instrument details."""
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == id).first()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(instrument, field, val)

    v_status, _ = calculate_validity_status(instrument.maturity_date)
    instrument.validity_status = v_status
    instrument.updated_at = datetime.datetime.now(datetime.timezone.utc)

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="INSTRUMENT",
        event_type="INSTRUMENT_UPDATED",
        details=payload.model_dump(exclude_unset=True, mode="json"),
        actor=current_user.username
    )

    db.commit()
    db.refresh(instrument)
    return _hydrate_instrument_dto(instrument)


@router.post("/{id}/verify")
def trigger_verification(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Executes automated OCR discrepancy checks and external registry validation.
    """
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == id).first()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

    records = run_instrument_verification(db, instrument)
    db.commit()
    db.refresh(instrument)

    return {
        "instrument_id": instrument.id,
        "instrument_number": instrument.instrument_number,
        "verification_status": instrument.verification_status,
        "checks_executed": len(records),
        "results": [
            {
                "method": r.verification_method,
                "source": r.verification_source,
                "result": r.result,
                "evidence": r.evidence_notes,
                "is_simulated": r.is_simulated
            }
            for r in records
        ]
    }


@router.post("/{id}/documents", response_model=InstrumentDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_instrument_document(
    id: int,
    document_category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN", "APPLICANT"))
):
    """
    Uploads and processes supporting files (FDR_RECEIPT, BANK_LIEN_LETTER, etc.)
    Extracts text/bounding boxes and updates repository catalog.
    """
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == id).first()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

    if current_user.role == "APPLICANT" and current_user.institution_id:
        if instrument.institution.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Read and store file
    file_bytes = file.file.read()
    file_size = len(file_bytes)
    sha256_hash = calculate_sha256(file_bytes)

    filename = file.filename or "uploaded_file"
    ext = Path(filename).suffix.lower()
    valid_extensions = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    if ext not in valid_extensions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported format '{ext}'. Allowed: PDF, PNG, JPG.")

    detected_mime = file.content_type or valid_extensions[ext]

    vault_dir = Path(settings.STORAGE_VAULT_PATH) / "instruments" / str(instrument.id)
    vault_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{sha256_hash[:12]}_{Path(filename).name}"
    storage_path = str(vault_dir / safe_name)

    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    # Parse and extract
    parsed = extract_document_content(storage_path, detected_mime)

    # Archive previous version in this category
    prev_doc = db.query(InstrumentDocument).filter(
        InstrumentDocument.instrument_id == instrument.id,
        InstrumentDocument.document_category == document_category,
        InstrumentDocument.status == "ACTIVE"
    ).first()
    new_version = (prev_doc.version + 1) if prev_doc else 1
    if prev_doc:
        prev_doc.status = "REPLACED_ARCHIVED"

    doc = InstrumentDocument(
        instrument_id=instrument.id,
        document_category=document_category,
        original_filename=filename,
        storage_path=storage_path,
        file_size_bytes=file_size,
        mime_type=detected_mime,
        sha256_hash=sha256_hash,
        phash_value=parsed.get("phash"),
        upload_timestamp=datetime.datetime.now(datetime.timezone.utc),
        uploaded_by=current_user.username,
        extraction_status=parsed.get("status", "PROCESSED"),
        extracted_fields_json=json.dumps(parsed.get("extracted_fields", [])),
        extracted_text=parsed.get("text"),
        ocr_performed=parsed.get("ocr_performed", False),
        version=new_version,
        status="ACTIVE"
    )
    db.add(doc)
    db.flush()

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="DOCUMENT",
        entity_id=doc.id,
        event_type="DOCUMENT_UPLOADED",
        details={
            "document_id": doc.id,
            "filename": filename,
            "category": document_category,
            "version": new_version
        },
        actor=current_user.username
    )

    db.commit()
    db.refresh(doc)

    preview = (doc.extracted_text[:180] + "...") if doc.extracted_text and len(doc.extracted_text) > 180 else doc.extracted_text
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
        "extracted_text_preview": preview
    }


@router.post("/{id}/lifecycle")
def transition_lifecycle(
    id: int,
    target_status: str = Form(...),
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN", "APPROVER"))
):
    """
    Explicitly transitions administrative lifecycle state with state-machine validation.
    """
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == id).first()
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found.")

    try:
        update_instrument_lifecycle(db, instrument, target_status, actor=current_user.username, remarks=remarks)
        db.commit()
        db.refresh(instrument)
        return _hydrate_instrument_dto(instrument)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

