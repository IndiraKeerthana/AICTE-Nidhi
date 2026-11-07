import io
import fitz
import json
import pytest

OFFICER_HEADERS = {
    "X-User-Role": "OFFICER",
    "X-User-Id": "officer1"
}


def create_sample_pdf(content: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def test_findings_have_evidence_links_and_page_numbers(client):
    """
    Feature 2: Findings must connect to officer document viewer with document IDs,
    page references, extracted vs expected values.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-EVID-TEST-001",
        "institution_name": "Evidence Test Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    # Upload an expired fire NOC
    pdf = create_sample_pdf("Fire Certificate No: FS-EVID-01. Expired on 15/10/2024.")
    doc_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("fire_evid.pdf", io.BytesIO(pdf), "application/pdf")}
    )
    doc_id = doc_res.json()["id"]

    findings = client.get(f"/api/applications/{app_id}/findings").json()
    expired_fnd = next(f for f in findings if "EXPIRED" in f["finding_code"])

    # Verify evidence fields
    assert expired_fnd["supporting_document_id"] == doc_id
    assert expired_fnd["supporting_page_number"] is not None
    assert expired_fnd["expected_value"] is not None
    assert expired_fnd["observed_value"] is not None
    assert expired_fnd["rule_code"] is not None
    assert expired_fnd["rule_description"] is not None
    assert expired_fnd["recommended_action"] is not None


def test_cross_document_finding_includes_secondary_metadata(client):
    """
    Feature 1 & 2: Cross-document consistency finding includes secondary document
    reference and metadata for side-by-side officer inspection.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-EVID-TEST-002",
        "institution_name": "Alpha Engineering Academy",
        "category": "NEW_INSTITUTE",
        "declared_intake": 60,
        "declared_land_acres": 10.0
    })
    app_id = app_res.json()["id"]

    # Upload Land Title Deed stating 10.0 acres
    land_pdf = create_sample_pdf(
        "Registered Land Title Deed No: DEED-9988. Land Area: 10.0 acres. Alpha Engineering Academy, Pune, Maharashtra."
    )
    doc1_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "LAND_TITLE_DEED"},
        files={"file": ("land_deed.pdf", io.BytesIO(land_pdf), "application/pdf")}
    )
    doc1_id = doc1_res.json()["id"]

    # Upload Building Plan stating 4.0 acres (Discrepancy: 10.0 acres vs 4.0 acres!)
    plan_pdf = create_sample_pdf(
        "Approved Building Plan Approval No: BP-1122. Total Campus Land Area: 4.0 acres. Alpha Engineering Academy."
    )
    doc2_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "BUILDING_PLAN"},
        files={"file": ("building_plan.pdf", io.BytesIO(plan_pdf), "application/pdf")}
    )
    doc2_id = doc2_res.json()["id"]

    findings = client.get(f"/api/applications/{app_id}/findings").json()
    xdoc_fnd = next((f for f in findings if "XDOC-LAND" in f["finding_code"]), None)
    assert xdoc_fnd is not None
    assert xdoc_fnd["category"] == "RECORD_MISMATCH"
    assert xdoc_fnd["supporting_document_id"] == doc1_id
    assert xdoc_fnd["secondary_document_id"] == doc2_id
    assert "building_plan.pdf" in (xdoc_fnd["secondary_document_name"] or "") or "Building Plan" in (xdoc_fnd["secondary_document_name"] or "")


def test_document_stream_endpoint_for_in_app_viewer(client):
    """
    Officer document viewer streams genuine document file with inline disposition.
    """
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-EVID-TEST-003",
        "institution_name": "Stream Test Institute",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    pdf_bytes = create_sample_pdf("Sample statutory content for in-app inspection viewer.")
    doc_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("stream_sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    doc_id = doc_res.json()["id"]

    stream_res = client.get(f"/api/documents/{doc_id}/stream", headers=OFFICER_HEADERS)
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "application/pdf"
    assert "inline" in stream_res.headers["content-disposition"]
    assert len(stream_res.content) > 100
