"""
AICTE Deposit Manager — Renewal & Replacement Workflow Service
Manages instrument lifecycle transitions upon maturity and preserves
historical links between original and renewed instruments.
"""

import datetime
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models import (
    DepositInstrument, RenewalRecord, AuditEvent, Notification,
    InstrumentDocument
)
from app.services.instrument_service import update_instrument_lifecycle, calculate_validity_status


def initiate_renewal_process(
    db: Session,
    original_instrument_id: int,
    new_maturity_date: datetime.date,
    actor: str = "OFFICER",
    observations: Optional[str] = None
) -> RenewalRecord:
    """
    Initiates a renewal workflow for an instrument approaching or past maturity.
    Prevents duplicate open renewal records and updates original instrument lifecycle.
    """
    instrument = db.query(DepositInstrument).filter(DepositInstrument.id == original_instrument_id).first()
    if not instrument:
        raise ValueError(f"Deposit instrument #{original_instrument_id} not found.")

    # Check for existing open renewal
    existing_open = db.query(RenewalRecord).filter(
        RenewalRecord.original_instrument_id == instrument.id,
        RenewalRecord.review_status.in_(["PENDING_REVIEW", "CORRECTIONS_REQUESTED"])
    ).first()
    if existing_open:
        raise ValueError(f"An active renewal record (#{existing_open.id}) is already pending review for this instrument.")

    today = datetime.datetime.now(datetime.timezone.utc).date()
    if new_maturity_date <= today:
        raise ValueError("New maturity date must be in the future.")

    # Update original instrument status to RENEWAL_IN_PROGRESS
    if instrument.lifecycle_status in ("ACTIVE", "RENEWAL_REQUIRED", "MATURED"):
        update_instrument_lifecycle(
            db, instrument, "RENEWAL_IN_PROGRESS", actor=actor, remarks="Renewal process initiated."
        )

    renewal = RenewalRecord(
        original_instrument_id=instrument.id,
        previous_maturity_date=instrument.maturity_date,
        new_maturity_date=new_maturity_date,
        submission_date=today,
        review_status="PENDING_REVIEW",
        review_observations=observations,
        reviewed_by=actor,
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(renewal)
    db.flush()

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="RENEWAL",
        entity_id=renewal.id,
        event_type="RENEWAL_INITIATED",
        details={
            "original_instrument_number": instrument.instrument_number,
            "previous_maturity_date": str(instrument.maturity_date),
            "new_maturity_date": str(new_maturity_date),
            "renewal_record_id": renewal.id
        },
        actor=actor
    )

    db.flush()
    return renewal


def register_replacement_instrument(
    db: Session,
    renewal_id: int,
    replacement_instrument_number: str,
    issuing_bank: str,
    amount: Decimal,
    new_maturity_date: datetime.date,
    issue_date: Optional[datetime.date] = None,
    branch_name: Optional[str] = None,
    actor: str = "OFFICER"
) -> DepositInstrument:
    """
    Creates and links a replacement instrument to the original instrument,
    preserving historical continuity and updating the renewal record.
    """
    renewal = db.query(RenewalRecord).filter(RenewalRecord.id == renewal_id).first()
    if not renewal:
        raise ValueError(f"Renewal record #{renewal_id} not found.")

    original = db.query(DepositInstrument).filter(DepositInstrument.id == renewal.original_instrument_id).first()
    if not original:
        raise ValueError("Associated original instrument not found.")

    # Check that replacement instrument number is unique
    existing_num = db.query(DepositInstrument).filter(
        DepositInstrument.instrument_number == replacement_instrument_number
    ).first()
    if existing_num:
        raise ValueError(f"Instrument number '{replacement_instrument_number}' already exists in system.")

    validity, _ = calculate_validity_status(new_maturity_date)

    replacement = DepositInstrument(
        instrument_number=replacement_instrument_number,
        institution_id=original.institution_id,
        instrument_type=original.instrument_type,
        issuing_bank=issuing_bank,
        branch_name=branch_name or original.branch_name,
        branch_ifsc=original.branch_ifsc,
        amount=amount,
        currency="INR",
        issue_date=issue_date or datetime.datetime.now(datetime.timezone.utc).date(),
        maturity_date=new_maturity_date,
        submission_date=datetime.datetime.now(datetime.timezone.utc).date(),
        lifecycle_status="PENDING_VERIFICATION",
        validity_status=validity,
        verification_status="UNVERIFIED",
        original_instrument_id=original.id,
        renewal_count=original.renewal_count + 1,
        lien_marked_to=original.lien_marked_to,
        joint_holder_name=original.joint_holder_name,
        purpose=original.purpose,
        notes=f"Renewal replacement for original FDR #{original.instrument_number}."
    )
    db.add(replacement)
    db.flush()

    renewal.replacement_instrument_id = replacement.id
    renewal.new_maturity_date = new_maturity_date

    AuditEvent.create_chained(
        db=db,
        instrument_id=replacement.id,
        entity_type="RENEWAL",
        entity_id=renewal.id,
        event_type="REPLACEMENT_INSTRUMENT_REGISTERED",
        details={
            "original_instrument_id": original.id,
            "original_instrument_number": original.instrument_number,
            "replacement_instrument_number": replacement.instrument_number,
            "renewal_count": replacement.renewal_count
        },
        actor=actor
    )

    db.flush()
    return replacement


def finalize_renewal_decision(
    db: Session,
    renewal_id: int,
    decision: str,  # APPROVED, REJECTED, CORRECTIONS_REQUESTED
    remarks: str,
    decided_by: str = "Regulation Bureau Officer"
) -> RenewalRecord:
    """
    Finalizes renewal evaluation:
    - If APPROVED: Original becomes SUPERSEDED; replacement becomes ACTIVE.
    - If REJECTED: Original reverts to RENEWAL_REQUIRED; replacement becomes REJECTED.
    """
    renewal = db.query(RenewalRecord).filter(RenewalRecord.id == renewal_id).first()
    if not renewal:
        raise ValueError(f"Renewal record #{renewal_id} not found.")

    original = db.query(DepositInstrument).filter(DepositInstrument.id == renewal.original_instrument_id).first()
    replacement = (
        db.query(DepositInstrument).filter(DepositInstrument.id == renewal.replacement_instrument_id).first()
        if renewal.replacement_instrument_id
        else None
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    renewal.review_status = decision
    renewal.review_observations = remarks
    renewal.reviewed_by = decided_by
    renewal.completed_at = now

    if decision == "APPROVED":
        if original:
            original.lifecycle_status = "SUPERSEDED"
            original.updated_at = now
        if replacement:
            replacement.lifecycle_status = "ACTIVE"
            replacement.updated_at = now
    elif decision == "REJECTED":
        if original:
            # Revert to renewal required or matured
            val_stat, _ = calculate_validity_status(original.maturity_date)
            original.lifecycle_status = "MATURED" if val_stat == "MATURED" else "RENEWAL_REQUIRED"
            original.updated_at = now
        if replacement:
            replacement.lifecycle_status = "REJECTED"
            replacement.updated_at = now

    AuditEvent.create_chained(
        db=db,
        instrument_id=original.id if original else None,
        entity_type="RENEWAL",
        entity_id=renewal.id,
        event_type="RENEWAL_DECISION_FINALIZED",
        details={
            "decision": decision,
            "remarks": remarks,
            "decided_by": decided_by,
            "original_instrument_id": original.id if original else None,
            "replacement_instrument_id": replacement.id if replacement else None
        },
        actor=decided_by
    )

    db.flush()
    return renewal

