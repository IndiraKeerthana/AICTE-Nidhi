import io
import fitz  # PyMuPDF

def create_sample_pdf(content: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_invalid_file_upload(client):
    # Create application first
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    # Try uploading an unauthorized file type (.exe)
    invalid_file = io.BytesIO(b"executable binary content")
    res = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "LAND_TITLE_DEED"},
        files={"file": ("malicious.exe", invalid_file, "application/x-msdownload")}
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]

def test_valid_pdf_upload_and_duplicate_detection(client):
    # 1. Create Application
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    # 2. Upload sample Land Title Deed PDF
    pdf_bytes_1 = create_sample_pdf("All India Council for Technical Education\nApproved Land Title: 8.25 Acres in Survey 104/2A.\nIntake Capacity: 60 Seats.")
    res_1 = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "LAND_TITLE_DEED"},
        files={"file": ("Land_Title_Deed.pdf", io.BytesIO(pdf_bytes_1), "application/pdf")}
    )
    assert res_1.status_code == 201
    doc_1_data = res_1.json()
    assert doc_1_data["original_filename"] == "Land_Title_Deed.pdf"
    assert doc_1_data["sha256_hash"] is not None

    # 3. Upload EXACT same file bytes under a different category (e.g. BUILDING_PLAN)
    res_2 = client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_category": "BUILDING_PLAN"},
        files={"file": ("Building_Plan.pdf", io.BytesIO(pdf_bytes_1), "application/pdf")}
    )
    assert res_2.status_code == 201
    doc_2_data = res_2.json()
    assert doc_2_data["sha256_hash"] == doc_1_data["sha256_hash"]

    # 4. Check application findings - duplicate anomaly should be detected!
    app_detail = client.get(f"/api/applications/{app_id}").json()
    dup_finding = next((f for f in app_detail["findings"] if f["category"] == "INTEGRITY_ANOMALY"), None)
    assert dup_finding is not None
    assert dup_finding["severity"] == "CRITICAL"
    assert "Identical Duplicate Document" in dup_finding["title"]
