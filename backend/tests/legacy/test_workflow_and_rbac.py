import io
import fitz
import pytest

def create_sample_pdf(content: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_applicant_access_restrictions(client):
    # 1. Create Application for Institution 1-9988776655
    res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    assert res.status_code == 201
    app_id = res.json()["id"]

    # 2. Upload document to application
    pdf_bytes = create_sample_pdf("Land Title Deed: 8.25 Acres. Valid and Approved.")
    upload_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "LAND_TITLE_DEED"},
        files={"file": ("Land_Deed.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 3. Applicant belonging to same institution can view
    auth_headers = {
        "X-User-Role": "APPLICANT",
        "X-User-Id": "inst_9988",
        "X-Institution-Id": "1-9988776655"
    }
    app_res = client.get(f"/api/applications/{app_id}", headers=auth_headers)
    assert app_res.status_code == 200
    assert app_res.json()["id"] == app_id

    # Can stream their own document
    stream_res = client.get(f"/api/documents/{doc_id}/stream", headers=auth_headers)
    assert stream_res.status_code == 200

    # 4. Applicant belonging to a DIFFERENT institution is blocked (403 Forbidden)
    diff_inst_headers = {
        "X-User-Role": "APPLICANT",
        "X-User-Id": "inst_diff",
        "X-Institution-Id": "1-1122334455"
    }
    forbidden_app = client.get(f"/api/applications/{app_id}", headers=diff_inst_headers)
    assert forbidden_app.status_code == 403
    assert "Access restricted" in forbidden_app.json()["detail"]

    forbidden_stream = client.get(f"/api/documents/{doc_id}/stream", headers=diff_inst_headers)
    assert forbidden_stream.status_code == 403

def test_final_decision_rbac_and_statutory_permissions(client):
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    # 1. Applicant role is strictly forbidden from recording regulatory decision
    applicant_headers = {
        "X-User-Role": "APPLICANT",
        "X-User-Id": "inst_9988",
        "X-Institution-Id": "1-9988776655"
    }
    forbidden_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Self-approval attempt by institution applicant."
        },
        headers=applicant_headers
    )
    assert forbidden_dec.status_code == 403
    assert "Access denied" in forbidden_dec.json()["detail"]

    # 1b. Gating blocks premature approval recommendation before required documents are uploaded
    approver_headers = {
        "X-User-Role": "APPROVER",
        "X-User-Id": "approver1"
    }
    gated_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Premature approval attempt without required documents.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=approver_headers
    )
    assert gated_dec.status_code == 422
    assert "Approval blocked" in gated_dec.json()["detail"]

    # Upload all mandatory documents for EOA_REGULAR
    for cat in ["FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "FACULTY_ROSTER"]:
        pdf = create_sample_pdf(f"Statutory document for {cat} AY 2026-2027.")
        doc_upload = client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": cat},
            files={"file": (f"{cat}.pdf", io.BytesIO(pdf), "application/pdf")}
        )
        assert doc_upload.status_code == 201

    # 2. Authorized Approver / Regional Officer records final statutory decision once eligible
    valid_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "All regular EoA requirements and compliance norms verified by Regional Committee.",
            "officer_name": "Prof. R. K. Verma (Regional Officer)"
        },
        headers=approver_headers
    )
    assert valid_dec.status_code == 200
    data = valid_dec.json()
    assert data["status"] == "APPROVED"
    assert data["final_decision"] == "RECOMMEND_APPROVAL"
    assert data["decided_by"] == "Prof. R. K. Verma (Regional Officer)"

def test_deficiency_notice_and_rescrutiny_flow(client):
    # 1. Create Application with mismatch
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    # Fetch findings
    detail = client.get(f"/api/applications/{app_id}").json()
    findings = detail["findings"]
    assert len(findings) >= 1
    target_finding_ids = [findings[0]["id"]]

    # 2. Officer issues official Deficiency Notice
    notice_res = client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json={
            "finding_ids": target_finding_ids,
            "instructions": "Please submit resolution letter and past approval sanction certificate for intake.",
            "officer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
        }
    )
    assert notice_res.status_code == 200
    assert notice_res.json()["status"] == "DEFICIENCY_FLAGGED"

    # Check alert was emitted
    refreshed_detail = client.get(f"/api/applications/{app_id}").json()
    assert refreshed_detail["status"] == "DEFICIENCY_FLAGGED"
    assert any(a["alert_type"] == "DEFICIENCY_NOTICE" for a in refreshed_detail["alerts"])

    # 3. Applicant uploads replacement document
    pdf_bytes = create_sample_pdf("Government Sanction Order: Sanctioned Intake capacity expansion 120 seats.")
    repl_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "BOARD_RESOLUTION"},
        files={"file": ("Sanction_Order.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert repl_res.status_code == 201

    # Check that new scrutiny run (#2) was triggered automatically
    updated_runs = client.get(f"/api/applications/{app_id}").json()["scrutiny_runs"]
    assert len(updated_runs) >= 2

    # 4. Officer returns application to review
    return_res = client.post(f"/api/applications/{app_id}/return-to-review")
    assert return_res.status_code == 200
    assert "returned to review" in return_res.json()["message"]

def test_document_checklist_and_grouped_scrutiny_report(client):
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    detail = client.get(f"/api/applications/{app_id}").json()
    
    # Check Section B: Document checklist contains mandatory and optional items
    checklist = detail.get("document_checklist", [])
    assert len(checklist) >= 6
    missing_items = [item for item in checklist if item["status"] == "MISSING"]
    assert len(missing_items) >= 1
    assert any(item["category_code"] == "FIRE_SAFETY_NOC" for item in checklist)

    # Check Section C: Grouped Scrutiny Report
    grouped = detail.get("grouped_scrutiny_report")
    assert grouped is not None
    assert "passed_checks" in grouped
    assert "issues_requiring_correction" in grouped
    assert "items_requiring_officer_review" in grouped
    assert "checks_could_not_be_completed" in grouped
    assert len(grouped["issues_requiring_correction"]) >= 1

def test_admin_and_rules_apis(client):
    # 1. Rules categories endpoint
    cat_res = client.get("/api/rules/categories")
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert len(cat_data["categories"]) >= 3
    assert any(c["code"] == "INCREASE_INTAKE" for c in cat_data["categories"])

    # 2. Admin integration status endpoint
    int_res = client.get("/api/admin/integrations/status")
    assert int_res.status_code == 200
    int_data = int_res.json()
    assert int_data["status"] == "OPERATIONAL"
    assert len(int_data["integrations"]) >= 4
    # Verify explicit DEMO / SIMULATED tagging
    assert any(i["mode"] == "DEMO_SIMULATOR" for i in int_data["integrations"])

    # 3. Admin audit log endpoint
    audit_res = client.get("/api/admin/audit")
    assert audit_res.status_code == 200
    assert isinstance(audit_res.json(), list)

    # 4. Regulatory rule update RBAC: Applicant cannot update rules
    applicant_headers = {"X-User-Role": "APPLICANT", "X-User-Id": "inst_1"}
    unauth_put = client.put("/api/admin/rules", json={"ruleset_version": "2025-2026.v2"}, headers=applicant_headers)
    assert unauth_put.status_code == 403

    # 5. Admin can update rules and it logs to audit history
    admin_headers = {"X-User-Role": "ADMIN", "X-User-Id": "admin1"}
    rules_cfg = client.get("/api/admin/rules").json()
    auth_put = client.put("/api/admin/rules", json=rules_cfg, headers=admin_headers)
    assert auth_put.status_code == 200
    assert auth_put.json()["status"] == "SUCCESS"

    # Verify audit event logged
    audit_after = client.get("/api/admin/audit", headers=admin_headers).json()
    assert any(e["event_type"] == "RULESET_UPDATED" for e in audit_after)
