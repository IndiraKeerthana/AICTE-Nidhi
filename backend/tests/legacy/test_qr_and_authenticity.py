import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
import fitz
import qrcode

from app.services.authority_verification import (
    decode_qr_code,
    decode_qr_code_from_image,
    verify_against_authority_registry,
    _extract_reference_from_payload,
    SIMULATED_AUTHORITY_REGISTRY
)
from app.services.anomaly_service import inspect_pdf_metadata_and_updates


def _create_qr_image_bytes(data: str) -> bytes:
    """Helper to generate PNG image bytes of a QR code."""
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_pdf_with_qr_code_json_payload(tmp_path):
    """Test 1: PDF containing a valid QR code with JSON payload."""
    payload_data = json.dumps({"cert_id": "FS-2026-1044", "issued_by": "Fire Dept"})
    qr_png = _create_qr_image_bytes(payload_data)

    pdf_path = tmp_path / "fire_cert_with_qr.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "GOVERNMENT OF MAHARASHTRA - FIRE SAFETY NOC")
    page.insert_image(fitz.Rect(50, 100, 250, 300), stream=qr_png)
    doc.save(str(pdf_path))
    doc.close()

    # 1. Decode QR code
    res = decode_qr_code(str(pdf_path))
    assert res["attempted"] is True
    assert res["found"] is True
    assert res["source_type"] == "PDF"
    assert res["page_number"] == 1
    assert res["pages_scanned"] == 1
    assert res["payload"] == payload_data
    assert "successfully detected and decoded on page 1" in res["notes"]

    # Also check backward-compatible wrapper
    text, notes = decode_qr_code_from_image(str(pdf_path))
    assert text == payload_data

    # 2. Verify against simulated authority registry
    auth_res = verify_against_authority_registry(
        cert_reference=None,
        cert_type="FIRE_SAFETY_NOC",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra",
        qr_payload=res["payload"],
        qr_metadata=res
    )

    assert auth_res["outcome"] == "VERIFIED"
    assert auth_res["status"] == "VERIFIED"
    assert auth_res["lookup_source"] == "QR_CODE"
    assert auth_res["source_reference"] == "FS-2026-1044"
    assert auth_res["is_simulated"] is True
    assert auth_res["qr_attempted"] is True
    assert auth_res["qr_found"] is True
    assert auth_res["qr_page_number"] == 1
    assert "[SIMULATED]" in auth_res["source_name"]


def test_pdf_with_qr_code_url_query_parameter(tmp_path):
    """Test 2: QR code containing a portal verification URL with query parameter."""
    portal_url = "https://fire.maharashtra.gov.in/portal/verify?cert=FS-2026-1044&nonce=78912"
    qr_png = _create_qr_image_bytes(portal_url)

    pdf_path = tmp_path / "url_qr.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(70, 70, 270, 270), stream=qr_png)
    doc.save(str(pdf_path))
    doc.close()

    res = decode_qr_code(str(pdf_path))
    assert res["found"] is True
    assert res["payload"] == portal_url

    # Authority verification parses URL reference without live internet access
    auth_res = verify_against_authority_registry(
        cert_reference=None,
        cert_type="FIRE_SAFETY_NOC",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra",
        qr_payload=res["payload"],
        qr_metadata=res
    )

    assert auth_res["outcome"] == "VERIFIED"
    assert auth_res["source_reference"] == "FS-2026-1044"
    assert auth_res["is_simulated"] is True
    assert "[SIMULATED]" in auth_res["source_name"]


def test_pdf_multipage_qr_on_page_2(tmp_path):
    """Test 3: Multipage PDF where QR code appears on page 2."""
    qr_png = _create_qr_image_bytes("BP-2025-MUN-881")

    pdf_path = tmp_path / "multipage_qr.pdf"
    doc = fitz.open()
    # Page 1: pure text
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 50), "Page 1 - General terms and annexures")
    # Page 2: with QR code
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 50), "Page 2 - Statutory Municipal Endorsement")
    p2.insert_image(fitz.Rect(50, 100, 250, 300), stream=qr_png)
    # Page 3: signature
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text((50, 50), "Page 3 - Signatures")
    doc.save(str(pdf_path))
    doc.close()

    res = decode_qr_code(str(pdf_path), max_pages=3)
    assert res["found"] is True
    assert res["page_number"] == 2
    assert res["pages_scanned"] == 2
    assert res["payload"] == "BP-2025-MUN-881"


def test_pdf_without_qr_code_graceful_handling(tmp_path):
    """Test 4: PDF without a QR code handled gracefully without error or fraud accusation."""
    pdf_path = tmp_path / "no_qr.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Certificate No: FS-2026-1044. Text only certificate without QR code.")
    doc.save(str(pdf_path))
    doc.close()

    res = decode_qr_code(str(pdf_path))
    assert res["attempted"] is True
    assert res["found"] is False
    assert res["payload"] is None
    assert res["page_number"] is None
    assert res["pages_scanned"] == 1
    assert "No readable QR code found" in res["notes"]
    assert res["error"] is None

    # Verify that registry lookup falls back to text reference successfully
    auth_res = verify_against_authority_registry(
        cert_reference="FS-2026-1044",
        cert_type="FIRE_SAFETY_NOC",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra",
        qr_payload=res["payload"],
        qr_metadata=res
    )
    assert auth_res["outcome"] == "VERIFIED"
    assert auth_res["lookup_source"] == "EXTRACTED_TEXT"
    assert auth_res["qr_found"] is False


def test_image_with_qr_code(tmp_path):
    """Test 5: Image document (PNG) containing a QR code."""
    qr_png = _create_qr_image_bytes("UNIV-AFFIL-2025-662")
    img_path = tmp_path / "affiliation_qr.png"
    img_path.write_bytes(qr_png)

    res = decode_qr_code(str(img_path))
    assert res["attempted"] is True
    assert res["found"] is True
    assert res["source_type"] == "IMAGE"
    assert res["page_number"] == 1
    assert res["pages_scanned"] == 1
    assert res["payload"] == "UNIV-AFFIL-2025-662"


def test_large_image_resolution_limit(tmp_path):
    """Test 6: Large image scaled down to respect processing limits."""
    # Create large canvas
    qr_img = qrcode.make("ENV-2025-CLEAR").convert("RGB")
    large_canvas = Image.new("RGB", (3200, 3200), "white")
    large_canvas.paste(qr_img, (500, 500))

    img_path = tmp_path / "large_scan.jpg"
    large_canvas.save(str(img_path), "JPEG")

    res = decode_qr_code(str(img_path), max_dimension=3000)
    assert res["found"] is True
    assert res["source_type"] == "IMAGE"
    assert res["payload"] == "ENV-2025-CLEAR"


def test_unreadable_or_corrupted_document(tmp_path):
    """Test 7: Unreadable / corrupted file handled gracefully with clean error reporting."""
    corrupted_pdf = tmp_path / "corrupted.pdf"
    corrupted_pdf.write_bytes(b"%PDF-1.4\nBROKEN_GARBAGE_BYTES_NO_HEADER")

    res = decode_qr_code(str(corrupted_pdf))
    assert res["attempted"] is True
    assert res["found"] is False
    assert res["payload"] is None
    assert "Error rendering PDF" in res["notes"] or res["error"] is not None


def test_missing_file_path():
    """Test 8: Missing file handled cleanly."""
    res = decode_qr_code("d:/non_existent_folder/missing_doc.pdf")
    assert res["attempted"] is True
    assert res["found"] is False
    assert res["error"] == "FILE_NOT_FOUND"


def test_decoder_failure_handling(tmp_path):
    """Test 9: Internal exception during detection handled gracefully."""
    pdf_path = tmp_path / "dummy.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with patch("app.services.authority_verification._decode_qr_from_cv_image", side_effect=RuntimeError("Simulated CV crash")):
        res = decode_qr_code(str(pdf_path))
        # Should not crash, returns safe structured dict
        assert res["attempted"] is True
        assert res["found"] is False


def test_extract_reference_patterns():
    """Test 10: Extraction of reference keys across various payload formats."""
    # JSON
    assert _extract_reference_from_payload('{"cert_id": "FS-2026-1044"}') == "FS-2026-1044"
    assert _extract_reference_from_payload('{"approval_ref": "BP-2025-MUN-881"}') == "BP-2025-MUN-881"
    assert _extract_reference_from_payload('{"certificate_number": "UNIV-AFFIL-2025-662"}') == "UNIV-AFFIL-2025-662"

    # URL query parameter
    assert _extract_reference_from_payload("https://portal.gov.in/verify?cert=FS-2026-1044") == "FS-2026-1044"
    assert _extract_reference_from_payload("https://portal.gov.in/check?ref=BP-2025-MUN-881&hash=abc") == "BP-2025-MUN-881"
    assert _extract_reference_from_payload("https://portal.gov.in/v?id=ENV-2025-CLEAR") == "ENV-2025-CLEAR"

    # URL path
    assert _extract_reference_from_payload("https://portal.gov.in/verification/FS-2026-1044") == "FS-2026-1044"

    # Plain statutory code
    assert _extract_reference_from_payload("FS-2026-1044") == "FS-2026-1044"


def test_pdf_incremental_updates_structural_check(tmp_path):
    """Test 11: PDF incremental updates check detects %%EOF markers and reports limitation on cryptographic signatures."""
    single_pass_pdf = tmp_path / "single_pass.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(single_pass_pdf))
    doc.close()

    res_single = inspect_pdf_metadata_and_updates(str(single_pass_pdf))
    assert res_single["is_suspicious_modification"] is False

    # Simulate appended incremental revisions by adding trailer markers
    multi_pass_pdf = tmp_path / "multi_pass.pdf"
    content = single_pass_pdf.read_bytes()
    # Append two additional incremental updates
    multi_pass_pdf.write_bytes(content + b"\n%%EOF\n% appended update 1\n%%EOF\n% appended update 2\n%%EOF\n")

    res_multi = inspect_pdf_metadata_and_updates(str(multi_pass_pdf))
    assert res_multi["incremental_updates_count"] >= 2
    assert res_multi["is_suspicious_modification"] is True
    # Verify description clarifies it is a structural inspection, not a digital signature claim
    assert "not cryptographic digital signature verification" in res_multi["explanation"].lower()


def test_simulated_authority_disclosure():
    """Test 12: Ensure all simulated authority responses carry explicit synthetic data disclosure."""
    for ref, record in SIMULATED_AUTHORITY_REGISTRY.items():
        res = verify_against_authority_registry(
            cert_reference=ref,
            cert_type=record["approval_type"],
            institution_name=record.get("institution_name"),
            declared_location=record.get("approved_location")
        )
        assert res["is_simulated"] is True
        assert "[SIMULATED]" in res["source_name"]

