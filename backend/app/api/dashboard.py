"""
AICTE Deposit Manager — Dashboard Metrics API
Provides aggregated KPI metrics, upcoming maturities, and status distributions.
"""

import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    DepositInstrument, ReleaseRefundRequest, RenewalRecord, AuditEvent, Institution
)
from app.schemas import DashboardMetricsResponse
from app.services.instrument_service import (
    calculate_validity_status, format_inr, DEFAULT_WARNING_WINDOW_DAYS
)
from app.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Computes real database-derived dashboard KPI statistics and upcoming deadlines.
    Restricts to institution records if user role is APPLICANT.
    """
    query = db.query(DepositInstrument)
    if current_user.role == "APPLICANT" and current_user.institution_id:
        inst = db.query(Institution).filter(Institution.aicte_permanent_id == current_user.institution_id).first()
        if inst:
            query = query.filter(DepositInstrument.institution_id == inst.id)
        else:
            query = query.filter(DepositInstrument.id == -1)

    instruments = query.all()
    today = datetime.datetime.now(datetime.timezone.utc).date()

    total_instruments = len(instruments)
    active_valid_count = 0
    expiring_soon_count = 0
    matured_count = 0
    pending_verification_count = 0
    total_val = Decimal("0.00")

    status_counts = {}
    validity_counts = {"ACTIVE_VALID": 0, "EXPIRING_SOON": 0, "MATURED": 0, "UNKNOWN_INCOMPLETE": 0}

    upcoming = []
    bank_totals = {}
    bank_counts = {}

    for inst in instruments:
        if inst.amount:
            total_val += Decimal(str(inst.amount))

        bank_totals[inst.issuing_bank] = bank_totals.get(inst.issuing_bank, 0.0) + float(inst.amount or 0)
        bank_counts[inst.issuing_bank] = bank_counts.get(inst.issuing_bank, 0) + 1

        # Lifecycle distribution
        l_stat = inst.lifecycle_status
        status_counts[l_stat] = status_counts.get(l_stat, 0) + 1

        if l_stat in ("PENDING_VERIFICATION", "SUBMITTED") or inst.verification_status in ("PENDING", "UNVERIFIED"):
            pending_verification_count += 1

        # Validity calculations
        v_stat, remaining = calculate_validity_status(inst.maturity_date, DEFAULT_WARNING_WINDOW_DAYS, as_of_date=today)
        validity_counts[v_stat] = validity_counts.get(v_stat, 0) + 1

        if v_stat == "ACTIVE_VALID":
            active_valid_count += 1
        elif v_stat == "EXPIRING_SOON":
            expiring_soon_count += 1
            upcoming.append({
                "id": inst.id,
                "instrument_number": inst.instrument_number,
                "institution_name": inst.institution.name if inst.institution else "Unknown",
                "issuing_bank": inst.issuing_bank,
                "amount": float(inst.amount),
                "formatted_amount": format_inr(inst.amount),
                "maturity_date": str(inst.maturity_date),
                "days_remaining": remaining,
                "validity_status": v_stat,
                "lifecycle_status": inst.lifecycle_status
            })
        elif v_stat == "MATURED":
            matured_count += 1

    # Sort upcoming maturities by shortest remaining days
    upcoming.sort(key=lambda x: x["days_remaining"] if x.get("days_remaining") is not None else 9999)

    # Renewals pending count
    renewals_query = db.query(RenewalRecord).filter(
        RenewalRecord.review_status.in_(["PENDING_REVIEW", "CORRECTIONS_REQUESTED"])
    )
    renewals_pending = renewals_query.count()

    # Release requests pending count
    releases_query = db.query(ReleaseRefundRequest).filter(
        ReleaseRefundRequest.review_status.in_(["SUBMITTED", "UNDER_REVIEW", "RETURNED_FOR_CORRECTION"])
    )
    release_requests_pending = releases_query.count()

    # Status distribution payload for charts
    status_distribution = [
        {"status": k, "count": v} for k, v in status_counts.items()
    ]

    # Recent Audit Activity
    audit_events = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(10).all()
    recent_activity = [
        {
            "id": a.id,
            "event_type": a.event_type,
            "actor": a.actor,
            "entity_type": a.entity_type,
            "instrument_id": a.instrument_id,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in audit_events
    ]

    return {
        "total_instruments": total_instruments,
        "active_valid_instruments": active_valid_count,
        "expiring_soon_instruments": expiring_soon_count,
        "matured_instruments": matured_count,
        "pending_verification": pending_verification_count,
        "renewals_pending": renewals_pending,
        "release_requests_pending": release_requests_pending,
        "total_deposit_value": float(total_val),
        "formatted_total_value": format_inr(total_val),
        "warning_window_days": DEFAULT_WARNING_WINDOW_DAYS,
        "status_distribution": status_distribution,
        "upcoming_maturities": upcoming[:8],
        "recent_activity": recent_activity,
        "bank_distribution": [
            {"bank": bank, "count": bank_counts[bank], "total_amount": amount}
            for bank, amount in sorted(bank_totals.items(), key=lambda item: item[1], reverse=True)
        ]
    }

