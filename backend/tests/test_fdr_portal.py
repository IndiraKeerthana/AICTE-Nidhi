"""
AICTE Deposit Manager — Comprehensive Test Suite
Validates financial instrument lifecycle, dynamic validity, verification engine,
renewal/replacement linking, release governance, CSV reporting, and synthetic demo scenarios.
"""

import os
import datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.config import settings
from app.main import app
from app.models import (
    Institution,
    DepositInstrument,
    InstrumentDocument,
    VerificationRecord,
    RenewalRecord,
    ReleaseRefundRequest,
    Notification,
    AuditEvent,
    User
)
from app.services.instrument_service import (
    calculate_validity_status,
    can_transition_lifecycle,
    format_inr
)
from app.services.fdr_verification_service import run_instrument_verification
from app.services.renewal_service import (
    initiate_renewal_process,
    register_replacement_instrument,
    finalize_renewal_decision
)
from app.services.release_service import (
    create_release_refund_request,
    finalize_release_decision
)
from app.services.report_service import generate_instruments_csv_export
from app.services.fdr_demo_data import seed_fdr_demo_scenarios
from app.services.baseline_service import ensure_default_users

# In-memory SQLite for isolated unit testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        ensure_default_users(session)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Indian Currency Formatting
# ---------------------------------------------------------------------------
def test_format_inr():
    assert format_inr(Decimal("1000")) == "₹1,000.00"
    assert format_inr(Decimal("100000")) == "₹1,00,000.00"
    assert format_inr(Decimal("2500000")) == "₹25,00,000.00"
    assert format_inr(Decimal("12000000")) == "₹1,20,00,000.00"
    assert format_inr(None) == "₹0.00"


# ---------------------------------------------------------------------------
# Test 2: Dynamic Runtime Validity Calculations
# ---------------------------------------------------------------------------
def test_calculate_validity_status():
    today = datetime.date.today()

    # Active & Valid (>30 days away)
    status_active, days_active = calculate_validity_status(
        maturity_date=today + datetime.timedelta(days=90),
        warning_days=30
    )
    assert status_active == "ACTIVE_VALID"
    assert days_active == 90

    # Expiring Soon (12 days away)
    status_exp, days_exp = calculate_validity_status(
        maturity_date=today + datetime.timedelta(days=12),
        warning_days=30
    )
    assert status_exp == "EXPIRING_SOON"
    assert days_exp == 12

    # Matured (20 days past)
    status_mat, days_mat = calculate_validity_status(
        maturity_date=today - datetime.timedelta(days=20),
        warning_days=30
    )
    assert status_mat == "MATURED"
    assert days_mat == -20

    # Incomplete / Missing dates
    status_inc, days_inc = calculate_validity_status(
        maturity_date=None
    )
    assert status_inc == "UNKNOWN_INCOMPLETE"
    assert days_inc is None


# ---------------------------------------------------------------------------
# Test 3: Lifecycle State Machine Transitions
# ---------------------------------------------------------------------------
def test_validate_lifecycle_transition():
    # Valid transitions
    assert can_transition_lifecycle("DRAFT", "SUBMITTED") is True
    assert can_transition_lifecycle("SUBMITTED", "PENDING_VERIFICATION") is True
    assert can_transition_lifecycle("PENDING_VERIFICATION", "ACTIVE") is True
    assert can_transition_lifecycle("ACTIVE", "RENEWAL_REQUIRED") is True
    assert can_transition_lifecycle("ACTIVE", "RELEASE_REQUESTED") is True

    # Invalid transitions
    assert can_transition_lifecycle("DRAFT", "RELEASED") is False
    assert can_transition_lifecycle("RELEASED", "ACTIVE") is False


# ---------------------------------------------------------------------------
# Test 4: Instrument Verification & Discrepancy Detection
# ---------------------------------------------------------------------------
def test_fdr_verification_discrepancy(db_session):
    today = datetime.date.today()

    inst = Institution(
        aicte_permanent_id="1-TEST-001",
        name="Test Engineering Academy",
        state="Karnataka",
        district="Bengaluru"
    )
    db_session.add(inst)
    db_session.flush()

    # Create instrument with recorded amount = 1.2 Crore
    deposit = DepositInstrument(
        instrument_number="FDR-TEST-DISCREPANCY-01",
        institution_id=inst.id,
        instrument_type="FDR",
        issuing_bank="State Bank of India",
        amount=12000000.0,
        currency="INR",
        issue_date=today - datetime.timedelta(days=60),
        maturity_date=today + datetime.timedelta(days=600),
        lifecycle_status="PENDING_VERIFICATION",
        validity_status="ACTIVE_VALID",
        verification_status="UNVERIFIED"
    )
    db_session.add(deposit)
    db_session.flush()

    # Attach document with extracted amount = 1.12 Crore (Amount mismatch)
    import json
    doc = InstrumentDocument(
        instrument_id=deposit.id,
        document_category="FDR_RECEIPT",
        original_filename="Test_FDR_Receipt.pdf",
        storage_path="vault/documents/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        upload_timestamp=datetime.datetime.now(datetime.timezone.utc),
        uploaded_by="officer1",
        extraction_status="SUCCESS",
        extracted_fields_json=json.dumps({
            "fdr_number": "FDR-TEST-DISCREPANCY-01",
            "bank_name": "State Bank of India",
            "amount": 11200000.0,
            "issue_date": str(today - datetime.timedelta(days=60)),
            "maturity_date": str(today + datetime.timedelta(days=600))
        }),
        extracted_text=f"State Bank of India Fixed Deposit Receipt FDR-TEST-DISCREPANCY-01 Principal Amount INR 11,200,000.00 Matures {today + datetime.timedelta(days=600)}",
        ocr_performed=True,
        version=1,
        status="ACTIVE"
    )
    db_session.add(doc)

    # Attach Bank Lien Letter
    doc_lien = InstrumentDocument(
        instrument_id=deposit.id,
        document_category="BANK_LIEN_LETTER",
        original_filename="Bank_Lien_Letter.pdf",
        storage_path="vault/documents/lien.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
        sha256_hash="f4c8996fb92427ae41e4649b934ca495991b7852b855e3b0c44298fc1c149afb",
        upload_timestamp=datetime.datetime.now(datetime.timezone.utc),
        uploaded_by="officer1",
        extraction_status="SUCCESS",
        extracted_fields_json=json.dumps({"lien": "AICTE"}),
        extracted_text="State Bank of India lien confirmation to Regional Officer, AICTE",
        ocr_performed=True,
        version=1,
        status="ACTIVE"
    )
    db_session.add(doc_lien)
    db_session.commit()

    # Run verification engine
    records = run_instrument_verification(db_session, deposit)

    assert deposit.verification_status in ("MISMATCH_DETECTED", "DISCREPANCY_FLAGGED")
    assert len(records) > 0

    # Verify discrepancy record recorded in DB
    discrepancy_records = [r for r in records if r.result in ("MISMATCH", "WARNING", "FAILED")]
    assert len(discrepancy_records) > 0
    assert any("amount mismatch" in (r.evidence_notes or "").lower() or "amount" in (r.evidence_notes or "").lower() for r in discrepancy_records)


# ---------------------------------------------------------------------------
# Test 5: Renewal & Replacement Linking
# ---------------------------------------------------------------------------
def test_renewal_replacement_workflow(db_session):
    today = datetime.date.today()

    inst = Institution(
        aicte_permanent_id="1-TEST-002",
        name="Vidya Technical Institute",
        state="Maharashtra",
        district="Pune"
    )
    db_session.add(inst)
    db_session.flush()

    # Original FDR maturing soon
    orig_fdr = DepositInstrument(
        instrument_number="FDR-ORIG-2021",
        institution_id=inst.id,
        instrument_type="FDR",
        issuing_bank="Punjab National Bank",
        amount=2500000.0,
        currency="INR",
        issue_date=today - datetime.timedelta(days=730),
        maturity_date=today + datetime.timedelta(days=10),
        lifecycle_status="ACTIVE",
        validity_status="EXPIRING_SOON",
        verification_status="VERIFIED"
    )
    db_session.add(orig_fdr)
    db_session.flush()

    # 1. Initiate Renewal
    new_mat = today + datetime.timedelta(days=1825)
    renewal = initiate_renewal_process(
        db=db_session,
        original_instrument_id=orig_fdr.id,
        new_maturity_date=new_mat,
        actor="officer1",
        observations="Tenure extension for 5 years"
    )
    assert renewal.review_status == "PENDING_REVIEW"
    assert orig_fdr.lifecycle_status == "RENEWAL_IN_PROGRESS"

    # 2. Register Replacement Instrument
    replacement_fdr = register_replacement_instrument(
        db=db_session,
        renewal_id=renewal.id,
        replacement_instrument_number="FDR-REPLACEMENT-2026",
        issuing_bank="Punjab National Bank",
        amount=Decimal("2500000.0"),
        new_maturity_date=new_mat,
        actor="officer1"
    )
    assert renewal.replacement_instrument_id == replacement_fdr.id

    # 3. Authorized Approver Decision
    decided_renewal = finalize_renewal_decision(
        db=db_session,
        renewal_id=renewal.id,
        decision="APPROVED",
        remarks="Verified lien letter from PNB. Approved.",
        decided_by="Prof. R. K. Verma"
    )
    assert decided_renewal.review_status == "APPROVED"
    assert orig_fdr.lifecycle_status == "SUPERSEDED"
    assert replacement_fdr.lifecycle_status == "ACTIVE"


# ---------------------------------------------------------------------------
# Test 6: Release & Refund Request Governance
# ---------------------------------------------------------------------------
def test_release_refund_governance(db_session):
    today = datetime.date.today()

    inst = Institution(
        aicte_permanent_id="1-TEST-003",
        name="Legacy Polytechnic Trust",
        state="Gujarat",
        district="Ahmedabad"
    )
    db_session.add(inst)
    db_session.flush()

    # 10-Year Matured FDR
    deposit = DepositInstrument(
        instrument_number="FDR-LEGACY-10YR",
        institution_id=inst.id,
        instrument_type="FDR",
        issuing_bank="Bank of Baroda",
        amount=1500000.0,
        currency="INR",
        issue_date=today - datetime.timedelta(days=3650),
        maturity_date=today - datetime.timedelta(days=10),
        lifecycle_status="MATURED",
        validity_status="MATURED",
        verification_status="VERIFIED"
    )
    db_session.add(deposit)
    db_session.flush()

    # 1. Submit Release Request
    valid_checklist = {
        "continuous_operation_years_satisfied": True,
        "no_pending_student_grievances": True,
        "audited_financial_accounts_clean": True,
        "competent_authority_in_principle_approval": True,
        "original_fdr_discharge_undertaking": True
    }

    rel_req = create_release_refund_request(
        db=db_session,
        instrument_id=deposit.id,
        request_type="FULL_RELEASE",
        reason="10-year term completed; no pending inquiries.",
        conditions_checklist=valid_checklist,
        actor="officer1"
    )
    assert rel_req.review_status == "SUBMITTED"
    assert deposit.lifecycle_status == "RELEASE_REQUESTED"

    # 2. Finalize Decision with Approved checklist
    final_decision = finalize_release_decision(
        db=db_session,
        request_id=rel_req.id,
        decision="APPROVED",
        remarks="Formal discharge granted under AICTE Regulation Manual.",
        conditions_checklist=valid_checklist,
        decided_by="Prof. R. K. Verma"
    )
    assert final_decision.review_status == "COMPLETED"
    assert deposit.lifecycle_status == "RELEASED"


# ---------------------------------------------------------------------------
# Test 7: RFC 4180 CSV Export Generation
# ---------------------------------------------------------------------------
def test_csv_export_generation(db_session):
    today = datetime.date.today()

    inst = Institution(
        aicte_permanent_id="1-TEST-CSV",
        name="Export Test Institute",
        state="Tamil Nadu",
        district="Chennai"
    )
    db_session.add(inst)
    db_session.flush()

    deposit = DepositInstrument(
        instrument_number="FDR-CSV-001",
        institution_id=inst.id,
        instrument_type="FDR",
        issuing_bank="HDFC Bank",
        amount=5000000.0,
        currency="INR",
        issue_date=today - datetime.timedelta(days=100),
        maturity_date=today + datetime.timedelta(days=500),
        lifecycle_status="ACTIVE",
        validity_status="ACTIVE_VALID",
        verification_status="VERIFIED"
    )
    db_session.add(deposit)
    db_session.commit()

    csv_output = generate_instruments_csv_export(db_session)
    assert "Instrument Number" in csv_output
    assert "FDR-CSV-001" in csv_output
    assert "HDFC Bank" in csv_output
    assert "Export Test Institute" in csv_output
    assert "ACTIVE_VALID" in csv_output


# ---------------------------------------------------------------------------
# Test 8: End-to-End Synthetic Scenarios Seeding
# ---------------------------------------------------------------------------
def test_seed_demo_scenarios_idempotent(db_session):
    # First seed run
    res1 = seed_fdr_demo_scenarios(db=db_session, force_refresh=True)
    assert res1["status"] == "SUCCESS"
    assert res1["seeded_instruments_count"] >= 12

    count1 = db_session.query(DepositInstrument).count()
    assert count1 >= 12

    # Second seed run without force_refresh (must be idempotent)
    res2 = seed_fdr_demo_scenarios(db=db_session, force_refresh=False)
    assert res2["status"] in ("SUCCESS", "ALREADY_SEEDED")

    count2 = db_session.query(DepositInstrument).count()
    assert count1 == count2, "Seed operation must be strictly idempotent"


# ---------------------------------------------------------------------------
# Test 9: FastAPI Endpoints Integration
# ---------------------------------------------------------------------------
def test_api_endpoints_health_and_metrics(client):
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    r_metrics = client.get("/api/dashboard/metrics")
    assert r_metrics.status_code == 200
    metrics = r_metrics.json()
    assert "total_instruments" in metrics
    assert "formatted_total_value" in metrics
    assert "upcoming_maturities" in metrics

    r_insts = client.get("/api/instruments")
    assert r_insts.status_code == 200
    assert isinstance(r_insts.json(), list)
    assert len(r_insts.json()) >= 12
