def test_synthetic_intake_mismatch_verification(client):
    """
    Verifies that declaring an intake of 120 against a baseline approved intake of 60
    triggers a high-severity RECORD_MISMATCH finding with full evidence and explainability.
    """
    payload = {
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "academic_year": "2026-2027",
        "declared_programme": "ENGINEERING_AND_TECHNOLOGY",
        "declared_course": "Computer Science & Engineering",
        "declared_intake": 120, # Declaring 120 seats
        "declared_land_acres": 8.25
    }

    res = client.post("/api/applications", json=payload)
    assert res.status_code == 201
    app_id = res.json()["id"]

    # Retrieve application findings
    findings_res = client.get(f"/api/applications/{app_id}/findings")
    assert findings_res.status_code == 200
    findings = findings_res.json()

    # Locate the intake mismatch finding
    intake_finding = next((f for f in findings if f["category"] == "RECORD_MISMATCH"), None)
    assert intake_finding is not None
    assert intake_finding["severity"] == "HIGH"
    assert "Sanctioned Intake Mismatch" in intake_finding["title"]
    assert "60 Seats" in intake_finding["expected_value"]
    assert "120 Seats" in intake_finding["observed_value"]
    assert "APH-2026-INTAKE-04" in intake_finding["rule_code"]
    assert intake_finding["review_status"] == "OPEN"
    assert len(intake_finding["recommended_action"]) > 10
