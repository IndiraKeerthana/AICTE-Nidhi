import pytest
from app.services.authority_verification import verify_against_authority_registry, SIMULATED_AUTHORITY_REGISTRY

def test_scenario_a_valid_matching_approval():
    """Scenario A: Successful external authority cross-verification with active status and matching details."""
    res = verify_against_authority_registry(
        cert_reference="BP-2025-MUN-881",
        cert_type="BUILDING_PLAN",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra"
    )
    assert res["outcome"] == "VERIFIED"
    assert res["status"] == "VERIFIED"
    assert res["is_simulated"] is True
    assert res["requires_human_review"] is False
    assert "Municipal Corporation Town Planning Department" in res["source_name"]
    assert "SIMULATED" in res["source_name"]


def test_scenario_b_approval_record_not_found():
    """Scenario B: Approval reference does not exist in the synthetic authority registry."""
    res = verify_against_authority_registry(
        cert_reference="BP-NONEXISTENT-999",
        cert_type="BUILDING_PLAN",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra"
    )
    assert res["outcome"] == "RECORD_NOT_FOUND"
    assert res["status"] == "MISMATCH_DETECTED"
    assert res["requires_human_review"] is True
    assert "not found in the synthetic registry" in res["specific_reason"]
    # Verify no fraud accusation is made
    assert "fraud" not in res["explanation"].lower()


def test_scenario_c_institution_entity_mismatch():
    """Scenario C: Approval reference is registered to a different institution."""
    res = verify_against_authority_registry(
        cert_reference="BP-2023-OTHER-INST",
        cert_type="BUILDING_PLAN",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra"
    )
    assert res["outcome"] == "ENTITY_MISMATCH"
    assert res["status"] == "MISMATCH_DETECTED"
    assert res["requires_human_review"] is True
    assert "Maharashtra Academy of Engineering & Technology" in res["observed_value"]
    assert "Sample Institute of Technology" in res["expected_value"]


def test_scenario_d_approved_location_mismatch():
    """Scenario D: Approval reference exists and institution matches, but approved location differs."""
    res = verify_against_authority_registry(
        cert_reference="BP-2024-DIFF-LOC",
        cert_type="BUILDING_PLAN",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra"
    )
    assert res["outcome"] == "LOCATION_MISMATCH"
    assert res["status"] == "MISMATCH_DETECTED"
    assert res["requires_human_review"] is True
    assert "Hadapsar" in res["observed_value"]
    assert "Kothrud" in res["expected_value"]


def test_scenario_f_expired_approval():
    """Scenario F: Certificate validity has expired."""
    res = verify_against_authority_registry(
        cert_reference="FS-2025-9981",
        cert_type="FIRE_SAFETY_NOC",
        institution_name="Sample Institute of Technology",
        declared_location="Survey 104/2A, Kothrud, Pune, Maharashtra"
    )
    assert res["outcome"] == "EXPIRED"
    assert res["status"] == "EXPIRED"
    assert "2025-09-15" in res["observed_value"]


def test_scenario_f_revoked_or_rejected_approval():
    """Scenario F: Registry records approval as revoked or rejected."""
    revoked_res = verify_against_authority_registry(
        cert_reference="BP-2022-REVOKED",
        cert_type="BUILDING_PLAN",
        institution_name="Sample Institute of Technology"
    )
    assert revoked_res["outcome"] == "STATUS_INVALID"
    assert "REVOKED" in revoked_res["observed_value"]

    rejected_res = verify_against_authority_registry(
        cert_reference="BP-2024-REJECTED",
        cert_type="BUILDING_PLAN",
        institution_name="Sample Institute of Technology"
    )
    assert rejected_res["outcome"] == "STATUS_INVALID"
    assert "REJECTED" in rejected_res["observed_value"]


def test_scenario_g_authority_service_unavailable():
    """Scenario G: Authority gateway timeout or offline."""
    res = verify_against_authority_registry(
        cert_reference="ENV-GATEWAY-TIMEOUT",
        cert_type="ENVIRONMENTAL_CLEARANCE",
        institution_name="Sample Institute of Technology"
    )
    assert res["outcome"] == "AUTHORITY_UNAVAILABLE"
    assert res["status"] == "SOURCE_UNAVAILABLE"
    assert "timed out" in res["specific_reason"].lower()


def test_scenario_g_extraction_incomplete():
    """Scenario G: Missing or unreadable reference number."""
    res = verify_against_authority_registry(
        cert_reference=None,
        cert_type="FIRE_SAFETY_NOC"
    )
    assert res["outcome"] == "EXTRACTION_INCOMPLETE"
    assert res["status"] == "SOURCE_UNAVAILABLE"
    assert "could not be reliably extracted" in res["specific_reason"]
