import io
import fitz
import pytest

OFFICER_HEADERS = {
    "X-User-Role": "OFFICER",
    "X-User-Id": "officer1"
}

APPROVER_HEADERS = {
    "X-User-Role": "APPROVER",
    "X-User-Id": "approver1"
}

APPLICANT_HEADERS = {
    "X-User-Role": "APPLICANT",
    "X-User-Id": "inst_9988",
    "X-Institution-Id": "1-9988776655"
}


def create_sample_pdf(content: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def test_issue_deficiency_notice_with_finding_ids(client):
    """
    Test issuing a deficiency notice by selecting specific findings.
    Verifies finding status transitions to RECTIFICATION_REQUESTED,
    alert created, audit event logged, and application marked DEFICIENCY_FLAGGED.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-DEF-TEST-001",
        "institution_name": "Deficiency Test Institute 1",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    assert app_res.status_code in (200, 201)
    app_id = app_res.json()["id"]

    # Retrieve open findings
    findings = client.get(f"/api/applications/{app_id}/findings").json()
    assert len(findings) > 0
    target_fnd = findings[0]

    # Issue notice with finding_id
    notice_res = client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json={
            "finding_ids": [target_fnd["id"]],
            "instructions": "Please submit approved sanction order for intake reconciliation.",
            "officer_name": "Officer"
        },
        headers=OFFICER_HEADERS
    )
    assert notice_res.status_code == 200
    assert notice_res.json()["status"] == "DEFICIENCY_FLAGGED"

    # Verify application detail reflects active deficiency notice
    detail = client.get(f"/api/applications/{app_id}").json()
    assert detail["status"] == "DEFICIENCY_FLAGGED"
    assert detail["active_deficiency_notice"] is not None
    assert detail["active_deficiency_notice"]["is_active"] is True
    assert "approved sanction order" in detail["active_deficiency_notice"]["instructions"]
    assert target_fnd["id"] in detail["active_deficiency_notice"]["finding_ids"]

    # Verify finding status is RECTIFICATION_REQUESTED
    updated_findings = client.get(f"/api/applications/{app_id}/findings").json()
    updated_fnd = next(f for f in updated_findings if f["id"] == target_fnd["id"])
    assert updated_fnd["review_status"] == "RECTIFICATION_REQUESTED"


def test_issue_deficiency_notice_with_document_categories(client):
    """
    Test issuing a deficiency notice selecting document categories directly.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-DEF-TEST-002",
        "institution_name": "Deficiency Test Institute 2",
        "category": "INCREASE_INTAKE",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    notice_res = client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json={
            "document_categories": ["FIRE_SAFETY_NOC"],
            "instructions": "Fire and Life Safety NOC is missing. Upload active certificate valid through AY 2026-2027.",
            "officer_name": "Officer"
        },
        headers=OFFICER_HEADERS
    )
    assert notice_res.status_code == 200
    res_data = notice_res.json()
    assert res_data["status"] == "DEFICIENCY_FLAGGED"
    assert "FIRE_SAFETY_NOC" in res_data["requested_categories"]

    detail = client.get(f"/api/applications/{app_id}").json()
    assert detail["active_deficiency_notice"] is not None
    assert "FIRE_SAFETY_NOC" in detail["active_deficiency_notice"]["requested_categories"]


def test_replacement_upload_archives_old_and_resolves_finding(client):
    """
    Full Lifecycle:
    1. Upload expired fire safety document -> Scrutiny flags expired NOC finding.
    2. Officer issues deficiency notice.
    3. Applicant uploads valid unexpired replacement document.
    4. Previous document is marked REPLACED_ARCHIVED.
    5. Re-scrutiny resolves the finding.
    6. System does NOT auto-approve (decision gating preserved).
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-DEF-TEST-003",
        "institution_name": "Deficiency Lifecycle Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    # 1. Upload expired FIRE_SAFETY_NOC (Valid till 31/12/2024)
    expired_pdf = create_sample_pdf(
        "Fire Safety Certificate No: FS-2024-9988. This certificate is valid till 31/12/2024."
    )
    upload1_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("fire_expired.pdf", io.BytesIO(expired_pdf), "application/pdf")}
    )
    assert upload1_res.status_code == 201
    doc1_id = upload1_res.json()["id"]

    # Verify expired finding exists
    findings1 = client.get(f"/api/applications/{app_id}/findings").json()
    expired_fnd = next((f for f in findings1 if "EXPIRED" in f["finding_code"]), None)
    assert expired_fnd is not None
    assert expired_fnd["review_status"] == "OPEN"

    # 2. Officer issues deficiency notice for the expired finding
    notice_res = client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json={
            "finding_ids": [expired_fnd["id"]],
            "document_categories": ["FIRE_SAFETY_NOC"],
            "instructions": "Fire NOC is expired. Upload valid renewed certificate.",
            "officer_name": "Officer"
        },
        headers=OFFICER_HEADERS
    )
    assert notice_res.status_code == 200

    # 3. Applicant uploads replacement valid certificate (valid till 31/05/2027)
    valid_pdf = create_sample_pdf(
        "Renewed Fire Safety Certificate No: FS-2027-1122. This certificate is valid till 31/05/2027."
    )
    upload2_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("fire_renewed.pdf", io.BytesIO(valid_pdf), "application/pdf")}
    )
    assert upload2_res.status_code == 201
    doc2_id = upload2_res.json()["id"]

    # 4. Check that old document doc1_id is archived
    detail = client.get(f"/api/applications/{app_id}").json()
    archived_doc = next(d for d in detail["documents"] if d["id"] == doc1_id)
    assert archived_doc["status"] == "REPLACED_ARCHIVED"

    active_doc = next(d for d in detail["documents"] if d["id"] == doc2_id)
    assert active_doc["status"] != "REPLACED_ARCHIVED"

    # 5. Check that the expired finding is RESOLVED
    findings2 = client.get(f"/api/applications/{app_id}/findings").json()
    resolved_fnd = next((f for f in findings2 if f["id"] == expired_fnd["id"]), None)
    if resolved_fnd:
        assert resolved_fnd["review_status"] == "RESOLVED"

    # 6. Check that application is NOT auto-approved
    assert detail["status"] != "APPROVED"
    assert detail["final_decision"] is None


def test_defective_replacement_upload_keeps_finding_active(client):
    """
    If replacement upload still contains deficiencies (e.g. still expired date),
    the finding must NOT be resolved, and application status remains DEFICIENCY_FLAGGED.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-DEF-TEST-004",
        "institution_name": "Defective Replacement Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    # Upload expired PDF
    expired_pdf1 = create_sample_pdf("Fire NOC Certificate No: FS-OLD-01. Expiry date: 31/03/2024.")
    client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("fire1.pdf", io.BytesIO(expired_pdf1), "application/pdf")}
    )

    findings1 = client.get(f"/api/applications/{app_id}/findings").json()
    expired_fnd = next(f for f in findings1 if "EXPIRED" in f["finding_code"])

    # Issue notice
    client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json={
            "finding_ids": [expired_fnd["id"]],
            "instructions": "Upload valid certificate.",
            "officer_name": "Officer"
        },
        headers=OFFICER_HEADERS
    )

    # Upload another expired PDF (e.g. 15/01/2025, which is also expired)
    expired_pdf2 = create_sample_pdf("Fire NOC Certificate No: FS-OLD-02. Expiry date: 15/01/2025.")
    client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("fire2.pdf", io.BytesIO(expired_pdf2), "application/pdf")}
    )

    # Verify finding is NOT resolved
    findings2 = client.get(f"/api/applications/{app_id}/findings").json()
    fnd_after = next(f for f in findings2 if "EXPIRED" in f["finding_code"])
    assert fnd_after["review_status"] in ("OPEN", "RECTIFICATION_REQUESTED")

    detail = client.get(f"/api/applications/{app_id}").json()
    assert detail["status"] == "DEFICIENCY_FLAGGED"
