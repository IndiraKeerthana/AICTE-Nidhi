"""
AICTE Deposit Manager — Institutions API
Lists institutions, creates institution records, and retrieves linked deposit instruments.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Institution, DepositInstrument
from app.schemas import InstitutionCreate, InstitutionResponse, DepositInstrumentResponse
from app.services.instrument_service import format_inr, calculate_validity_status, DEFAULT_WARNING_WINDOW_DAYS
from app.api.auth import get_current_user, require_role, UserInfo

router = APIRouter(prefix="/institutions", tags=["Institutions"])


@router.get("", response_model=List[InstitutionResponse])
def list_institutions(
    search: Optional[str] = Query(None, description="Search by name, AICTE ID or state"),
    state: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Lists institutions with deposit instrument counts."""
    query = db.query(Institution)

    if current_user.role == "APPLICANT" and current_user.institution_id:
        query = query.filter(Institution.aicte_permanent_id == current_user.institution_id)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Institution.name.ilike(s),
                Institution.aicte_permanent_id.ilike(s),
                Institution.district.ilike(s),
                Institution.state.ilike(s)
            )
        )

    if state and state != "ALL":
        query = query.filter(Institution.state == state)

    institutions = query.order_by(Institution.name.asc()).offset(offset).limit(limit).all()

    results = []
    for inst in institutions:
        inst_dto = {
            "id": inst.id,
            "aicte_permanent_id": inst.aicte_permanent_id,
            "institution_code": inst.institution_code,
            "name": inst.name,
            "institution_type": inst.institution_type,
            "address": inst.address,
            "state": inst.state,
            "district": inst.district,
            "contact_email": inst.contact_email,
            "contact_phone": inst.contact_phone,
            "record_status": inst.record_status,
            "created_at": inst.created_at,
            "updated_at": inst.updated_at,
            "instruments_count": len(inst.instruments)
        }
        results.append(inst_dto)

    return results


@router.post("", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
def create_institution(
    payload: InstitutionCreate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN"))
):
    """Registers a new institution entity."""
    existing = db.query(Institution).filter(
        Institution.aicte_permanent_id == payload.aicte_permanent_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Institution with Permanent ID '{payload.aicte_permanent_id}' already exists."
        )

    inst = Institution(
        aicte_permanent_id=payload.aicte_permanent_id,
        institution_code=payload.institution_code,
        name=payload.name,
        institution_type=payload.institution_type or "TECHNICAL_INSTITUTE",
        address=payload.address or "Campus Address",
        state=payload.state or "Maharashtra",
        district=payload.district or "Pune",
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        record_status=payload.record_status or "ACTIVE"
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)

    return {
        "id": inst.id,
        "aicte_permanent_id": inst.aicte_permanent_id,
        "institution_code": inst.institution_code,
        "name": inst.name,
        "institution_type": inst.institution_type,
        "address": inst.address,
        "state": inst.state,
        "district": inst.district,
        "contact_email": inst.contact_email,
        "contact_phone": inst.contact_phone,
        "record_status": inst.record_status,
        "created_at": inst.created_at,
        "updated_at": inst.updated_at,
        "instruments_count": 0
    }


@router.get("/{id}")
def get_institution_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Returns institution profile and all associated security deposits/FDRs."""
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    if current_user.role == "APPLICANT" and current_user.institution_id:
        if inst.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    instruments = []
    total_val = 0.0
    for i in inst.instruments:
        v_status, rem = calculate_validity_status(i.maturity_date, DEFAULT_WARNING_WINDOW_DAYS)
        total_val += float(i.amount)
        instruments.append({
            "id": i.id,
            "instrument_number": i.instrument_number,
            "bank": i.issuing_bank,
            "amount": float(i.amount),
            "formatted_amount": format_inr(i.amount),
            "maturity_date": str(i.maturity_date),
            "remaining_days": rem,
            "validity_status": v_status,
            "lifecycle_status": i.lifecycle_status,
            "verification_status": i.verification_status
        })

    return {
        "id": inst.id,
        "aicte_permanent_id": inst.aicte_permanent_id,
        "institution_code": inst.institution_code,
        "name": inst.name,
        "institution_type": inst.institution_type,
        "address": inst.address,
        "state": inst.state,
        "district": inst.district,
        "contact_email": inst.contact_email,
        "contact_phone": inst.contact_phone,
        "record_status": inst.record_status,
        "created_at": inst.created_at,
        "instruments": instruments,
        "total_deposit_value": total_val,
        "formatted_total_value": format_inr(total_val)
    }

