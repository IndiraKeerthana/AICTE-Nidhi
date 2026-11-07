"""
AICTE Deposit Manager — Automated Reminders & Notification Service
Generates idempotent reminders for approaching maturities, overdue renewals,
unresolved discrepancies, and pending release reviews.
"""

import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import (
    DepositInstrument, ReleaseRefundRequest, Notification, Institution
)
from app.services.instrument_service import calculate_validity_status, DEFAULT_WARNING_WINDOW_DAYS


def generate_system_notifications(
    db: Session,
    warning_days: int = DEFAULT_WARNING_WINDOW_DAYS,
    as_of_date: Optional[datetime.date] = None
) -> List[Notification]:
    """
    Scans active instruments, verification records, and release requests
    to generate notifications idempotently (no duplicate creation within 24 hours).
    """
    today = as_of_date or datetime.datetime.now(datetime.timezone.utc).date()
    created_notifications: List[Notification] = []

    instruments = db.query(DepositInstrument).all()

    for inst in instruments:
        if inst.lifecycle_status in ("RELEASED", "ARCHIVED", "SUPERSEDED"):
            continue

        v_status, remaining = calculate_validity_status(inst.maturity_date, warning_days, as_of_date=today)

        # 1. Approaching Maturity Warning
        if v_status == "EXPIRING_SOON" and remaining is not None and remaining >= 0:
            existing = db.query(Notification).filter(
                Notification.instrument_id == inst.id,
                Notification.notification_type == "MATURITY_WARNING",
                Notification.trigger_date == today
            ).first()

            if not existing:
                notif = Notification(
                    institution_id=inst.institution_id,
                    instrument_id=inst.id,
                    notification_type="MATURITY_WARNING",
                    trigger_date=today,
                    target_role="OFFICER",
                    title=f"Maturity Warning: FDR #{inst.instrument_number} expires in {remaining} days",
                    message=f"Deposit of ₹{inst.amount:,.2f} at {inst.issuing_bank} is due to mature on {inst.maturity_date}. Timely renewal notice or extension required.",
                    severity="WARNING",
                    is_read=False
                )
                db.add(notif)
                created_notifications.append(notif)

        # 2. Overdue Matured Instrument
        elif v_status == "MATURED":
            existing = db.query(Notification).filter(
                Notification.instrument_id == inst.id,
                Notification.notification_type == "MATURED_OVERDUE",
                Notification.trigger_date == today
            ).first()

            if not existing:
                days_overdue = abs(remaining) if remaining is not None else 0
                notif = Notification(
                    institution_id=inst.institution_id,
                    instrument_id=inst.id,
                    notification_type="MATURED_OVERDUE",
                    trigger_date=today,
                    target_role="OFFICER",
                    title=f"Matured Overdue: FDR #{inst.instrument_number} ({days_overdue} days past maturity)",
                    message=f"Deposit instrument matured on {inst.maturity_date}. Active renewal replacement or formal discharge has not been finalized.",
                    severity="CRITICAL",
                    is_read=False
                )
                db.add(notif)
                created_notifications.append(notif)

        # 3. Verification Pending
        if inst.verification_status in ("PENDING", "UNVERIFIED") and inst.lifecycle_status == "SUBMITTED":
            existing = db.query(Notification).filter(
                Notification.instrument_id == inst.id,
                Notification.notification_type == "VERIFICATION_PENDING",
                Notification.trigger_date == today
            ).first()

            if not existing:
                notif = Notification(
                    institution_id=inst.institution_id,
                    instrument_id=inst.id,
                    notification_type="VERIFICATION_PENDING",
                    trigger_date=today,
                    target_role="OFFICER",
                    title=f"Pending Verification: FDR #{inst.instrument_number}",
                    message=f"New deposit submission from {inst.institution.name if inst.institution else 'Institution'} requires automated document and registry verification.",
                    severity="INFO",
                    is_read=False
                )
                db.add(notif)
                created_notifications.append(notif)

        # 4. Discrepancy Flagged
        if inst.verification_status == "MISMATCH_DETECTED":
            existing = db.query(Notification).filter(
                Notification.instrument_id == inst.id,
                Notification.notification_type == "DISCREPANCY_FLAGGED",
                Notification.trigger_date == today
            ).first()

            if not existing:
                notif = Notification(
                    institution_id=inst.institution_id,
                    instrument_id=inst.id,
                    notification_type="DISCREPANCY_FLAGGED",
                    trigger_date=today,
                    target_role="OFFICER",
                    title=f"Verification Discrepancy: FDR #{inst.instrument_number}",
                    message=f"Automated verification detected conflicting values (amount, bank, or reference) in supporting documents for {inst.issuing_bank}.",
                    severity="WARNING",
                    is_read=False
                )
                db.add(notif)
                created_notifications.append(notif)

    # 5. Release Requests Awaiting Action
    pending_releases = db.query(ReleaseRefundRequest).filter(
        ReleaseRefundRequest.review_status.in_(["SUBMITTED", "UNDER_REVIEW"])
    ).all()
    for rel in pending_releases:
        existing = db.query(Notification).filter(
            Notification.request_id == rel.id,
            Notification.notification_type == "RELEASE_AWAITING_ACTION",
            Notification.trigger_date == today
        ).first()

        if not existing:
            notif = Notification(
                institution_id=rel.institution_id,
                instrument_id=rel.instrument_id,
                request_id=rel.id,
                notification_type="RELEASE_AWAITING_ACTION",
                trigger_date=today,
                target_role="APPROVER",
                title=f"Release Request Awaiting Review: #{rel.request_number}",
                message=f"A formal {rel.request_type.replace('_', ' ').lower()} request has been submitted for scrutiny.",
                severity="INFO",
                is_read=False
            )
            db.add(notif)
            created_notifications.append(notif)

    db.flush()
    return created_notifications

