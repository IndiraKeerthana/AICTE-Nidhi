"""
AICTE Deposit Manager — Release & Refund Requests API
Handles release, discharge, and refund request submission and authorized scrutiny decisions.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReleaseRefundRequest, DepositInstrument, Institution
from app.schemas import (
    ReleaseRefundRequestResponse, ReleaseRefundRequestCreate,
    ReleaseRefundRequestDecision
)
from app.services.release_service import (
    create_release_refund_request, finalize_release_decision,
    PROTOTYPE_RELEASE_CHECKLIST_TEMPLATE
)
from app.api.auth import get_current_user, require_role, UserInfo

router = APIRouter(prefix="/releases", tags=["Release & Refund Requests"])


def _hydrate_release_dto(req: ReleaseRefundRequest) -> dict:
    return {
        "id": req.id,
        "request_number": req.request_number,
        "institution_id": req.institution_id,
        "instrument_id": req.instrument_id,
        "request_type": req.request_type,
        "request_date": req.request_date,
        "reason": req.reason,
        "conditions_checklist_json": req.conditions_checklist_json,
        "review_status": req.review_status,
        "scrutiny_observations": req.scrutiny_observations,
        "decision_record": req.decision_record,
        "decision_date": req.decision_date,
        "decided_by": req.decided_by,
        "decision_remarks": req.decision_remarks,
        "rejection_reason": req.rejection_reason,
        "created_at": req.created_at,
        "updated_at": req.updated_at,
        "institution_name": req.institution.name if req.institution else None,
        "instrument_number": req.instrument.instrument_number if req.instrument else None
    }


@router.get("/checklist-template")
def get_release_checklist_template():
    """Returns the prototype release/refund verification checklist criteria."""
    return PROTOTYPE_RELEASE_CHECKLIST_TEMPLATE


@router.get("", response_model=List[ReleaseRefundRequestResponse])
def list_release_requests(
    review_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Lists release/refund requests with status filtering."""
    query = db.query(ReleaseRefundRequest)

    if current_user.role == "APPLICANT" and current_user.institution_id:
        query = query.join(Institution, ReleaseRefundRequest.institution_id == Institution.id)\
                     .filter(Institution.aicte_permanent_id == current_user.institution_id)

    if review_status and review_status != "ALL":
        query = query.filter(ReleaseRefundRequest.review_status == review_status)

    requests = query.order_by(ReleaseRefundRequest.id.desc()).offset(offset).limit(limit).all()
    return [_hydrate_release_dto(r) for r in requests]


@router.post("", response_model=ReleaseRefundRequestResponse, status_code=status.HTTP_201_CREATED)
def submit_release_request(
    payload: ReleaseRefundRequestCreate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN", "APPLICANT"))
):
    """Submits a release or refund request for scrutiny."""
    try:
        req = create_release_refund_request(
            db=db,
            instrument_id=payload.instrument_id,
            request_type=payload.request_type,
            reason=payload.reason,
            conditions_checklist=payload.conditions_checklist,
            actor=current_user.username
        )
        db.commit()
        db.refresh(req)
        return _hydrate_release_dto(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{id}", response_model=ReleaseRefundRequestResponse)
def get_release_request_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Retrieves full details for a release/refund request."""
    req = db.query(ReleaseRefundRequest).filter(ReleaseRefundRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release request not found.")

    if current_user.role == "APPLICANT" and current_user.institution_id:
        if req.institution.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return _hydrate_release_dto(req)


@router.post("/{id}/decision", response_model=ReleaseRefundRequestResponse)
def record_release_decision(
    id: int,
    payload: ReleaseRefundRequestDecision,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Finalizes statutory decision (APPROVED / REJECTED / RETURNED_FOR_CORRECTION).
    Restricted to authorized Regulation Bureau officers and approvers.
    """
    try:
        req = finalize_release_decision(
            db=db,
            request_id=id,
            decision=payload.decision,
            remarks=payload.remarks,
            conditions_checklist=payload.conditions_checklist,
            decided_by=f"{current_user.full_name} ({current_user.role})"
        )
        db.commit()
        db.refresh(req)
        return _hydrate_release_dto(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

