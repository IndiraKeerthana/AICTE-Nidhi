"""
Unit & Integration Tests for the Three Realistic Demonstration Scenarios:
1. Scenario 1 (APP-2026-SARASWATI-001): Complete Submission, Ready for Approval.
2. Scenario 2 (APP-2026-PRAGATI-002): Missing Mandatory Documents.
3. Scenario 3 (APP-2026-VANGUARD-003): Flagged for Review (Intake, Expired NOC, Location Mismatch).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import Application, Document, Finding, BaselineRecord
from app.services.demo_scenarios import seed_three_demo_scenarios
from app.api.decision import validate_approval_eligibility

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_scenarios():
    """Ensures DB tables and seeded scenarios exist before tests run."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        seed_three_demo_scenarios(db, force_refresh=True)
    finally:
        db.close()
    yield


@pytest.fixture
def auth_headers():
    return {"X-User-Role": "OFFICER", "X-User-Name": "officer1"}


def test_scenario1_saraswati_ready_for_approval(auth_headers):
    """
    Scenario 1: Saraswati College of Engineering & Technology
    - All 3 mandatory documents submitted and processed.
    - Status is READY_FOR_REVIEW.
    - Zero blocking findings.
    - Eligible for approval recommendation.
    - final_decision is None (leaves authority boundary to human officer).
    """
    db = SessionLocal()
    try:
        app1 = db.query(Application).filter(
            Application.application_number == "APP-2026-SARASWATI-001"
        ).first()
        assert app1 is not None, "Scenario 1 application record not found"
        assert app1.status == "READY_FOR_REVIEW"
        assert app1.final_decision is None, "Application must not be auto-decided"
        assert app1.declared_intake == 120

        # Check documents
        docs = db.query(Document).filter(Document.application_id == app1.id).all()
        assert len(docs) == 3, f"Expected 3 documents, got {len(docs)}"
        doc_categories = {d.document_category for d in docs}
        assert "FIRE_SAFETY_NOC" in doc_categories
        assert "AFFILIATION_LETTER" in doc_categories
        assert "FACULTY_ROSTER" in doc_categories

        # Check findings (should have 0 unresolved blocking findings)
        blocking_reasons = validate_approval_eligibility(app1, db)
        assert len(blocking_reasons) == 0, f"Expected 0 blocking reasons, got: {blocking_reasons}"

        # Test via API
        resp = client.get(f"/api/applications/{app1.id}/approval-eligibility", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_eligible"] is True
        assert data["blocking_reasons"] == []

        # Test document streaming for each document
        for doc in docs:
            stream_resp = client.get(f"/api/documents/{doc.id}/stream", headers=auth_headers)
            assert stream_resp.status_code == 200
            assert "application/pdf" in stream_resp.headers["content-type"]
            assert len(stream_resp.content) > 1000
    finally:
        db.close()


def test_scenario2_pragati_missing_documents(auth_headers):
    """
    Scenario 2: Pragati Institute of Technical Studies
    - Only FACULTY_ROSTER submitted; FIRE_SAFETY_NOC and AFFILIATION_LETTER missing.
    - Status is DEFICIENCY_FLAGGED.
    - Blocked from approval recommendation.
    - Explicit missing document finding and clear blocking explanation.
    """
    db = SessionLocal()
    try:
        app2 = db.query(Application).filter(
            Application.application_number == "APP-2026-PRAGATI-002"
        ).first()
        assert app2 is not None, "Scenario 2 application record not found"
        assert app2.status == "DEFICIENCY_FLAGGED"
        assert app2.final_decision is None

        # Check documents
        docs = db.query(Document).filter(Document.application_id == app2.id).all()
        assert len(docs) == 1, f"Expected only 1 document, got {len(docs)}"
        assert docs[0].document_category == "FACULTY_ROSTER"

        # Check blocking reasons
        blocking_reasons = validate_approval_eligibility(app2, db)
        assert len(blocking_reasons) >= 1
        combined_reasons = " ".join(blocking_reasons)
        assert "FIRE_SAFETY_NOC" in combined_reasons
        assert "AFFILIATION_LETTER" in combined_reasons

        # Test via API
        resp = client.get(f"/api/applications/{app2.id}/approval-eligibility", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_eligible"] is False
        assert len(data["blocking_reasons"]) >= 1

        # Check document streaming for the uploaded roster
        stream_resp = client.get(f"/api/documents/{docs[0].id}/stream", headers=auth_headers)
        assert stream_resp.status_code == 200
        assert "application/pdf" in stream_resp.headers["content-type"]
    finally:
        db.close()


def test_scenario3_vanguard_flagged_for_review(auth_headers):
    """
    Scenario 3: Vanguard Institute of Applied Technology
    - All 3 documents submitted, but scrutiny identifies:
      1. Sanctioned Intake Mismatch (180 declared vs 60 baseline).
      2. Expired Fire Safety NOC (expired in 2024).
      3. Location Mismatch (Hinjewadi in affiliation order vs Katraj-Kondhwa declared campus).
    - Status is DEFICIENCY_FLAGGED.
    - Blocked from approval recommendation.
    - Multiple specific evidence-backed blocking reasons.
    """
    db = SessionLocal()
    try:
        app3 = db.query(Application).filter(
            Application.application_number == "APP-2026-VANGUARD-003"
        ).first()
        assert app3 is not None, "Scenario 3 application record not found"
        assert app3.status == "DEFICIENCY_FLAGGED"
        assert app3.final_decision is None
        assert app3.declared_intake == 180

        # Check documents
        docs = db.query(Document).filter(Document.application_id == app3.id).all()
        assert len(docs) == 3

        # Check findings
        findings = db.query(Finding).filter(Finding.application_id == app3.id).all()
        finding_codes = {f.finding_code for f in findings}

        # Check specific findings exist
        has_intake_finding = any("FND-INTAKE" in code for code in finding_codes)
        has_expired_fire_finding = any("FND-EXPIRED-FIRE" in code or "AUTH-FIRE_SAFETY_NOC" in code for code in finding_codes)
        has_location_mismatch = any("AUTH-AFFILIATION_LETTER" in code for code in finding_codes)

        assert has_intake_finding, f"Expected intake finding, got: {finding_codes}"
        assert has_expired_fire_finding, f"Expected expired fire NOC finding, got: {finding_codes}"
        assert has_location_mismatch, f"Expected location mismatch finding, got: {finding_codes}"

        # Test approval eligibility is blocked
        resp = client.get(f"/api/applications/{app3.id}/approval-eligibility", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_eligible"] is False
        assert len(data["blocking_reasons"]) >= 3

        # Test document streaming for all 3 documents
        for doc in docs:
            stream_resp = client.get(f"/api/documents/{doc.id}/stream", headers=auth_headers)
            assert stream_resp.status_code == 200
            assert "application/pdf" in stream_resp.headers["content-type"]
    finally:
        db.close()


def test_seed_idempotency():
    """
    Verifies that calling seed_three_demo_scenarios with force_refresh=False
    returns existing records quickly without duplicate creation.
    """
    db = SessionLocal()
    try:
        res1 = seed_three_demo_scenarios(db, force_refresh=False)
        assert len(res1) == 3
        assert "APP-2026-SARASWATI-001" in res1
        assert "APP-2026-PRAGATI-002" in res1
        assert "APP-2026-VANGUARD-003" in res1
    finally:
        db.close()

