def test_reviewer_action_and_hash_chained_audit(client):
    # 1. Create Application (which generates intake finding)
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "declared_intake": 120
    })
    app_id = app_res.json()["id"]

    findings = client.get(f"/api/applications/{app_id}/findings").json()
    finding = findings[0]
    finding_id = finding["id"]

    # 2. Reviewer records an action: "REQUEST_DEFICIENCY"
    action_payload = {
        "finding_id": finding_id,
        "action_type": "REQUEST_DEFICIENCY",
        "justification_remarks": "Declared intake of 120 lacks prior approval. Submitting deficiency notice to college.",
        "reviewer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
    }
    action_res = client.post(f"/api/findings/{finding_id}/action", json=action_payload)
    assert action_res.status_code == 200
    updated_finding = action_res.json()
    assert updated_finding["review_status"] == "RECTIFICATION_REQUESTED"
    assert updated_finding["resolution_notes"] == action_payload["justification_remarks"]

    # 3. Verify that the action entered the audit trail
    audit_res = client.get(f"/api/audit/applications/{app_id}")
    assert audit_res.status_code == 200
    audit_events = audit_res.json()
    assert len(audit_events) >= 2  # APPLICATION_CREATED, FINDING_GENERATED, REVIEWER_ACTION

    reviewer_event = next((e for e in audit_events if e["event_type"] == "REVIEWER_ACTION"), None)
    assert reviewer_event is not None
    assert reviewer_event["actor"] == "Dr. V. Sharma (AICTE Scrutiny Officer)"
    assert reviewer_event["details"]["action_type"] == "REQUEST_DEFICIENCY"
    assert reviewer_event["previous_hash"] is not None
    assert reviewer_event["event_hash"] is not None

    # 4. Verify cryptographic hash chain integrity across all events
    chain_res = client.get("/api/audit/verify-chain")
    assert chain_res.status_code == 200
    chain_data = chain_res.json()
    assert chain_data["status"] == "VALID"
    assert chain_data["total_events"] >= len(audit_events)
