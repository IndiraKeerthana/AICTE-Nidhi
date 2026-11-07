import io
import pytest
from app.services.anomaly_service import (
    evaluate_institution_name_similarity,
    inspect_pdf_metadata_and_updates,
    compare_perceptual_hashes
)

def test_name_similarity_abbreviation_variation():
    declared = "Government College of Engineering, Pune"
    cert_with_govt = "Certificate of Affiliation\nThis is to certify that Govt. College of Engineering, Pune is approved."
    score, acceptable = evaluate_institution_name_similarity(declared, cert_with_govt)
    assert acceptable is True
    assert score >= 75.0

    different_inst = "Certificate of Affiliation\nThis is to certify that Apex Institute of Technology, Mumbai is approved."
    score_diff, acceptable_diff = evaluate_institution_name_similarity(declared, different_inst)
    assert acceptable_diff is False
    assert score_diff < 75.0

def test_perceptual_hash_comparison():
    # Identical hash has distance 0
    h1 = "f0f0f0f0f0f0f0f0"
    assert compare_perceptual_hashes(h1, h1) == 0

    # 1-bit difference has distance 1 (match under threshold <= 4)
    h2 = "f0f0f0f0f0f0f0f1"
    assert compare_perceptual_hashes(h1, h2) <= 4

    # Completely different hash
    h3 = "0000000000000000"
    assert compare_perceptual_hashes(h1, h3) > 10

def test_pdf_incremental_modification_detection(tmp_path):
    # Single-pass clean PDF (one %%EOF)
    clean_pdf = tmp_path / "clean.pdf"
    clean_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\nstartxref\n10\n%%EOF\n")
    res_clean = inspect_pdf_metadata_and_updates(str(clean_pdf))
    assert res_clean["incremental_updates_count"] == 0
    assert res_clean["is_suspicious_modification"] is False

    # Modified PDF with multiple %%EOF markers
    mod_pdf = tmp_path / "modified.pdf"
    mod_pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\nstartxref\n10\n%%EOF\n"
        b"2 0 obj\n<<>>\nendobj\ntrailer\n<<>>\nstartxref\n40\n%%EOF\n"
        b"3 0 obj\n<<>>\nendobj\ntrailer\n<<>>\nstartxref\n80\n%%EOF\n"
    )
    res_mod = inspect_pdf_metadata_and_updates(str(mod_pdf))
    assert res_mod["incremental_updates_count"] >= 2
    assert res_mod["is_suspicious_modification"] is True
