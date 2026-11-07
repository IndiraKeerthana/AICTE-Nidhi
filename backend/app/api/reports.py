"""
AICTE Deposit Manager — Reports & Exports API
Provides portfolio summary analytics and CSV spreadsheet downloads.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import DepositInstrument, Institution
from app.services.report_service import generate_instruments_csv_export
from app.services.instrument_service import format_inr
from app.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])


@router.get("/instruments/export.csv")
def export_instruments_csv(
    institution_id: Optional[int] = Query(None),
    issuing_bank: Optional[str] = Query(None),
    lifecycle_status: Optional[str] = Query(None),
    validity_status: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Exports filtered security deposit / FDR data to standard CSV.
    Uses real filtered backend data with RFC 4180 sanitization.
    """
    # Enforce applicant scope
    if current_user.role == "APPLICANT" and current_user.institution_id:
        inst = db.query(Institution).filter(Institution.aicte_permanent_id == current_user.institution_id).first()
        institution_id = inst.id if inst else -1

    csv_data = generate_instruments_csv_export(
        db=db,
        institution_id=institution_id,
        issuing_bank=issuing_bank,
        lifecycle_status=lifecycle_status,
        validity_status=validity_status,
        verification_status=verification_status
    )

    import datetime
    filename = f"aicte_deposit_register_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/summary")
def get_reports_summary(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Returns portfolio breakdown by issuing bank, instrument type, and lifecycle state.
    """
    query = db.query(DepositInstrument)
    if current_user.role == "APPLICANT" and current_user.institution_id:
        inst = db.query(Institution).filter(Institution.aicte_permanent_id == current_user.institution_id).first()
        if inst:
            query = query.filter(DepositInstrument.institution_id == inst.id)
        else:
            query = query.filter(DepositInstrument.id == -1)

    instruments = query.all()

    bank_distribution = {}
    type_distribution = {}
    total_val = 0.0

    for inst in instruments:
        amt = float(inst.amount)
        total_val += amt
        bank_distribution[inst.issuing_bank] = bank_distribution.get(inst.issuing_bank, 0.0) + amt
        type_distribution[inst.instrument_type] = type_distribution.get(inst.instrument_type, 0) + 1

    bank_summary = [
        {"bank": b, "total_amount": amt, "formatted_amount": format_inr(amt)}
        for b, amt in sorted(bank_distribution.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "total_instruments_count": len(instruments),
        "total_deposit_value": total_val,
        "formatted_total_value": format_inr(total_val),
        "bank_distribution": bank_summary,
        "type_distribution": type_distribution,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

