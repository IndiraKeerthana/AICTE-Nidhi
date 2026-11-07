import io
import fitz
from app.config import settings

def create_sample_pdf(content: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_portal_integration_unauthorized(client):
    res = client.post("/api/integration/v1/applications", json={
        "institution_aicte_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "declared_intake": 120
    })
    assert res.status_code == 401
    assert "Invalid or missing X-Integration-Key" in res.json()["detail"]

def test_portal_integration_end_to_end_and_idempotency(client):
    headers = {
        "X-Integration-Key": settings.INTEGRATION_API_KEY,
        "X-Correlation-ID": "test-corr-12345",
        "X-Idempotency-Key": "idemp-unique-token-999"
    }
    payload = {
        "institution_aicte_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "application_category": "INCREASE_INTAKE",
        "academic_year": "2026-2027",
        "declared_programme": "ENGINEERING_AND_TECHNOLOGY",
        "declared_course": "Computer Science & Engineering",
        "declared_intake": 120,
        "declared_land_acres": 8.25
    }

    # 1. Submit through integration adapter
    res1 = client.post("/api/integration/v1/applications", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["status"] == "ACCEPTED"
    assert data1["tracking_id"].startswith("TRK-")
    tracking_id = data1["tracking_id"]
    assert "DEMO INTEGRATION" in data1["integration_mode"]

    # 2. Resubmit with identical Idempotency Key -> should return existing without re-creation
    res2 = client.post("/api/integration/v1/applications", json=payload, headers=headers)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["tracking_id"] == tracking_id
    assert data2.get("is_duplicate_event") is True

    # 3. Query status via integration API
    status_res = client.get(f"/api/integration/v1/applications/{tracking_id}/status", headers=headers)
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["tracking_id"] == tracking_id
    assert s_data["latest_scrutiny_run"]["run_number"] >= 1

    # 4. Query report via integration API
    report_res = client.get(f"/api/integration/v1/applications/{tracking_id}/report", headers=headers)
    assert report_res.status_code == 200
    r_data = report_res.json()
    assert len(r_data["checks_executed"]) >= 2
    assert any("INTAKE" in c["check_code"] for c in r_data["checks_executed"])

    # 5. Submit rectification via integration API (Upload Land Title Deed)
    pdf_bytes = create_sample_pdf("Land Title Deed: 8.25 Acres in Survey 104/2A. Approved Campus Space.")
    rect_res = client.post(
        f"/api/integration/v1/applications/{tracking_id}/rectifications",
        headers=headers,
        data={"document_category": "LAND_TITLE_DEED"},
        files={"file": ("Renewed_Land_Deed.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert rect_res.status_code == 200
    rect_data = rect_res.json()
    assert rect_data["status"] == "RECTIFICATION_PROCESSED"
    assert rect_data["new_scrutiny_run_number"] >= 2

def test_alerts_and_officer_decision(client):
    # 1. Create an application with mismatch intake
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    # 2. Check alerts generated
    alerts_res = client.get("/api/alerts")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) >= 1

    target_alert = alerts[0]
    # Acknowledge alert
    ack_res = client.post(f"/api/alerts/{target_alert['id']}/acknowledge")
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # 3. Check scrutiny runs API
    runs_res = client.get(f"/api/applications/{app_id}/runs")
    assert runs_res.status_code == 200
    runs = runs_res.json()
    assert len(runs) >= 1
    run_id = runs[0]["id"]

    run_detail = client.get(f"/api/runs/{run_id}").json()
    assert len(run_detail["checks"]) >= 2

    # 4a. Gating correctly blocks approval recommendation on deficient application
    blocked_res = client.post(f"/api/applications/{app_id}/decision", json={
        "decision": "RECOMMEND_APPROVAL",
        "justification_remarks": "Scrutiny committee reviewed all evidence and approved relaxation under State Gazette.",
        "officer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
    })
    assert blocked_res.status_code == 422
    assert "Approval blocked" in blocked_res.json()["detail"]

    # 4b. Officer records statutory rejection for unaddressed deficiencies
    dec_res = client.post(f"/api/applications/{app_id}/decision", json={
        "decision": "RECOMMEND_REJECTION",
        "justification_remarks": "Application rejected due to unaddressed intake discrepancies and missing documentation.",
        "officer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
    })
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "REJECTED"
    assert dec_res.json()["final_decision"] == "RECOMMEND_REJECTION"
