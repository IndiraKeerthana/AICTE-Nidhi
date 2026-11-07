import io
import json
import os
import tempfile
import fitz
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import Institution, Application, Document, ExtractedField, Finding
from app.services.document_parser import extract_document_content

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


import uuid

@pytest.fixture(scope="module")
def test_data(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("doc_viewer_tests")
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        # Create Institution
        inst = Institution(
            aicte_permanent_id=f"1-TEST-VIEWER-{uid}",
            name="Apex Institute of Technology",
            state="Maharashtra",
            district="Pune",
            institution_type="ENGINEERING",
            address="Plot 42, Tech Park, Pune"
        )
        db.add(inst)
        db.flush()

        # Create Application
        appl = Application(
            application_number=f"APP-VIEWER-{uid}",
            institution_id=inst.id,
            academic_year="2025-2026",
            category="NEW_INSTITUTION",
            declared_intake=120,
            declared_land_acres=7.5,
            status="SUBMITTED"
        )
        db.add(appl)
        db.flush()

        # Create real PDF file with PyMuPDF
        pdf_path = tmp_path / "test_approval_letter.pdf"
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", fontsize=14)
        page.insert_text((72, 140), "Approved Intake: 120 seats in B.Tech Computer Engineering", fontsize=11)
        page.insert_text((72, 180), "Valid Till: 31/03/2026", fontsize=11)
        page.insert_text((72, 220), "Order No: AICTE/2025/APP-99881", fontsize=11)
        doc.save(str(pdf_path))
        doc.close()

        # Create real PNG image file
        png_path = tmp_path / "test_campus_plan.png"
        img_doc = fitz.open()
        img_page = img_doc.new_page(width=400, height=300)
        img_page.insert_text((50, 50), "Campus Layout Map", fontsize=12)
        pix = img_page.get_pixmap()
        pix.save(str(png_path))
        img_doc.close()

        # Insert PDF Document record
        pdf_doc = Document(
            application_id=appl.id,
            document_category="EOA_RECOMMENDED",
            original_filename="test_approval_letter.pdf",
            storage_path=str(pdf_path),
            file_size_bytes=os.path.getsize(str(pdf_path)),
            mime_type="application/pdf",
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            status="PROCESSED",
            page_count=1,
            extracted_text="Approved Intake: 120 seats\nValid Till: 31/03/2026\nOrder No: AICTE/2025/APP-99881"
        )
        db.add(pdf_doc)
        db.flush()

        # Insert ExtractedField records with bounding box
        ef1 = ExtractedField(
            document_id=pdf_doc.id,
            field_key="intake_capacity",
            field_value="120",
            normalized_value="120",
            confidence_score=0.95,
            page_number=1,
            source_snippet="Approved Intake: 120",
            bounding_box=json.dumps({"x": 72.0, "y": 140.0, "width": 120.0, "height": 14.0, "page_width": 595.0, "page_height": 842.0}),
            extraction_method="PYMUPDF"
        )
        ef2 = ExtractedField(
            document_id=pdf_doc.id,
            field_key="expiry_date",
            field_value="31/03/2026",
            normalized_value="31/03/2026",
            confidence_score=0.92,
            page_number=1,
            source_snippet="Valid Till: 31/03/2026",
            bounding_box=json.dumps({"x": 72.0, "y": 180.0, "width": 110.0, "height": 14.0, "page_width": 595.0, "page_height": 842.0}),
            extraction_method="PYMUPDF"
        )
        db.add_all([ef1, ef2])

        # Insert Image Document record
        image_doc = Document(
            application_id=appl.id,
            document_category="BUILDING_PLAN",
            original_filename="test_campus_plan.png",
            storage_path=str(png_path),
            file_size_bytes=os.path.getsize(str(png_path)),
            mime_type="image/png",
            sha256_hash="f4b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b866",
            status="PROCESSED",
            page_count=1,
            extracted_text="Campus Layout Map"
        )
        db.add(image_doc)

        # Insert Finding linked to document
        fnd = Finding(
            finding_code=f"FND-VIEWER-TEST-{appl.id}",
            application_id=appl.id,
            category="RECORD_MISMATCH",
            severity="HIGH",
            title="Intake Discrepancy Found in Attachment",
            description="Declared intake does not match approved intake on page 1 of letter.",
            expected_value="120",
            observed_value="180",
            supporting_document_id=pdf_doc.id,
            supporting_page_number=1,
            source_snippet="Approved Intake: 120 seats",
            bounding_box=json.dumps({"x": 72.0, "y": 140.0, "width": 120.0, "height": 14.0, "page_width": 595.0, "page_height": 842.0}),
            rule_code="RULE-INTAKE-01",
            rule_description="Declared intake must reconcile with statutory clearance.",
            recommended_action="Officer review required.",
            review_status="OPEN"
        )
        db.add(fnd)

        db.commit()

        pdf_id = pdf_doc.id
        image_id = image_doc.id
        app_id = appl.id
        fnd_id = fnd.id
        pdf_size = pdf_doc.file_size_bytes

        return {
            "institution_id": inst.id,
            "aicte_id": inst.aicte_permanent_id,
            "application_id": app_id,
            "pdf_doc_id": pdf_id,
            "image_doc_id": image_id,
            "pdf_path": pdf_path,
            "pdf_size": pdf_size,
            "finding_id": fnd_id
        }
    finally:
        db.close()


def test_document_stream_pdf_success(test_data):
    """Test that /api/documents/{id}/stream returns real PDF bytes with application/pdf Content-Type."""
    doc_id = test_data["pdf_doc_id"]
    headers = {"X-User-Role": "OFFICER", "X-User-Id": "officer1"}

    response = client.get(f"/api/documents/{doc_id}/stream", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert "test_approval_letter.pdf" in response.headers["content-disposition"]

    # Verify that received bytes are a valid PDF
    doc = fitz.open(stream=response.content, filetype="pdf")
    assert len(doc) == 1
    assert "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION" in doc[0].get_text()
    doc.close()


def test_document_stream_image_success(test_data):
    """Test that /api/documents/{id}/stream for image returns image/png Content-Type."""
    doc_id = test_data["image_doc_id"]
    headers = {"X-User-Role": "OFFICER", "X-User-Id": "officer1"}

    response = client.get(f"/api/documents/{doc_id}/stream", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "inline" in response.headers["content-disposition"]
    assert len(response.content) > 0


def test_document_stream_all_aliases(test_data):
    """Ensure all alias paths (/documents/{id}/raw, /applications/{app_id}/documents/{id}/stream, etc.) work identically."""
    app_id = test_data["application_id"]
    doc_id = test_data["pdf_doc_id"]
    headers = {"X-User-Role": "OFFICER", "X-User-Id": "officer1"}

    alias_paths = [
        f"/api/documents/{doc_id}/raw",
        f"/api/applications/{app_id}/documents/{doc_id}/stream",
        f"/api/applications/{app_id}/documents/{doc_id}/raw",
    ]

    for path in alias_paths:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"Failed on path: {path}"
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) == test_data["pdf_size"]


def test_document_details_metadata_and_extracted_fields(test_data):
    """Test GET /api/documents/{id} returns full metadata, stream_url, and extracted fields with bounding boxes."""
    doc_id = test_data["pdf_doc_id"]
    headers = {"X-User-Role": "OFFICER", "X-User-Id": "officer1"}

    response = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == doc_id
    assert data["original_filename"] == "test_approval_letter.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["stream_url"] == f"/api/documents/{doc_id}/stream"
    assert len(data["extracted_fields"]) >= 2

    # Check extracted fields structure
    intake_field = next(f for f in data["extracted_fields"] if f["field_key"] == "intake_capacity")
    assert intake_field["field_value"] == "120"
    assert intake_field["confidence_score"] == 0.95
    assert intake_field["page_number"] == 1
    assert intake_field["bounding_box"] is not None

    bbox = json.loads(intake_field["bounding_box"])
    assert bbox["x"] == 72.0
    assert bbox["y"] == 140.0
    assert bbox["page_width"] == 595.0


def test_document_stream_error_handling(test_data, tmp_path):
    """Verify structured 404 JSON is returned for invalid IDs or missing vault files."""
    headers = {"X-User-Role": "OFFICER", "X-User-Id": "officer1"}

    # 1. Non-existent document ID
    res1 = client.get("/api/documents/99999/stream", headers=headers)
    assert res1.status_code == 404
    assert res1.headers["content-type"] == "application/json"
    assert res1.json()["detail"] == "Document not found"

    # 2. Mismatched application ID
    doc_id = test_data["pdf_doc_id"]
    res2 = client.get(f"/api/applications/99999/documents/{doc_id}/stream", headers=headers)
    assert res2.status_code == 404
    assert res2.json()["detail"] == "Document not found"

    # 3. Document whose physical file is missing from vault
    db = SessionLocal()
    try:
        missing_doc = Document(
            application_id=test_data["application_id"],
            document_category="OTHER",
            original_filename="deleted_file.pdf",
            storage_path=str(tmp_path / "non_existent_file.pdf"),
            file_size_bytes=1024,
            mime_type="application/pdf",
            sha256_hash="0000000000000000000000000000000000000000000000000000000000000000",
            status="PROCESSED"
        )
        db.add(missing_doc)
        db.commit()
        db.refresh(missing_doc)
        missing_id = missing_doc.id
    finally:
        db.close()

    res3 = client.get(f"/api/documents/{missing_id}/stream", headers=headers)
    assert res3.status_code == 404
    assert res3.headers["content-type"] == "application/json"
    assert "Document file missing from vault" in res3.json()["detail"]


def test_bounding_box_generation_from_parser(tmp_path):
    """Verify document parser extracts genuine bounding box coordinates from real PDF pages."""
    pdf_path = tmp_path / "sample_intake.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((150, 250), "Sanctioned Intake: 240 seats", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    parsed = extract_document_content(str(pdf_path), "application/pdf")
    fields = parsed.get("extracted_fields", [])
    intake = next((f for f in fields if f["field_key"] == "intake_capacity"), None)

    assert intake is not None, "Intake field was not extracted by parser"
    assert intake["field_value"] == "240"
    assert intake["bounding_box"] is not None

    bbox = json.loads(intake["bounding_box"])
    assert "x" in bbox and "y" in bbox and "width" in bbox and "height" in bbox
    assert bbox["page_width"] == 600.0
    assert bbox["page_height"] == 800.0


def test_applicant_institution_boundary_enforcement(test_data):
    """Ensure applicant cannot access documents belonging to another institution."""
    doc_id = test_data["pdf_doc_id"]
    alien_applicant_headers = {
        "X-User-Role": "APPLICANT",
        "X-User-Id": "alien_user",
        "X-Institution-Id": "1-ANOTHER-INSTITUTION"
    }

    resp = client.get(f"/api/documents/{doc_id}/stream", headers=alien_applicant_headers)
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]
