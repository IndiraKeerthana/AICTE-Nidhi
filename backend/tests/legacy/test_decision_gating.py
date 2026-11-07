import io
import fitz
import pytest
from app.models import Application, ScrutinyRun, Finding, Document

def create_sample_pdf(content: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

OFFICER_HEADERS = {
    "X-User-Role": "OFFICER",
    "X-User-Id": "officer1"
}

APPROVER_HEADERS = {
    "X-User-Role": "APPROVER",
    "X-User-Id": "approver1"
}

def test_missing_mandatory_documents_blocks_approval(client):
    """
    Requirement 2 & 6: Approval must be blocked when mandatory documents are missing.
    Returns clear, actionable validation error (HTTP 422) detailing missing documents.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-001",
        "institution_name": "Gating Test Technical Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    assert app_res.status_code in (200, 201)
    app_id = app_res.json()["id"]

    # Check eligibility endpoint returns not eligible with specific missing documents
    elig_res = client.get(f"/api/applications/{app_id}/approval-eligibility", headers=OFFICER_HEADERS)
    assert elig_res.status_code == 200
    elig_data = elig_res.json()
    assert elig_data["is_eligible"] is False
    assert any("Mandatory document(s) missing" in reason for reason in elig_data["blocking_reasons"])
    assert any("FIRE_SAFETY_NOC" in reason for reason in elig_data["blocking_reasons"])

    # Attempt to record RECOMMEND_APPROVAL directly
    decision_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Premature recommendation without required statutory attachments.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=APPROVER_HEADERS
    )
    assert decision_res.status_code == 422
    err_detail = decision_res.json()["detail"]
    assert "Approval blocked" in err_detail
    assert "Mandatory document(s) missing" in err_detail

    # Verify database state was NOT changed to APPROVED
    app_detail = client.get(f"/api/applications/{app_id}").json()
    assert app_detail["status"] != "APPROVED"
    assert app_detail["final_decision"] is None


def test_unresolved_blocking_finding_blocks_approval(client):
    """
    Requirement 2 & 3: Unresolved critical/high blocking findings (intake mismatch) block approval.
    Resolving the finding with officer justification clears the block and permits approval.
    """
    # 1. Create application with declared intake of 120 vs baseline of 60
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-002",
        "institution_name": "Gating Mismatch Technical Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 120  # Mismatch triggers FND-INTAKE (HIGH, VERIFIED_FACT)
    })
    app_id = app_res.json()["id"]

    # Upload all mandatory documents for EOA_REGULAR
    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )

    # 2. Attempt RECOMMEND_APPROVAL while intake mismatch finding is still OPEN
    blocked_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Approving despite open intake discrepancy.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=APPROVER_HEADERS
    )
    assert blocked_res.status_code == 422
    assert "Approval blocked" in blocked_res.json()["detail"]
    assert "FND-INTAKE" in blocked_res.json()["detail"]

    # 3. Locate the blocking intake finding
    findings = client.get(f"/api/applications/{app_id}/findings").json()
    intake_finding = next(f for f in findings if "INTAKE" in f["finding_code"])
    assert intake_finding["review_status"] == "OPEN"

    # 4. Officer resolves the finding with statutory justification remarks
    resolve_res = client.post(
        f"/api/findings/{intake_finding['id']}/action",
        json={
            "action_type": "RESOLVE",
            "justification_remarks": "Verified State Government Gazette sanction order authorizing 120 intake seats.",
            "reviewer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
        }
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["review_status"] == "RESOLVED"

    # 5. Now attempt RECOMMEND_APPROVAL again: must succeed!
    approval_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "All documents verified and intake authorization resolved per Gazette notification.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=APPROVER_HEADERS
    )
    assert approval_res.status_code == 200
    assert approval_res.json()["status"] == "APPROVED"
    assert approval_res.json()["final_decision"] == "RECOMMEND_APPROVAL"


def test_officer_override_clears_blocking_status(client):
    """
    Requirement 3 & 7: Preserve authorised officer decision-making.
    An officer can OVERRIDE a finding with formal justification remarks,
    which unblocks approval without treating the finding as fatal fraud.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-003",
        "institution_name": "Override Test Technical Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )

    findings = client.get(f"/api/applications/{app_id}/findings").json()
    intake_finding = next(f for f in findings if "INTAKE" in f["finding_code"])

    # Officer records statutory OVERRIDE
    override_res = client.post(
        f"/api/findings/{intake_finding['id']}/action",
        json={
            "action_type": "OVERRIDE",
            "justification_remarks": "High Court interim order permits admission up to 120 seats pending disposal of writ.",
            "reviewer_name": "Prof. R. K. Verma (Regional Officer)"
        }
    )
    assert override_res.status_code == 200
    assert override_res.json()["review_status"] == "OVERRIDDEN"

    # Approval recommendation is now permitted
    dec_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Approved subject to final High Court judgment per judicial override remarks.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=APPROVER_HEADERS
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "APPROVED"


def test_incomplete_scrutiny_blocks_approval(client, db):
    """
    Requirement 1 & 2: Incomplete or running scrutiny blocks approval recommendation.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-004",
        "institution_name": "Scrutiny Status Technical Campus",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )

    # Simulate scrutiny run being in RUNNING state
    app = db.query(Application).filter(Application.id == app_id).first()
    latest_run = max(app.scrutiny_runs, key=lambda r: r.run_number)
    latest_run.status = "RUNNING"
    db.commit()

    blocked_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Attempting approval while scrutiny pipeline is running.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=APPROVER_HEADERS
    )
    assert blocked_res.status_code == 422
    assert "still in progress" in blocked_res.json()["detail"]


def test_eligible_application_approved_successfully(client):
    """
    Requirement 1 & 7: Fully eligible application with all mandatory documents and completed scrutiny
    is approved successfully with audit event and alert resolution.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-005",
        "institution_name": "Fully Eligible Technical Campus",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )

    # Verify eligibility API confirms clean status
    elig = client.get(f"/api/applications/{app_id}/approval-eligibility", headers=OFFICER_HEADERS).json()
    assert elig["is_eligible"] is True
    assert len(elig["blocking_reasons"]) == 0

    # Record approval
    dec_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "All EoA compliance checks verified and authenticated by Competent Authority.",
            "officer_name": "Prof. R. K. Verma (Competent Authority)"
        },
        headers=APPROVER_HEADERS
    )
    assert dec_res.status_code == 200
    data = dec_res.json()
    assert data["status"] == "APPROVED"
    assert data["final_decision"] == "RECOMMEND_APPROVAL"
    assert data["decided_by"] == "Prof. R. K. Verma (Competent Authority)"
    assert data["decided_at"] is not None

    # Check hash-chained audit event was created
    app_detail = client.get(f"/api/applications/{app_id}").json()
    assert any(e["event_type"] == "OFFICER_FINAL_DECISION_RECORDED" for e in app_detail["audit_events"])


def test_terminal_state_immutability_and_repeated_decisions_blocked(client):
    """
    Requirement 4 & 5: Once an application has been decided (APPROVED or REJECTED),
    subsequent decisions are blocked with HTTP 409 Conflict until reopened.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-006",
        "institution_name": "Terminal State Technical Campus",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )

    # Initial decision: Approved
    first_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "All statutory checks verified and recommended for approval.",
            "officer_name": "Prof. R. K. Verma (Competent Authority)"
        },
        headers=APPROVER_HEADERS
    )
    assert first_dec.status_code == 200

    # Repeated decision attempts on approved application must be blocked with 409 Conflict
    repeat_approval = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Duplicate approval attempt.",
            "officer_name": "Another Officer"
        },
        headers=APPROVER_HEADERS
    )
    assert repeat_approval.status_code == 409
    assert "already been finalized" in repeat_approval.json()["detail"]

    # Attempting to change to rejection without reopening must also be blocked
    repeat_rejection = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_REJECTION",
            "justification_remarks": "Attempting to overwrite approval with rejection.",
            "officer_name": "Another Officer"
        },
        headers=APPROVER_HEADERS
    )
    assert repeat_rejection.status_code == 409
    assert "already been finalized" in repeat_rejection.json()["detail"]

    # Attempting to issue deficiency notice on finalized application must also be blocked (Requirement 5)
    deficiency_attempt = client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json={
            "finding_ids": [1],
            "instructions": "Attempting to issue deficiency on finalized application."
        },
        headers=OFFICER_HEADERS
    )
    assert deficiency_attempt.status_code == 409
    assert "already been finalized" in deficiency_attempt.json()["detail"]


def test_reopening_workflow_via_return_to_review(client):
    """
    Requirement 4: Authorized reopening workflow via return-to-review clears final decision
    and allows re-scrutiny and subsequent new decision.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-007",
        "institution_name": "Reopen Test Technical Campus",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )

    # 1. Initially approve
    init_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Initial statutory approval by Regional Committee.",
            "officer_name": "Prof. R. K. Verma (Competent Authority)"
        },
        headers=APPROVER_HEADERS
    )
    assert init_dec.status_code == 200

    # 2. Officer formally reopens the application via return-to-review
    reopen_res = client.post(f"/api/applications/{app_id}/return-to-review", headers=OFFICER_HEADERS)
    assert reopen_res.status_code == 200
    assert "returned to review" in reopen_res.json()["message"]

    # Verify decision state is reset
    reopened_app = client.get(f"/api/applications/{app_id}").json()
    assert reopened_app["final_decision"] is None
    assert reopened_app["decided_by"] is None

    # 3. New decision can now be recorded
    new_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Re-evaluated and approved after formal review reopening.",
            "officer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
        },
        headers=APPROVER_HEADERS
    )
    assert new_dec.status_code == 200
    assert new_dec.json()["status"] == "APPROVED"


def test_rejection_allowed_even_with_deficiencies(client):
    """
    Requirement 3: Rejection is NOT blocked by missing documents or open findings.
    Rejection is the legally appropriate regulatory consequence for defective applications.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-008",
        "institution_name": "Deficient Technical Campus",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120  # Has missing documents and intake mismatch
    })
    app_id = app_res.json()["id"]

    # Officer records statutory rejection
    rejection_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_REJECTION",
            "justification_remarks": "Mandatory documents omitted and unaddressed intake expansion contradiction.",
            "officer_name": "Prof. R. K. Verma (Competent Authority)"
        },
        headers=APPROVER_HEADERS
    )
    assert rejection_res.status_code == 200
    data = rejection_res.json()
    assert data["status"] == "REJECTED"
    assert data["final_decision"] == "RECOMMEND_REJECTION"


def test_invalid_decision_payload_rejected(client):
    """
    Validates that invalid decision options are rejected with HTTP 400 Bad Request.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-GATE-TEST-009",
        "institution_name": "Invalid Payload Campus",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    invalid_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "AUTO_APPROVE_BYPASS",
            "justification_remarks": "Invalid non-statutory decision attempt.",
            "officer_name": "Officer"
        },
        headers=APPROVER_HEADERS
    )
    assert invalid_res.status_code == 400
    assert "Invalid decision" in invalid_res.json()["detail"]
