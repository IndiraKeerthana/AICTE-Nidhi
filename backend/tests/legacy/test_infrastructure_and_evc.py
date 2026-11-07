import io
import pytest
from PIL import Image
from app.services.infrastructure_review import (
    review_infrastructure_evidence,
    evaluate_application_infrastructure,
    check_cross_slot_photo_reuse
)


def test_review_infrastructure_evidence_valid(tmp_path):
    img = Image.new("RGB", (800, 600), color="blue")
    img_path = tmp_path / "valid_lab.jpg"
    img.save(str(img_path), "JPEG")

    res = review_infrastructure_evidence(str(img_path))
    assert res["status"] == "PASSED"
    assert res["outcome"] == "VERIFIED"
    assert res["width"] == 800
    assert res["height"] == 600
    assert res["aspect_ratio"] == 1.33
    assert res["phash"] is not None
    assert res["is_evc_recommended"] is False


def test_review_infrastructure_evidence_insufficient_resolution(tmp_path):
    # Low resolution: 320x240
    img = Image.new("RGB", (320, 240), color="red")
    img_path = tmp_path / "small_lab.jpg"
    img.save(str(img_path), "JPEG")

    res = review_infrastructure_evidence(str(img_path))
    assert res["status"] == "MANUAL_REVIEW"
    assert res["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert res["requires_human_review"] is True
    assert res["is_evc_recommended"] is True
    assert "below the standard evidence threshold" in res["notes"]


def test_review_infrastructure_evidence_corrupt_file(tmp_path):
    corrupt_file = tmp_path / "broken.jpg"
    corrupt_file.write_bytes(b"INVALID_IMAGE_HEADER_BYTES")

    res = review_infrastructure_evidence(str(corrupt_file))
    assert res["status"] == "FAILED"
    assert res["outcome"] == "CHECK_FAILED"
    assert res["requires_human_review"] is True


def test_evaluate_application_infrastructure_not_applicable():
    class MockApp:
        category = "INCREASE_INTAKE"

    # No infrastructure photos
    results = evaluate_application_infrastructure(MockApp(), [])
    assert len(results) == 1
    assert results[0]["status"] == "NOT_APPLICABLE"
    assert results[0]["requires_human_review"] is False


def test_evaluate_application_infrastructure_with_photo(tmp_path):
    img = Image.new("RGB", (1024, 768), color="green")
    img_path = tmp_path / "campus_lab.png"
    img.save(str(img_path), "PNG")

    class MockDoc:
        id = 42
        document_category = "LAB_INFRASTRUCTURE_PHOTO"
        original_filename = "campus_lab.png"
        storage_path = str(img_path)
        mime_type = "image/png"
        status = "PROCESSED"

    class MockApp:
        category = "INCREASE_INTAKE"

    results = evaluate_application_infrastructure(MockApp(), [MockDoc()])
    assert len(results) == 1
    assert results[0]["status"] == "PASSED"
    assert results[0]["outcome"] == "VERIFIED"
    assert "1024x768" in results[0]["observed_value"]


def test_evc_action_api(client):
    # Create application which generates intake finding
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]
    findings = client.get(f"/api/applications/{app_id}/findings").json()
    finding_id = findings[0]["id"]

    resp = client.post(
        f"/api/findings/{finding_id}/action",
        json={
            "action_type": "RECOMMEND_EVC",
            "justification_remarks": "On-site physical inspection by EVC recommended to verify lab setups and computing hardware.",
            "reviewer_name": "Prof. Officer"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "EVC_RECOMMENDED"
