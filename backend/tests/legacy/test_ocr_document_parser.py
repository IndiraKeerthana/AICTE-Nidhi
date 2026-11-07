import io
import fitz
import pytest
from PIL import Image, ImageDraw
from app.services.document_parser import (
    extract_document_content,
    configure_tesseract,
    is_tesseract_available
)
from app.models import Application, Document

def create_synthetic_text_pdf(text: str) -> bytes:
    """Creates a native PDF containing standard readable vector text."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def create_synthetic_scanned_pdf(text_in_image: str = "Scanned Regulatory Attachment") -> bytes:
    """
    Creates a synthetic scanned PDF by rendering text into a raster bitmap image,
    then placing that image on a blank PDF page without any text layer.
    """
    img = Image.new("RGB", (800, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 80), text_in_image, fill=(0, 0, 0))

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=800, height=300)
    page.insert_image(page.rect, stream=img_bytes)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def create_synthetic_blank_scanned_pdf(num_pages: int = 1) -> bytes:
    """Creates a synthetic scanned PDF with blank white image pages (no text)."""
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    doc = fitz.open()
    for _ in range(num_pages):
        page = doc.new_page(width=600, height=400)
        page.insert_image(page.rect, stream=img_bytes)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def test_text_based_pdf_uses_pymupdf(tmp_path):
    """
    Requirement 1: Continue using PyMuPDF text extraction for PDFs that already contain readable text.
    OCR must not be triggered when readable text is present.
    """
    text = (
        "AICTE Statutory Approval Order\n"
        "Sanctioned Intake Capacity: 120 seats\n"
        "Registered Land Area: 8.25 acres in Survey 104/2A\n"
        "Valid up to: 31/03/2027\n"
        "Certificate no: AICTE-2026-REG-8821\n"
    )
    pdf_bytes = create_synthetic_text_pdf(text)
    pdf_path = tmp_path / "readable_sample.pdf"
    pdf_path.write_bytes(pdf_bytes)

    res = extract_document_content(str(pdf_path), "application/pdf")

    assert res["extraction_method"] == "PYMUPDF"
    assert res["ocr_needed"] is False
    assert res["ocr_performed"] is False
    assert res["status"] == "PROCESSED"
    assert res["is_complete"] is True
    assert res["page_count"] == 1
    assert "Sanctioned Intake Capacity: 120 seats" in res["extracted_text"]

    # Verify structured fields were extracted with method PYMUPDF
    field_keys = {f["field_key"]: f["field_value"] for f in res["extracted_fields"]}
    assert "intake_capacity" in field_keys
    assert field_keys["intake_capacity"] == "120"
    assert "land_area" in field_keys
    assert "8.25" in field_keys["land_area"]
    assert "expiry_date" in field_keys
    assert field_keys["expiry_date"] == "31/03/2027"
    assert all(f["extraction_method"] == "PYMUPDF" for f in res["extracted_fields"])


def test_scanned_pdf_with_readable_content_runs_tesseract(tmp_path, monkeypatch):
    """
    Requirement 2 & 4: When a PDF contains insufficient extractable text, render its pages
    to images using PyMuPDF and run actual Tesseract OCR through supported dependencies.
    """
    pdf_bytes = create_synthetic_scanned_pdf("Sanctioned intake: 120 seats. Valid till 31/03/2027.")
    pdf_path = tmp_path / "scanned_readable.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # Mock Tesseract as operational and simulate OCR text extraction
    monkeypatch.setattr(
        "app.services.document_parser.configure_tesseract",
        lambda: (True, "Tesseract v5.4.0")
    )
    rendered_images = []

    def mock_image_to_string(image, **kwargs):
        rendered_images.append(image)
        assert isinstance(image, Image.Image)
        return "Government Directorate of Technical Education\nApproved Intake: 120 seats\nValid till 31/03/2027\nCertificate no: DTE-2026-NOC-771"

    monkeypatch.setattr("pytesseract.image_to_string", mock_image_to_string)

    res = extract_document_content(str(pdf_path), "application/pdf")

    # Verify PyMuPDF rendered the page and OCR was invoked
    assert len(rendered_images) == 1
    assert res["ocr_needed"] is True
    assert res["ocr_performed"] is True
    assert res["ocr_engine_available"] is True
    assert res["extraction_method"] == "OCR_TESSERACT"
    assert res["status"] == "PROCESSED"
    assert res["is_complete"] is True
    assert "Approved Intake: 120 seats" in res["extracted_text"]

    # Verify extracted fields are accurately populated and reference page 1 with method OCR_TESSERACT
    intake_f = next((f for f in res["extracted_fields"] if f["field_key"] == "intake_capacity"), None)
    assert intake_f is not None
    assert intake_f["field_value"] == "120"
    assert intake_f["page_number"] == 1
    assert intake_f["extraction_method"] == "OCR_TESSERACT"

    expiry_f = next((f for f in res["extracted_fields"] if f["field_key"] == "expiry_date"), None)
    assert expiry_f is not None
    assert expiry_f["field_value"] == "31/03/2027"
    assert expiry_f["page_number"] == 1


def test_unreadable_or_empty_scanned_pdf_reports_incomplete(tmp_path, monkeypatch):
    """
    Requirement 5: If OCR returns no useful text (blank/unreadable scan), return an explicit
    incomplete-extraction result. Do not silently treat the document as successfully processed.
    """
    pdf_bytes = create_synthetic_blank_scanned_pdf(num_pages=1)
    pdf_path = tmp_path / "blank_scan.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # Mock Tesseract as operational, but OCR returns empty text (blank page)
    monkeypatch.setattr(
        "app.services.document_parser.configure_tesseract",
        lambda: (True, "Tesseract v5.4.0")
    )
    ocr_calls = []

    def mock_empty_ocr(image, **kwargs):
        ocr_calls.append(image)
        return "   \n\n   "

    monkeypatch.setattr("pytesseract.image_to_string", mock_empty_ocr)

    res = extract_document_content(str(pdf_path), "application/pdf")

    assert len(ocr_calls) == 1
    assert res["ocr_needed"] is True
    assert res["ocr_performed"] is True  # OCR was attempted
    assert res["status"] == "EXTRACTION_FAILED"  # Incomplete extraction
    assert res["is_complete"] is False
    assert res["extraction_method"] == "OCR_UNREADABLE"
    assert "Incomplete extraction" in res["extracted_text"]
    assert res["incomplete_reason"] is not None
    assert "no legible or useful text" in res["incomplete_reason"]
    assert len(res["extracted_fields"]) == 0


def test_unavailable_ocr_dependency_reports_incomplete(tmp_path, monkeypatch):
    """
    Requirement 4 & 5: If Tesseract is missing, return an explicit incomplete-extraction result.
    Never set ocr_performed = True without invoking OCR.
    """
    pdf_bytes = create_synthetic_scanned_pdf("Any scanned text")
    pdf_path = tmp_path / "scanned_no_tesseract.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # Mock Tesseract as missing / unavailable
    monkeypatch.setattr(
        "app.services.document_parser.configure_tesseract",
        lambda: (False, "Tesseract engine binary not found in system PATH.")
    )

    ocr_invoked = []
    def fail_if_called(image, **kwargs):
        ocr_invoked.append(True)
        raise AssertionError("OCR should not be invoked when dependency is missing!")

    monkeypatch.setattr("pytesseract.image_to_string", fail_if_called)

    res = extract_document_content(str(pdf_path), "application/pdf")

    assert len(ocr_invoked) == 0
    assert res["ocr_needed"] is True
    assert res["ocr_performed"] is False  # Never True without invoking OCR!
    assert res["ocr_engine_available"] is False
    assert res["status"] == "EXTRACTION_FAILED"
    assert res["is_complete"] is False
    assert res["extraction_method"] == "SCANNED_PDF_NO_OCR"
    assert "Incomplete extraction" in res["extracted_text"]
    assert "OCR engine is unavailable" in res["incomplete_reason"]
    assert len(res["extracted_fields"]) == 0


def test_first_three_pages_limit_and_page_references(tmp_path, monkeypatch):
    """
    Requirement 3 & 6: Start with the first three pages, respecting processing limits.
    Preserve accurate page references for extracted fields.
    """
    # Create a 5-page scanned PDF
    pdf_bytes = create_synthetic_blank_scanned_pdf(num_pages=5)
    pdf_path = tmp_path / "five_pages.pdf"
    pdf_path.write_bytes(pdf_bytes)

    monkeypatch.setattr(
        "app.services.document_parser.configure_tesseract",
        lambda: (True, "Tesseract v5.4.0")
    )

    pages_processed = []
    def mock_multipage_ocr(image, **kwargs):
        page_num = len(pages_processed) + 1
        pages_processed.append(page_num)
        if page_num == 1:
            return "Page 1 Content: Approved Intake: 60 seats."
        elif page_num == 2:
            return "Page 2 Content: Land Area: 7.5 acres."
        elif page_num == 3:
            return "Page 3 Content: Valid up to: 15/08/2027."
        return "Page 4+ Should not be called!"

    monkeypatch.setattr("pytesseract.image_to_string", mock_multipage_ocr)

    res = extract_document_content(str(pdf_path), "application/pdf", max_ocr_pages=3)

    # Verified only first 3 pages were processed
    assert pages_processed == [1, 2, 3]
    assert res["ocr_performed"] is True
    assert res["page_count"] == 5
    assert res["status"] == "PROCESSED"

    # Verify page references on extracted fields
    intake = next(f for f in res["extracted_fields"] if f["field_key"] == "intake_capacity")
    assert intake["page_number"] == 1
    assert intake["field_value"] == "60"

    land = next(f for f in res["extracted_fields"] if f["field_key"] == "land_area")
    assert land["page_number"] == 2
    assert "7.5" in land["field_value"]

    expiry = next(f for f in res["extracted_fields"] if f["field_key"] == "expiry_date")
    assert expiry["page_number"] == 3
    assert expiry["field_value"] == "15/08/2027"


def test_ocr_runtime_exception_reports_explicit_failure(tmp_path, monkeypatch):
    """
    Requirement 5: If OCR execution errors out or times out, report explicit failure.
    """
    pdf_bytes = create_synthetic_scanned_pdf("Scanned content")
    pdf_path = tmp_path / "ocr_error.pdf"
    pdf_path.write_bytes(pdf_bytes)

    monkeypatch.setattr(
        "app.services.document_parser.configure_tesseract",
        lambda: (True, "Tesseract v5.4.0")
    )

    def mock_failing_ocr(image, **kwargs):
        raise RuntimeError("Tesseract subprocess timed out after 15 seconds")

    monkeypatch.setattr("pytesseract.image_to_string", mock_failing_ocr)

    res = extract_document_content(str(pdf_path), "application/pdf")

    assert res["ocr_needed"] is True
    assert res["ocr_performed"] is True
    assert res["status"] == "EXTRACTION_FAILED"
    assert res["is_complete"] is False
    assert res["extraction_method"] == "OCR_FAILED"
    assert "OCR execution failed" in res["incomplete_reason"]
    assert "timed out" in res["incomplete_reason"]


def test_end_to_end_scanned_pdf_upload_and_checklist_status(client, monkeypatch):
    """
    Verifies that uploading an incomplete scanned PDF marks the document status as
    EXTRACTION_FAILED and the checklist status as UNREADABLE in the application detail.
    """
    # 1. Create Application
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-OCR-TEST-001",
        "institution_name": "OCR Test Institute of Technology",
        "category": "EOA_REGULAR",
        "declared_intake": 60
    })
    app_id = app_res.json()["id"]

    # 2. Upload a scanned PDF when OCR is unavailable
    monkeypatch.setattr(
        "app.services.document_parser.configure_tesseract",
        lambda: (False, "Tesseract engine not installed on server.")
    )

    scanned_bytes = create_synthetic_scanned_pdf("Scanned NOC with no text layer")
    upload_res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "FIRE_SAFETY_NOC"},
        files={"file": ("Fire_NOC_Scanned.pdf", io.BytesIO(scanned_bytes), "application/pdf")}
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["status"] == "EXTRACTION_FAILED"

    # 3. Inspect application detail checklist: must show UNREADABLE
    detail = client.get(f"/api/applications/{app_id}").json()
    fire_item = next(item for item in detail["document_checklist"] if item["category_code"] == "FIRE_SAFETY_NOC")
    assert fire_item["status"] == "UNREADABLE"
    assert "Incomplete extraction" in fire_item["verification_evidence"]

    # 4. Attempting to approve must be blocked by gating because extraction is incomplete
    approval_attempt = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Attempting approval with incomplete-extraction document.",
            "officer_name": "Prof. R. K. Verma"
        },
        headers={"X-User-Role": "APPROVER", "X-User-Id": "approver1"}
    )
    assert approval_attempt.status_code == 422
    assert "Document extraction incomplete" in approval_attempt.json()["detail"]

