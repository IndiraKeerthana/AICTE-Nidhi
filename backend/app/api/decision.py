import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Application, ReviewerAction, AuditEvent, Alert, Document, Finding, ScrutinyRun
from app.api.auth import get_current_user, require_role, UserInfo
from app.services.compliance_rules import compliance_engine

router = APIRouter(tags=["Officer Final Regulatory Decision"])

CATEGORY_DOC_TITLES = {
    "LAND_TITLE_DEED": "Land Registered Title Deed & Conversion Order",
    "BUILDING_PLAN": "Approved Building Plan & Built-up Area Certificate",
    "FIRE_SAFETY_NOC": "Fire and Life Safety Certificate (NOC)",
    "AFFILIATION_LETTER": "University Affiliation Order & Sanction Letter",
    "FACULTY_ROSTER": "Faculty Cadre Roster & Qualifications Sheet",
    "BALANCE_SHEET": "Audited Annual Financial Balance Sheet",
    "LAB_INFRASTRUCTURE_PHOTO": "Laboratory Equipment & Campus Infrastructure Photograph",
    "BOARD_RESOLUTION": "Governing Board Resolution for Approval Application"
}

def is_blocking_finding(finding: Finding) -> bool:
    """
    Determines whether a finding blocks regulatory approval.
    Per AICTE regulatory rules:
    - Findings already RESOLVED or OVERRIDDEN with officer justification do NOT block.
    - Advisory warnings (MEDIUM or LOW severity) do NOT block.
    - Checks that could not be completed (e.g. gateway unavailable, extraction incomplete)
      or automated inferences (e.g. name similarity variation) require officer review
      but do not block approval if the officer decides to approve with justification.
    - Findings block approval if they are active/unresolved AND:
      1. Category is MISSING_DOCUMENT, OR
      2. Severity is CRITICAL, OR
      3. Category is EXPIRED_DOCUMENT, OR
      4. Category is INTEGRITY_ANOMALY and severity in ("CRITICAL", "HIGH"), OR
      5. Category is RECORD_MISMATCH with evidence_classification == "VERIFIED_FACT" and severity in ("CRITICAL", "HIGH"), OR
      6. Category is AUTHORITY with evidence_classification == "VERIFIED_FACT" and severity in ("CRITICAL", "HIGH").
    """
    if finding.review_status in ("RESOLVED", "OVERRIDDEN"):
        return False

    if finding.category == "MISSING_DOCUMENT":
        return True

    if finding.severity == "CRITICAL":
        return True

    if finding.category == "EXPIRED_DOCUMENT" and finding.severity in ("CRITICAL", "HIGH"):
        return True

    if finding.category == "INTEGRITY_ANOMALY" and finding.severity in ("CRITICAL", "HIGH"):
        return True

    if finding.category == "RECORD_MISMATCH" and finding.evidence_classification == "VERIFIED_FACT" and finding.severity in ("CRITICAL", "HIGH"):
        return True

    if finding.category == "AUTHORITY" and finding.evidence_classification == "VERIFIED_FACT" and finding.severity in ("CRITICAL", "HIGH"):
        return True

    return False


def validate_approval_eligibility(app: Application, db: Session) -> list[str]:
    """
    Validates regulatory requirements before an approval recommendation can be recorded:
    1. Scrutiny completeness: Scrutiny pipeline must have executed and not be failed or running.
    2. Mandatory documents: All mandatory attachments prescribed by APH rules must be uploaded.
    3. Blocking findings: No unresolved CRITICAL or HIGH-severity statutory findings may remain.
    Returns a list of human-readable blocking reasons (empty if eligible).
    """
    blocking_reasons: list[str] = []

    # 1. Scrutiny Stage Completion
    if not app.scrutiny_runs:
        blocking_reasons.append("Automated scrutiny has not been performed on this application.")
    else:
        latest_run = max(app.scrutiny_runs, key=lambda r: (r.run_number or 0, r.id or 0))
        if latest_run.status in ("RUNNING", "QUEUED"):
            blocking_reasons.append(
                f"Automated scrutiny run #{latest_run.run_number} is still in progress ({latest_run.status}). Scrutiny must complete before approval."
            )
        elif latest_run.status == "FAILED":
            blocking_reasons.append(
                f"Latest automated scrutiny run #{latest_run.run_number} failed. Application must undergo successful re-scrutiny before approval."
            )

    # 2. Mandatory Documents Completeness
    mandatory_codes = compliance_engine.get_mandatory_documents(app.category)
    active_docs = [d for d in app.documents if d.status != "REPLACED_ARCHIVED"]
    submitted_categories = {d.document_category for d in active_docs}

    missing_docs = [code for code in mandatory_codes if code not in submitted_categories]
    if missing_docs:
        doc_names = [CATEGORY_DOC_TITLES.get(code, code) for code in missing_docs]
        blocking_reasons.append(
            f"Mandatory document(s) missing for category '{app.category}': {', '.join(doc_names)} ({', '.join(missing_docs)})."
        )

    # 2b. Readable Document Extraction Validation
    for doc in active_docs:
        if doc.status == "EXTRACTION_FAILED":
            blocking_reasons.append(
                f"Document extraction incomplete for '{doc.original_filename}' ({doc.document_category}). Legible attachment or OCR processing required."
            )

    # 3. Unresolved Blocking Findings
    for finding in app.findings:
        if is_blocking_finding(finding):
            blocking_reasons.append(
                f"Unresolved blocking finding [{finding.finding_code}] ({finding.category}, {finding.severity}): {finding.title} — {finding.description}"
            )

    return blocking_reasons


class DecisionPayload(BaseModel):
    decision: str = Field(..., json_schema_extra={"example": "RECOMMEND_APPROVAL"}) # RECOMMEND_APPROVAL, RECOMMEND_REJECTION, DEFICIENCY_NOTICE
    justification_remarks: str = Field(..., min_length=10, json_schema_extra={"example": "All statutory checks verified. Recommended for Approval by Scrutiny Committee."})
    officer_name: str | None = Field(None, json_schema_extra={"example": "Prof. R. K. Verma (Competent Authority)"})


@router.get("/applications/{id}/approval-eligibility")
def check_approval_eligibility(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Checks regulatory approval eligibility and returns any outstanding blocking reasons.
    """
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    blocking_reasons = validate_approval_eligibility(app, db)
    return {
        "application_id": app.id,
        "application_number": app.application_number,
        "is_eligible": len(blocking_reasons) == 0,
        "blocking_reasons": blocking_reasons,
        "is_finalized": app.status in ("APPROVED", "REJECTED") or app.final_decision in ("RECOMMEND_APPROVAL", "RECOMMEND_REJECTION"),
        "final_decision": app.final_decision,
        "status": app.status
    }


@router.post("/applications/{id}/decision")
def record_final_decision(
    id: int,
    payload: DecisionPayload,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Final Human Authority Decision Boundary with P0 Backend Gating:
    Records statutory approval/rejection or deficiency decision.
    Strictly enforced in backend:
    - Applicants are forbidden (403) from recording decisions.
    - Terminal states (APPROVED, REJECTED) cannot be overwritten (409 Conflict) unless reopened.
    - Approval recommendations are strictly gated (422 Unprocessable Entity) if mandatory documents are missing,
      scrutiny is incomplete, or unresolved blocking findings exist.
    """

    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    valid_decisions = {"RECOMMEND_APPROVAL", "RECOMMEND_REJECTION", "DEFICIENCY_NOTICE"}
    if payload.decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{payload.decision}'. Allowed statutory decisions: {list(valid_decisions)}"
        )

    # 1. Enforce Terminal State Immutability
    if app.status in ("APPROVED", "REJECTED") or app.final_decision in ("RECOMMEND_APPROVAL", "RECOMMEND_REJECTION"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Application decision has already been finalized ({app.final_decision or app.status}) by {app.decided_by or 'Authorised Officer'}. "
                "Final decisions cannot be overwritten unless formally reopened via an authorized review workflow (return-to-review)."
            )
        )

    # 2. Enforce Approval Eligibility Gating
    if payload.decision == "RECOMMEND_APPROVAL":
        blocking_reasons = validate_approval_eligibility(app, db)
        if blocking_reasons:
            reasons_summary = "; ".join(blocking_reasons)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Approval blocked: Application has {len(blocking_reasons)} incomplete requirement(s): {reasons_summary}"
            )

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    deciding_officer = payload.officer_name or current_user.full_name or "Competent Authority"

    app.final_decision = payload.decision
    app.decision_remarks = payload.justification_remarks
    app.decided_by = deciding_officer
    app.decided_at = now_utc

    if payload.decision == "RECOMMEND_APPROVAL":
        app.status = "APPROVED"
    elif payload.decision == "RECOMMEND_REJECTION":
        app.status = "REJECTED"
    elif payload.decision == "DEFICIENCY_NOTICE":
        app.status = "DEFICIENCY_FLAGGED"

    if payload.decision in ("RECOMMEND_APPROVAL", "RECOMMEND_REJECTION"):
        active_alerts = db.query(Alert).filter(
            Alert.application_id == app.id,
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
        ).all()
        for a in active_alerts:
            a.status = "RESOLVED"

    # Record ReviewerAction entry
    action = ReviewerAction(
        application_id=app.id,
        action_type=payload.decision,
        justification_remarks=payload.justification_remarks,
        reviewer_name=deciding_officer,
        created_at=now_utc
    )
    db.add(action)

    # Record Hash-Chained Audit Event
    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="OFFICER_FINAL_DECISION_RECORDED",
        details={
            "decision": payload.decision,
            "justification": payload.justification_remarks,
            "officer": deciding_officer,
            "role": current_user.role,
            "resulting_status": app.status
        },
        actor=deciding_officer
    )

    db.commit()
    db.refresh(app)

    return {
        "message": "Regulatory statutory decision recorded successfully.",
        "application_number": app.application_number,
        "status": app.status,
        "final_decision": app.final_decision,
        "decided_by": app.decided_by,
        "decided_at": app.decided_at
    }
