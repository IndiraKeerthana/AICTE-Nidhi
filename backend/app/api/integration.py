import uuid
import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, status, UploadFile, File, Form, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models import Application, Document, Finding, ScrutinyRun, AuditEvent, ExtractedField
from app.services.baseline_service import ensure_baseline_records
from app.services.orchestrator import execute_automated_scrutiny
from app.services.storage import validate_and_store_document
from app.services.document_parser import extract_document_content
from pydantic import BaseModel, Field

router = APIRouter(prefix="/integration/v1", tags=["Portal Integration Adapter"])

def verify_integration_client(
    x_integration_key: str | None = Header(None, description="API Client Key for Authorized Portal Access"),
    x_correlation_id: str | None = Header(None, description="Request correlation identifier"),
    x_idempotency_key: str | None = Header(None, description="Idempotency key for deduplication")
) -> dict:
    if not x_integration_key or x_integration_key != settings.INTEGRATION_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Integration-Key. Access denied."
        )
    return {
        "correlation_id": x_correlation_id or str(uuid.uuid4()),
        "idempotency_key": x_idempotency_key
    }

class IntegrationAppPayload(BaseModel):
    institution_aicte_id: str = Field(..., json_schema_extra={"example": "1-9988776655"})
    institution_name: str = Field(..., json_schema_extra={"example": "Sample Institute of Technology"})
    application_category: str = Field("INCREASE_INTAKE", json_schema_extra={"example": "INCREASE_INTAKE"})
    academic_year: str = Field("2026-2027", json_schema_extra={"example": "2026-2027"})
    declared_programme: str = Field("ENGINEERING_AND_TECHNOLOGY")
    declared_course: str = Field("Computer Science & Engineering")
    declared_intake: int = Field(120, json_schema_extra={"example": 120})
    declared_land_acres: float = Field(8.25, json_schema_extra={"example": 8.25})

@router.post("/applications", status_code=status.HTTP_201_CREATED)
def submit_application_from_portal(
    payload: IntegrationAppPayload,
    response: Response,
    db: Session = Depends(get_db),
    auth_ctx: dict = Depends(verify_integration_client)
):
    """
    Core Integration Endpoint: Ingests application submission from external AICTE portal.
    Supports idempotency via X-Idempotency-Key.
    """
    correlation_id = auth_ctx["correlation_id"]
    idempotency_key = auth_ctx["idempotency_key"]
    response.headers["X-Correlation-ID"] = correlation_id

    # Check idempotency
    if idempotency_key:
        existing_app = db.query(Application).filter(Application.idempotency_key == idempotency_key).first()
        if existing_app:
            return {
                "message": "Idempotent request: returning existing application.",
                "tracking_id": existing_app.tracking_id,
                "application_number": existing_app.application_number,
                "status": existing_app.status,
                "is_duplicate_event": True,
                "integration_mode": "DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION"
            }

    # Ensure institution and baseline records exist
    inst = ensure_baseline_records(
        db=db,
        aicte_id=payload.institution_aicte_id,
        inst_name=payload.institution_name
    )

    tracking_id = f"TRK-{uuid.uuid4().hex[:12].upper()}"
    app_num = f"APP-2026-{uuid.uuid4().hex[:6].upper()}"

    app = Application(
        application_number=app_num,
        tracking_id=tracking_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        institution_id=inst.id,
        category=payload.application_category,
        academic_year=payload.academic_year,
        status="SUBMITTED",
        declared_programme=payload.declared_programme,
        declared_course=payload.declared_course,
        declared_intake=payload.declared_intake,
        declared_land_acres=payload.declared_land_acres
    )
    db.add(app)
    db.flush()

    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="INTEGRATION_SUBMISSION_RECEIVED",
        details={
            "tracking_id": tracking_id,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "source": "AICTE_PORTAL_ADAPTER"
        },
        actor="PORTAL_INTEGRATION_SERVICE"
    )

    # Automatically trigger scrutiny pipeline
    scrutiny_run = execute_automated_scrutiny(db, app.id, trigger_source="PORTAL_INTEGRATION")

    db.commit()
    return {
        "status": "ACCEPTED",
        "tracking_id": tracking_id,
        "application_number": app.application_number,
        "scrutiny_run_number": scrutiny_run.run_number,
        "scrutiny_status": scrutiny_run.status,
        "integration_mode": "DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION",
        "correlation_id": correlation_id
    }

@router.get("/applications/{tracking_id}/status")
def get_application_scrutiny_status(
    tracking_id: str,
    response: Response,
    db: Session = Depends(get_db),
    auth_ctx: dict = Depends(verify_integration_client)
):
    response.headers["X-Correlation-ID"] = auth_ctx["correlation_id"]
    app = db.query(Application).filter(Application.tracking_id == tracking_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tracking ID '{tracking_id}' not found.")

    latest_run = db.query(ScrutinyRun).filter(ScrutinyRun.application_id == app.id).order_by(ScrutinyRun.run_number.desc()).first()

    return {
        "tracking_id": app.tracking_id,
        "application_number": app.application_number,
        "application_status": app.status,
        "latest_scrutiny_run": {
            "run_number": latest_run.run_number if latest_run else None,
            "status": latest_run.status if latest_run else "PENDING",
            "ruleset_version": latest_run.ruleset_version if latest_run else None,
            "total_checks": latest_run.total_checks if latest_run else 0,
            "passed": latest_run.passed_checks if latest_run else 0,
            "failed": latest_run.failed_checks if latest_run else 0,
            "warnings": latest_run.warnings_count if latest_run else 0,
            "completed_at": latest_run.completed_at if latest_run else None
        },
        "open_deficiencies_count": db.query(Finding).filter(Finding.application_id == app.id, Finding.review_status == "OPEN").count(),
        "integration_mode": "DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION"
    }

@router.get("/applications/{tracking_id}/report")
def get_scrutiny_report(
    tracking_id: str,
    response: Response,
    db: Session = Depends(get_db),
    auth_ctx: dict = Depends(verify_integration_client)
):
    response.headers["X-Correlation-ID"] = auth_ctx["correlation_id"]
    app = db.query(Application).filter(Application.tracking_id == tracking_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tracking ID '{tracking_id}' not found.")

    latest_run = db.query(ScrutinyRun).filter(ScrutinyRun.application_id == app.id).order_by(ScrutinyRun.run_number.desc()).first()
    checks = latest_run.check_results if latest_run else []
    findings = app.findings

    return {
        "report_metadata": {
            "tracking_id": app.tracking_id,
            "application_number": app.application_number,
            "institution_name": app.institution.name,
            "category": app.category,
            "academic_year": app.academic_year,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "integration_mode": "DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION"
        },
        "scrutiny_summary": {
            "run_number": latest_run.run_number if latest_run else 1,
            "status": latest_run.status if latest_run else "PENDING",
            "ruleset_version": latest_run.ruleset_version if latest_run else "2025-2026.v1",
            "total_checks": latest_run.total_checks if latest_run else 0,
            "passed_checks": latest_run.passed_checks if latest_run else 0,
            "failed_checks": latest_run.failed_checks if latest_run else 0,
            "duration_ms": latest_run.execution_duration_ms if latest_run else 0,
        },
        "checks_executed": [
            {
                "check_code": c.check_code,
                "category": c.category,
                "status": c.status,
                "expected": c.expected_value,
                "observed": c.observed_value,
                "explanation": c.explanation,
                "requires_review": c.requires_human_review
            } for c in checks
        ],
        "findings": [
            {
                "finding_code": f.finding_code,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "expected_value": f.expected_value,
                "observed_value": f.observed_value,
                "rule_code": f.rule_code,
                "recommended_action": f.recommended_action,
                "status": f.review_status,
                "evidence_class": f.evidence_classification
            } for f in findings
        ]
    }

@router.post("/applications/{tracking_id}/rectifications")
def submit_rectification_replacement(
    tracking_id: str,
    document_category: str = Form(...),
    file: UploadFile = File(...),
    response: Response = None,
    db: Session = Depends(get_db),
    auth_ctx: dict = Depends(verify_integration_client)
):
    """
    Submits a replacement document to rectify an existing deficiency.
    Automatically marks older document as REPLACED_ARCHIVED and re-runs scrutiny.
    """
    app = db.query(Application).filter(Application.tracking_id == tracking_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tracking ID '{tracking_id}' not found.")

    # Archive previous document for this category
    prev_doc = db.query(Document).filter(
        Document.application_id == app.id,
        Document.document_category == document_category,
        Document.status != "REPLACED_ARCHIVED"
    ).first()
    if prev_doc:
        prev_doc.status = "REPLACED_ARCHIVED"

    # Store new document
    storage_path, sha256_hash, file_size, detected_mime = validate_and_store_document(app.id, file)
    parsed = extract_document_content(storage_path, detected_mime)

    new_doc = Document(
        application_id=app.id,
        document_category=document_category,
        original_filename=file.filename or "replacement_doc",
        storage_path=storage_path,
        file_size_bytes=file_size,
        mime_type=detected_mime,
        sha256_hash=sha256_hash,
        status=parsed.get("status", "PROCESSED"),
        page_count=parsed.get("page_count", 1),
        extracted_text=parsed.get("extracted_text", ""),
        phash_value=parsed.get("phash"),
        pdf_metadata_json=parsed.get("metadata_json"),
        incremental_updates_count=parsed.get("incremental_updates_count", 0),
        ocr_needed=parsed.get("ocr_needed", False),
        ocr_performed=parsed.get("ocr_performed", False),
        ocr_engine_available=parsed.get("ocr_engine_available", True)
    )
    db.add(new_doc)
    db.flush()

    for field_info in parsed.get("extracted_fields", []):
        ef = ExtractedField(
            document_id=new_doc.id,
            field_key=field_info["field_key"],
            field_value=field_info["field_value"],
            normalized_value=field_info.get("normalized_value"),
            confidence_score=field_info.get("confidence_score", 1.0),
            page_number=field_info.get("page_number", 1),
            source_snippet=field_info.get("source_snippet"),
            extraction_method=field_info.get("extraction_method", parsed.get("extraction_method"))
        )
        db.add(ef)

    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="DOCUMENT_RECTIFIED_VIA_INTEGRATION",
        details={
            "document_category": document_category,
            "filename": file.filename,
            "previous_document_id": prev_doc.id if prev_doc else None,
            "new_document_id": new_doc.id
        },
        actor="PORTAL_INTEGRATION_SERVICE"
    )

    # Re-run automated scrutiny (Run #2)
    new_run = execute_automated_scrutiny(db, app.id, trigger_source="RECTIFICATION_RE_SCRUTINY")

    db.commit()
    return {
        "status": "RECTIFICATION_PROCESSED",
        "tracking_id": app.tracking_id,
        "new_scrutiny_run_number": new_run.run_number,
        "new_run_status": new_run.status,
        "summary": new_run.summary_notes,
        "integration_mode": "DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION"
    }
