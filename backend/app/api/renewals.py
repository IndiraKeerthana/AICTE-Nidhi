"""
AICTE Deposit Manager — Renewals & Replacements API
Manages the renewal lifecycle of maturing instruments and registers replacement FDRs.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RenewalRecord, DepositInstrument, Institution
from app.schemas import (
    RenewalRecordResponse, RenewalRecordCreate, RenewalRecordDecision,
    DepositInstrumentResponse
)
from app.services.renewal_service import (
    initiate_renewal_process, register_replacement_instrument, finalize_renewal_decision
)
from app.api.auth import get_current_user, require_role, UserInfo

router = APIRouter(prefix="/renewals", tags=["Renewals & Replacements"])


@router.get("", response_model=List[RenewalRecordResponse])
def list_renewals(
    review_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Lists renewal records with review status filtering."""
    query = db.query(RenewalRecord)

    if current_user.role == "APPLICANT" and current_user.institution_id:
        query = query.join(DepositInstrument, RenewalRecord.original_instrument_id == DepositInstrument.id)\
                     .join(Institution, DepositInstrument.institution_id == Institution.id)\
                     .filter(Institution.aicte_permanent_id == current_user.institution_id)

    if review_status and review_status != "ALL":
        query = query.filter(RenewalRecord.review_status == review_status)

    renewals = query.order_by(RenewalRecord.id.desc()).offset(offset).limit(limit).all()
    return renewals


@router.post("/{instrument_id}/initiate", response_model=RenewalRecordResponse, status_code=status.HTTP_201_CREATED)
def initiate_renewal(
    instrument_id: int,
    payload: RenewalRecordCreate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN", "APPLICANT"))
):
    """Initiates renewal workflow for an instrument approaching or past maturity."""
    try:
        renewal = initiate_renewal_process(
            db=db,
            original_instrument_id=instrument_id,
            new_maturity_date=payload.new_maturity_date,
            actor=current_user.username,
            observations=payload.review_observations
        )

        # If replacement details were supplied in the same payload, register replacement right away
        if payload.replacement_instrument_number and payload.replacement_bank and payload.replacement_amount:
            register_replacement_instrument(
                db=db,
                renewal_id=renewal.id,
                replacement_instrument_number=payload.replacement_instrument_number,
                issuing_bank=payload.replacement_bank,
                amount=payload.replacement_amount,
                new_maturity_date=payload.new_maturity_date,
                actor=current_user.username
            )

        db.commit()
        db.refresh(renewal)
        return renewal
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/replacement")
def register_replacement(
    id: int,
    replacement_instrument_number: str,
    issuing_bank: str,
    amount: float,
    new_maturity_date: str,
    branch_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN", "APPLICANT"))
):
    """Registers a replacement FDR linked to the active renewal record."""
    import datetime
    from decimal import Decimal
    try:
        mat_date = datetime.date.fromisoformat(new_maturity_date)
        replacement = register_replacement_instrument(
            db=db,
            renewal_id=id,
            replacement_instrument_number=replacement_instrument_number,
            issuing_bank=issuing_bank,
            amount=Decimal(str(amount)),
            new_maturity_date=mat_date,
            branch_name=branch_name,
            actor=current_user.username
        )
        db.commit()
        db.refresh(replacement)
        return {
            "renewal_id": id,
            "replacement_instrument_id": replacement.id,
            "replacement_instrument_number": replacement.instrument_number,
            "lifecycle_status": replacement.lifecycle_status,
            "message": "Replacement instrument registered successfully and linked to original FDR."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/decision", response_model=RenewalRecordResponse)
def decide_renewal(
    id: int,
    payload: RenewalRecordDecision,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Finalizes renewal approval or rejection decision.
    Only authorized officers/approvers may record decisions.
    """
    try:
        renewal = finalize_renewal_decision(
            db=db,
            renewal_id=id,
            decision=payload.decision,
            remarks=payload.remarks,
            decided_by=f"{current_user.full_name} ({current_user.role})"
        )
        db.commit()
        db.refresh(renewal)
        return renewal
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

