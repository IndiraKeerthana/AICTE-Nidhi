from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List, Any, Dict
import datetime
from decimal import Decimal


# --- Institution Schemas ---
class InstitutionBase(BaseModel):
    aicte_permanent_id: str = Field(..., json_schema_extra={"example": "1-9988776655"})
    institution_code: Optional[str] = Field(None, json_schema_extra={"example": "MH-PUN-042"})
    name: str = Field(..., json_schema_extra={"example": "Saraswati College of Engineering & Technology"})
    institution_type: Optional[str] = "TECHNICAL_INSTITUTE"
    address: Optional[str] = "Survey 104/2A, Kothrud"
    state: Optional[str] = "Maharashtra"
    district: Optional[str] = "Pune"
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    record_status: Optional[str] = "ACTIVE"


class InstitutionCreate(InstitutionBase):
    pass


class InstitutionResponse(InstitutionBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    instruments_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


# --- Document Schemas ---
class InstrumentDocumentResponse(BaseModel):
    id: int
    instrument_id: int
    document_category: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    phash_value: Optional[str] = None
    upload_timestamp: datetime.datetime
    uploaded_by: str
    extraction_status: str
    ocr_performed: bool
    version: int
    status: str
    extracted_text_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InstrumentDocumentDetailResponse(InstrumentDocumentResponse):
    extracted_text: Optional[str] = None
    extracted_fields_json: Optional[str] = None
    stream_url: Optional[str] = None


# --- Verification Record Schemas ---
class VerificationRecordBase(BaseModel):
    verification_method: str = Field(..., json_schema_extra={"example": "AUTOMATED_OCR_PARSE"})
    verification_source: str = Field(..., json_schema_extra={"example": "State Bank of India Corporate Registry [Simulated]"})
    result: str = Field(..., json_schema_extra={"example": "VERIFIED"})
    fields_checked: Optional[str] = None
    observed_values: Optional[str] = None
    evidence_notes: Optional[str] = None
    officer_observations: Optional[str] = None
    is_simulated: bool = True
    verified_by: Optional[str] = "SYSTEM"


class VerificationRecordCreate(VerificationRecordBase):
    document_id: Optional[int] = None


class VerificationRecordResponse(VerificationRecordBase):
    id: int
    instrument_id: int
    document_id: Optional[int] = None
    verification_timestamp: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Renewal Record Schemas ---
class RenewalRecordCreate(BaseModel):
    new_maturity_date: datetime.date
    review_observations: Optional[str] = None
    replacement_instrument_number: Optional[str] = None
    replacement_bank: Optional[str] = None
    replacement_amount: Optional[Decimal] = None


class RenewalRecordDecision(BaseModel):
    decision: str = Field(..., json_schema_extra={"example": "APPROVED"})  # APPROVED, REJECTED, CORRECTIONS_REQUESTED
    remarks: str


class RenewalRecordResponse(BaseModel):
    id: int
    original_instrument_id: int
    replacement_instrument_id: Optional[int] = None
    previous_maturity_date: Optional[datetime.date] = None
    new_maturity_date: Optional[datetime.date] = None
    submission_date: datetime.date
    review_status: str
    supporting_document_id: Optional[int] = None
    review_observations: Optional[str] = None
    reviewed_by: Optional[str] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Release / Refund Request Schemas ---
class ReleaseRefundRequestCreate(BaseModel):
    instrument_id: int
    request_type: str = Field("FULL_RELEASE", json_schema_extra={"example": "FULL_RELEASE"})  # FULL_RELEASE, DISCHARGE, PARTIAL_REFUND
    reason: str = Field(..., min_length=10)
    conditions_checklist: Optional[Dict[str, bool]] = None


class ReleaseRefundRequestDecision(BaseModel):
    decision: str = Field(..., json_schema_extra={"example": "APPROVED"})  # APPROVED, REJECTED, RETURNED_FOR_CORRECTION
    remarks: str = Field(..., min_length=10)
    conditions_checklist: Optional[Dict[str, bool]] = None


class ReleaseRefundRequestResponse(BaseModel):
    id: int
    request_number: str
    institution_id: int
    instrument_id: int
    request_type: str
    request_date: datetime.date
    reason: str
    conditions_checklist_json: Optional[str] = None
    review_status: str
    scrutiny_observations: Optional[str] = None
    decision_record: Optional[str] = None
    decision_date: Optional[datetime.datetime] = None
    decided_by: Optional[str] = None
    decision_remarks: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    institution_name: Optional[str] = None
    instrument_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Deposit Instrument Schemas ---
class DepositInstrumentBase(BaseModel):
    instrument_number: str = Field(..., json_schema_extra={"example": "FDR-SBIN-2024-8841"})
    institution_id: int
    instrument_type: str = Field("FDR", json_schema_extra={"example": "FDR"})
    issuing_bank: str = Field(..., json_schema_extra={"example": "State Bank of India"})
    branch_name: Optional[str] = "Kothrud Branch, Pune"
    branch_ifsc: Optional[str] = "SBIN0001234"
    account_number: Optional[str] = "3829104819"
    amount: Decimal = Field(..., json_schema_extra={"example": 1500000.00})
    currency: str = "INR"
    issue_date: Optional[datetime.date] = None
    maturity_date: Optional[datetime.date] = None
    lien_marked_to: Optional[str] = "Regional Officer, AICTE"
    joint_holder_name: Optional[str] = None
    purpose: Optional[str] = "Establishment of Technical Institution Corpus Deposit"
    notes: Optional[str] = None


class DepositInstrumentCreate(DepositInstrumentBase):
    pass


class DepositInstrumentUpdate(BaseModel):
    issuing_bank: Optional[str] = None
    branch_name: Optional[str] = None
    branch_ifsc: Optional[str] = None
    account_number: Optional[str] = None
    amount: Optional[Decimal] = None
    issue_date: Optional[datetime.date] = None
    maturity_date: Optional[datetime.date] = None
    lifecycle_status: Optional[str] = None
    lien_marked_to: Optional[str] = None
    joint_holder_name: Optional[str] = None
    notes: Optional[str] = None


class DepositInstrumentResponse(DepositInstrumentBase):
    id: int
    submission_date: datetime.date
    lifecycle_status: str
    validity_status: str
    verification_status: str
    original_instrument_id: Optional[int] = None
    renewal_count: int = 0
    remaining_days: Optional[int] = None
    formatted_amount: Optional[str] = None
    institution: Optional[InstitutionBase] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    documents_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class DepositInstrumentDetailResponse(DepositInstrumentResponse):
    documents: List[InstrumentDocumentResponse] = []
    verification_records: List[VerificationRecordResponse] = []
    renewals_as_original: List[RenewalRecordResponse] = []
    release_requests: List[ReleaseRefundRequestResponse] = []


# --- Notification Schemas ---
class NotificationResponse(BaseModel):
    id: int
    institution_id: Optional[int] = None
    instrument_id: Optional[int] = None
    request_id: Optional[int] = None
    notification_type: str
    trigger_date: datetime.date
    target_role: str
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Audit Event Schemas ---
class AuditEventResponse(BaseModel):
    id: int
    instrument_id: Optional[int] = None
    entity_type: str
    entity_id: Optional[int] = None
    event_type: str
    details_json: str
    actor: str
    previous_hash: str
    event_hash: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Dashboard Metrics Schemas ---
class DashboardMetricsResponse(BaseModel):
    total_instruments: int
    active_valid_instruments: int
    expiring_soon_instruments: int
    matured_instruments: int
    pending_verification: int
    renewals_pending: int
    release_requests_pending: int
    total_deposit_value: float
    formatted_total_value: str
    warning_window_days: int
    status_distribution: List[Dict[str, Any]]
    upcoming_maturities: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]
    bank_distribution: List[Dict[str, Any]] = []


# --- User Schemas ---
class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    designation: str
    institution_id: Optional[str] = None
    email: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
