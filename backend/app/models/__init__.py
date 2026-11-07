import datetime
import hashlib
import json
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey, Numeric, Index
)
from sqlalchemy.orm import relationship
from app.database import Base


def get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def get_current_date():
    return datetime.datetime.now(datetime.timezone.utc).date()


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    aicte_permanent_id = Column(String(50), unique=True, index=True, nullable=False)
    institution_code = Column(String(50), unique=True, index=True, nullable=True)
    name = Column(String(255), index=True, nullable=False)
    institution_type = Column(String(100), default="TECHNICAL_INSTITUTE")  # ENGINEERING, MANAGEMENT, PHARMACY, TECHNICAL_INSTITUTE
    address = Column(String(255), default="Sample Campus")
    state = Column(String(100), default="Maharashtra")
    district = Column(String(100), default="Pune")
    contact_email = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    record_status = Column(String(50), default="ACTIVE")  # ACTIVE, UNDER_REVIEW, SUSPENDED
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    instruments = relationship("DepositInstrument", back_populates="institution", cascade="all, delete-orphan")
    release_requests = relationship("ReleaseRefundRequest", back_populates="institution", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="institution", cascade="all, delete-orphan")


class DepositInstrument(Base):
    """
    Core financial instrument entity tracking Security Deposits and FDRs.
    Lifecycle states:
      DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> ACTIVE -> RENEWAL_REQUIRED -> RENEWAL_IN_PROGRESS -> MATURED -> RELEASE_REQUESTED -> RELEASED / REJECTED / SUPERSEDED / ARCHIVED
    Validity states:
      ACTIVE_VALID, EXPIRING_SOON, MATURED, UNKNOWN_INCOMPLETE
    Verification states:
      UNVERIFIED, PENDING, VERIFIED, MISMATCH_DETECTED, UNAVAILABLE, FAILED
    """
    __tablename__ = "deposit_instruments"

    id = Column(Integer, primary_key=True, index=True)
    instrument_number = Column(String(100), unique=True, index=True, nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_type = Column(String(50), default="FDR", index=True)  # FDR, JOINT_FDR, BANK_GUARANTEE, SECURITY_DEPOSIT
    issuing_bank = Column(String(150), nullable=False, index=True)
    branch_name = Column(String(150), nullable=True)
    branch_ifsc = Column(String(20), nullable=True)
    account_number = Column(String(50), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="INR")
    issue_date = Column(Date, nullable=True)
    maturity_date = Column(Date, nullable=True, index=True)
    submission_date = Column(Date, default=get_current_date)
    lifecycle_status = Column(String(50), default="SUBMITTED", index=True)
    validity_status = Column(String(50), default="ACTIVE_VALID", index=True)
    verification_status = Column(String(50), default="UNVERIFIED", index=True)
    original_instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="SET NULL"), nullable=True, index=True)
    renewal_count = Column(Integer, default=0)
    lien_marked_to = Column(String(150), default="Regional Officer, AICTE")
    joint_holder_name = Column(String(150), nullable=True)
    purpose = Column(String(150), default="Establishment of Technical Institution Corpus Deposit")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    institution = relationship("Institution", back_populates="instruments")
    documents = relationship("InstrumentDocument", back_populates="instrument", cascade="all, delete-orphan")
    verification_records = relationship("VerificationRecord", back_populates="instrument", cascade="all, delete-orphan")
    renewals_as_original = relationship("RenewalRecord", foreign_keys="[RenewalRecord.original_instrument_id]", back_populates="original_instrument", cascade="all, delete-orphan")
    renewals_as_replacement = relationship("RenewalRecord", foreign_keys="[RenewalRecord.replacement_instrument_id]", back_populates="replacement_instrument")
    release_requests = relationship("ReleaseRefundRequest", back_populates="instrument", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", foreign_keys="[AuditEvent.instrument_id]", back_populates="instrument", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="instrument", cascade="all, delete-orphan")


class InstrumentDocument(Base):
    __tablename__ = "instrument_documents"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    document_category = Column(String(100), nullable=False)  # FDR_RECEIPT, BANK_LIEN_LETTER, JOINT_NAME_AGREEMENT, BANK_CONFIRMATION, RELEASE_SANCTION, OTHER
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    sha256_hash = Column(String(64), index=True, nullable=False)
    phash_value = Column(String(32), index=True, nullable=True)
    upload_timestamp = Column(DateTime, default=get_utc_now)
    uploaded_by = Column(String(100), default="SYSTEM")
    extraction_status = Column(String(50), default="PENDING")  # PENDING, PROCESSED, EXTRACTION_FAILED
    extracted_fields_json = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    ocr_performed = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, REPLACED_ARCHIVED, UNAVAILABLE

    instrument = relationship("DepositInstrument", back_populates="documents")
    verification_records = relationship("VerificationRecord", back_populates="document")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("instrument_documents.id", ondelete="SET NULL"), nullable=True)
    verification_method = Column(String(50), nullable=False)  # AUTOMATED_OCR_PARSE, REGISTRY_CHECK, INDEPENDENT_CONFIRMATION, MANUAL_OFFICER_REVIEW, QR_DECODE
    verification_timestamp = Column(DateTime, default=get_utc_now)
    verification_source = Column(String(150), nullable=False)
    result = Column(String(50), nullable=False)  # VERIFIED, MISMATCH, PENDING, UNAVAILABLE, FAILED
    fields_checked = Column(Text, nullable=True)  # JSON list
    observed_values = Column(Text, nullable=True)  # JSON dict
    evidence_notes = Column(Text, nullable=True)
    officer_observations = Column(Text, nullable=True)
    is_simulated = Column(Boolean, default=True)
    verified_by = Column(String(100), default="SYSTEM")

    instrument = relationship("DepositInstrument", back_populates="verification_records")
    document = relationship("InstrumentDocument", back_populates="verification_records")


class RenewalRecord(Base):
    __tablename__ = "renewal_records"

    id = Column(Integer, primary_key=True, index=True)
    original_instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    replacement_instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="SET NULL"), nullable=True, index=True)
    previous_maturity_date = Column(Date, nullable=True)
    new_maturity_date = Column(Date, nullable=True)
    submission_date = Column(Date, default=get_current_date)
    review_status = Column(String(50), default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED, CORRECTIONS_REQUESTED
    supporting_document_id = Column(Integer, ForeignKey("instrument_documents.id", ondelete="SET NULL"), nullable=True)
    review_observations = Column(Text, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    original_instrument = relationship("DepositInstrument", foreign_keys=[original_instrument_id], back_populates="renewals_as_original")
    replacement_instrument = relationship("DepositInstrument", foreign_keys=[replacement_instrument_id], back_populates="renewals_as_replacement")


class ReleaseRefundRequest(Base):
    __tablename__ = "release_refund_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_number = Column(String(50), unique=True, index=True, nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(50), default="FULL_RELEASE")  # FULL_RELEASE, DISCHARGE, PARTIAL_REFUND
    request_date = Column(Date, default=get_current_date)
    reason = Column(Text, nullable=False)
    conditions_checklist_json = Column(Text, nullable=True)  # JSON checklist of compliance conditions
    review_status = Column(String(50), default="SUBMITTED", index=True)  # SUBMITTED, UNDER_REVIEW, RETURNED_FOR_CORRECTION, APPROVED, REJECTED, COMPLETED
    scrutiny_observations = Column(Text, nullable=True)
    decision_record = Column(String(50), nullable=True)  # APPROVED, REJECTED
    decision_date = Column(DateTime, nullable=True)
    decided_by = Column(String(100), nullable=True)
    decision_remarks = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    institution = relationship("Institution", back_populates="release_requests")
    instrument = relationship("DepositInstrument", back_populates="release_requests")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True)
    instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="CASCADE"), nullable=True, index=True)
    request_id = Column(Integer, ForeignKey("release_refund_requests.id", ondelete="CASCADE"), nullable=True)
    notification_type = Column(String(50), index=True, nullable=False)  # MATURITY_WARNING, MATURED_OVERDUE, VERIFICATION_PENDING, RENEWAL_PENDING, RELEASE_AWAITING_ACTION, DISCREPANCY_FLAGGED
    trigger_date = Column(Date, default=get_current_date)
    target_role = Column(String(50), default="OFFICER")  # OFFICER, APPROVER, ADMIN, APPLICANT
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(50), default="INFO")  # INFO, WARNING, CRITICAL
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_utc_now)

    institution = relationship("Institution", back_populates="notifications")
    instrument = relationship("DepositInstrument", back_populates="notifications")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("deposit_instruments.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type = Column(String(50), default="INSTRUMENT")  # INSTRUMENT, DOCUMENT, VERIFICATION, RENEWAL, RELEASE, NOTIFICATION
    entity_id = Column(Integer, nullable=True)
    event_type = Column(String(100), index=True, nullable=False)
    details_json = Column(Text, nullable=False)
    actor = Column(String(100), default="SYSTEM")
    previous_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=get_utc_now)

    instrument = relationship("DepositInstrument", foreign_keys=[instrument_id], back_populates="audit_events")

    @classmethod
    def create_chained(cls, db, instrument_id: int | None, event_type: str, details: dict, actor: str = "SYSTEM", entity_type: str = "INSTRUMENT", entity_id: int | None = None):
        last_event = db.query(cls).order_by(cls.id.desc()).first()
        prev_hash = last_event.event_hash if last_event else "0" * 64

        details_str = json.dumps(details, sort_keys=True, default=str)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        hasher = hashlib.sha256()
        hasher.update(prev_hash.encode("utf-8"))
        hasher.update(event_type.encode("utf-8"))
        hasher.update(details_str.encode("utf-8"))
        hasher.update(actor.encode("utf-8"))
        hasher.update(now_iso.encode("utf-8"))
        event_hash = hasher.hexdigest()

        event = cls(
            instrument_id=instrument_id,
            entity_type=entity_type,
            entity_id=entity_id or instrument_id,
            event_type=event_type,
            details_json=details_str,
            actor=actor,
            previous_hash=prev_hash,
            event_hash=event_hash,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(event)
        db.flush()
        return event


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(50), default="OFFICER")  # OFFICER, APPROVER, ADMIN, APPLICANT, REVIEWER
    designation = Column(String(100), default="Regulation Bureau Officer")
    institution_id = Column(String(50), nullable=True)  # AICTE Permanent ID for APPLICANT users
    email = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now)
