"""
AICTE Deposit Manager — Financial Instrument Service
Handles instrument validity calculations, lifecycle state machine transitions,
and formatting utilities for Security Deposits and FDRs.
"""

import datetime
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models import DepositInstrument, AuditEvent, Notification

# Prototype warning window configuration (default: 30 days)
DEFAULT_WARNING_WINDOW_DAYS = 30


def calculate_validity_status(
    maturity_date: Optional[datetime.date],
    warning_days: int = DEFAULT_WARNING_WINDOW_DAYS,
    as_of_date: Optional[datetime.date] = None
) -> Tuple[str, Optional[int]]:
    """
    Computes validity status and remaining days relative to runtime date:
    - ACTIVE_VALID: Unexpired and beyond the warning window.
    - EXPIRING_SOON: Unexpired but matures within warning window (default 30 days).
    - MATURED: Maturity date has passed.
    - UNKNOWN_INCOMPLETE: Maturity date is missing or invalid.
    """
    if maturity_date is None:
        return "UNKNOWN_INCOMPLETE", None

    today = as_of_date or datetime.datetime.now(datetime.timezone.utc).date()
    delta_days = (maturity_date - today).days

    if delta_days < 0:
        return "MATURED", delta_days
    elif delta_days <= warning_days:
        return "EXPIRING_SOON", delta_days
    else:
        return "ACTIVE_VALID", delta_days


VALID_LIFECYCLE_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "ARCHIVED"},
    "SUBMITTED": {"PENDING_VERIFICATION", "ACTIVE", "REJECTED", "ARCHIVED"},
    "PENDING_VERIFICATION": {"ACTIVE", "REJECTED", "RENEWAL_REQUIRED", "SUBMITTED"},
    "ACTIVE": {"RENEWAL_REQUIRED", "RENEWAL_IN_PROGRESS", "MATURED", "RELEASE_REQUESTED", "ARCHIVED"},
    "RENEWAL_REQUIRED": {"RENEWAL_IN_PROGRESS", "MATURED", "RELEASE_REQUESTED", "ACTIVE"},
    "RENEWAL_IN_PROGRESS": {"ACTIVE", "SUPERSEDED", "MATURED", "RENEWAL_REQUIRED"},
    "MATURED": {"RENEWAL_REQUIRED", "RENEWAL_IN_PROGRESS", "RELEASE_REQUESTED", "ARCHIVED"},
    "RELEASE_REQUESTED": {"RELEASED", "ACTIVE", "MATURED", "UNDER_REVIEW"},
    "RELEASED": {"ARCHIVED"},
    "SUPERSEDED": {"ARCHIVED"},
    "REJECTED": {"ARCHIVED", "DRAFT"},
    "ARCHIVED": set()
}


def can_transition_lifecycle(current_status: str, target_status: str) -> bool:
    """Validates whether a lifecycle state transition is legally permissible."""
    if current_status == target_status:
        return True
    allowed = VALID_LIFECYCLE_TRANSITIONS.get(current_status, set())
    return target_status in allowed


def update_instrument_lifecycle(
    db: Session,
    instrument: DepositInstrument,
    new_status: str,
    actor: str = "OFFICER",
    remarks: Optional[str] = None
) -> DepositInstrument:
    """
    Enforces lifecycle state machine transitions and logs chained audit event.
    """
    if not can_transition_lifecycle(instrument.lifecycle_status, new_status):
        raise ValueError(
            f"Invalid lifecycle transition from '{instrument.lifecycle_status}' to '{new_status}'."
        )

    old_status = instrument.lifecycle_status
    instrument.lifecycle_status = new_status
    instrument.updated_at = datetime.datetime.now(datetime.timezone.utc)

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="INSTRUMENT",
        event_type="LIFECYCLE_STATUS_CHANGED",
        details={
            "instrument_number": instrument.instrument_number,
            "old_status": old_status,
            "new_status": new_status,
            "remarks": remarks
        },
        actor=actor
    )

    db.flush()
    return instrument


def format_inr(amount: Decimal | float | int | None) -> str:
    """Formats currency in Indian numbering system (Lakhs and Crores)."""
    if amount is None:
        return "₹0.00"
    try:
        val = float(amount)
        s, *d = str(f"{val:.2f}").split(".")
        r = []
        if len(s) > 3:
            r.append(s[-3:])
            s = s[:-3]
            while len(s) > 2:
                r.append(s[-2:])
                s = s[:-2]
            if s:
                r.append(s)
            formatted = ",".join(reversed(r))
        else:
            formatted = s
        return f"₹{formatted}.{d[0]}" if d else f"₹{formatted}"
    except Exception:
        return f"₹{amount}"


def sync_instrument_validity(instrument: DepositInstrument, warning_days: int = DEFAULT_WARNING_WINDOW_DAYS) -> str:
    """Calculates and updates validity_status on an instrument record in memory."""
    v_status, _ = calculate_validity_status(instrument.maturity_date, warning_days)
    instrument.validity_status = v_status
    return v_status
