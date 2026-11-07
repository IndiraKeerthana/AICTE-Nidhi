"""
AICTE Deposit Manager — Release and Refund Workflow Service
Handles release, discharge, and refund requests with configurable conditions checklist,
regulatory scrutiny observations, and authorized decision boundary.
"""

import json
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import (
    DepositInstrument, ReleaseRefundRequest, AuditEvent, Notification
)
from app.services.instrument_service import calculate_validity_status

PROTOTYPE_RELEASE_CHECKLIST_TEMPLATE = {
    "continuous_operation_years_satisfied": {
        "label": "Institution completed prescribed continuous operational period (e.g. 8–10 years per APH norms)",
        "mandatory": True
    },
    "no_pending_student_grievances": {
        "label": "No unresolved student fee complaints or pending court litigations on record",
        "mandatory": True
    },
    "audited_financial_accounts_clean": {
        "label": "Annual compliance affidavits and audited financial balance sheets up to date",
        "mandatory": True
    },
    "competent_authority_in_principle_approval": {
        "label": "In-principle recommendation from Regional Committee / Bureau Head",
        "mandatory": True
    },
    "original_fdr_discharge_undertaking": {
        "label": "Formal discharge undertaking and bank lien release requisition submitted",
        "mandatory": True
    }
}


def create_release_refund_request(
    db: Session,
    instrument_id: int,
    request_type: str = "FULL_RELEASE",
    reason: str = "",
    conditions_checklist: Optional[Dict[str, bool]] = None,
    actor: str = "OFFICER"
) -> ReleaseRefundRequest:
    """
    Submits a release or refund request for an active or matured deposit instrument.
    Sets instrument lifecycle status to RELEASE_REQUESTED.
    """
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == instrument_id).first()
    if not instrument:
        raise ValueError(f"Deposit instrument #{instrument_id} not found.")

    # Check for existing open request
    existing = db.query(ReleaseRefundRequest).filter(
        ReleaseRefundRequest.instrument_id == instrument.id,
        ReleaseRefundRequest.review_status.in_(["SUBMITTED", "UNDER_REVIEW", "RETURNED_FOR_CORRECTION"])
    ).first()
    if existing:
        raise ValueError(f"A release request (#{existing.request_number}) is already pending review for this instrument.")

    # Generate sequential request number
    count = db.query(ReleaseRefundRequest).count() + 1
    req_number = f"REL-2026-{count:04d}"

    # Initialize conditions checklist
    checklist = {}
    for key, item in PROTOTYPE_RELEASE_CHECKLIST_TEMPLATE.items():
        user_val = conditions_checklist.get(key, False) if conditions_checklist else False
        checklist[key] = {
            "label": item["label"],
            "mandatory": item["mandatory"],
            "verified": bool(user_val)
        }

    request = ReleaseRefundRequest(
        request_number=req_number,
        institution_id=instrument.institution_id,
        instrument_id=instrument.id,
        request_type=request_type,
        request_date=datetime.datetime.now(datetime.timezone.utc).date(),
        reason=reason,
        conditions_checklist_json=json.dumps(checklist),
        review_status="SUBMITTED",
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(request)

    instrument.lifecycle_status = "RELEASE_REQUESTED"
    instrument.updated_at = datetime.datetime.now(datetime.timezone.utc)

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="RELEASE",
        entity_id=request.id,
        event_type="RELEASE_REQUEST_SUBMITTED",
        details={
            "request_number": req_number,
            "request_type": request_type,
            "instrument_number": instrument.instrument_number
        },
        actor=actor
    )

    db.flush()
    return request


def finalize_release_decision(
    db: Session,
    request_id: int,
    decision: str,  # APPROVED, REJECTED, RETURNED_FOR_CORRECTION
    remarks: str,
    conditions_checklist: Optional[Dict[str, bool]] = None,
    decided_by: str = "Regional Officer / Competent Authority"
) -> ReleaseRefundRequest:
    """
    Evaluates and records final statutory decision on release/refund request.
    If APPROVED:
      - All mandatory conditions in checklist must be satisfied.
      - Instrument lifecycle transitions to RELEASED.
    If REJECTED:
      - Instrument reverts to appropriate previous status.
    """
    request = db.query(ReleaseRefundRequest).filter(ReleaseRefundRequest.id == request_id).first()
    if not request:
        raise ValueError(f"Release request #{request_id} not found.")

    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == request.instrument_id).first()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Update checklist state if provided
    checklist = json.loads(request.conditions_checklist_json or "{}")
    if conditions_checklist:
        for k, v in conditions_checklist.items():
            if k in checklist:
                checklist[k]["verified"] = bool(v)
            else:
                checklist[k] = {"label": k, "mandatory": True, "verified": bool(v)}
        request.conditions_checklist_json = json.dumps(checklist)

    # If approving, check mandatory checklist items
    if decision == "APPROVED":
        unverified_mandatory = [
            item["label"] for item in checklist.values() if item.get("mandatory") and not item.get("verified")
        ]
        if unverified_mandatory:
            raise ValueError(
                f"Cannot approve release: Mandatory compliance condition(s) unverified: {'; '.join(unverified_mandatory)}."
            )

        request.review_status = "COMPLETED"
        request.decision_record = "APPROVED"
        request.decision_date = now
        request.decided_by = decided_by
        request.decision_remarks = remarks

        if instrument:
            instrument.lifecycle_status = "RELEASED"
            instrument.updated_at = now

    elif decision == "REJECTED":
        request.review_status = "REJECTED"
        request.decision_record = "REJECTED"
        request.decision_date = now
        request.decided_by = decided_by
        request.rejection_reason = remarks

        if instrument:
            v_stat, _ = calculate_validity_status(instrument.maturity_date)
            instrument.lifecycle_status = "MATURED" if v_stat == "MATURED" else "ACTIVE"
            instrument.updated_at = now

    elif decision == "RETURNED_FOR_CORRECTION":
        request.review_status = "RETURNED_FOR_CORRECTION"
        request.decision_remarks = remarks
        request.updated_at = now

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id if instrument else None,
        entity_type="RELEASE",
        entity_id=request.id,
        event_type="RELEASE_DECISION_FINALIZED",
        details={
            "request_number": request.request_number,
            "decision": decision,
            "decided_by": decided_by,
            "remarks": remarks
        },
        actor=decided_by
    )

    db.flush()
    return request

