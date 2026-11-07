import pytest
from app.models import Finding, Alert, Application, AuditEvent

def test_officer_alerts_full_lifecycle(client):
    # 1. Create an application with declared intake mismatch (declared 120 vs baseline 60)
    app_res = client.post("/api/applications", json={
        "aicte_permanent_id": "1-ALERT-TEST-001",
        "institution_name": "Alerts Test Technical Campus",
        "category": "INCREASE_INTAKE",
        "academic_year": "2026-2027",
        "declared_intake": 120
    })
    assert app_res.status_code in (200, 201)
    app_id = app_res.json()["id"]

    # 2. Verify alert created from real scrutiny event and linked to finding & scrutiny run
    alerts_res = client.get("/api/alerts?status_filter=UNRESOLVED")
    assert alerts_res.status_code == 200
    unresolved_alerts = alerts_res.json()
    
    # Filter alerts for this specific application
    app_alerts = [a for a in unresolved_alerts if a["application_id"] == app_id]
    assert len(app_alerts) >= 1

    intake_alert = next((a for a in app_alerts if a["alert_type"] == "RECORD_MISMATCH"), None)
    assert intake_alert is not None
    assert intake_alert["severity"] == "Review required"
    assert intake_alert["status"] == "ACTIVE"
    assert intake_alert["finding_id"] is not None
    assert intake_alert["scrutiny_run_id"] is not None
    assert intake_alert["institution_name"] == "Alerts Test Technical Campus"
    assert "APP-" in intake_alert["application_reference"]

    # 3. Verify repeated processing does not create duplicate active alerts
    # Trigger re-scrutiny without changing data
    rescrutiny_res = client.post(f"/api/applications/{app_id}/return-to-review")
    assert rescrutiny_res.status_code == 200

    alerts_res2 = client.get("/api/alerts?status_filter=UNRESOLVED")
    app_alerts2 = [a for a in alerts_res2.json() if a["application_id"] == app_id and a["alert_type"] == "RECORD_MISMATCH"]
    # Still exactly 1 active/unresolved alert for intake mismatch (no duplicate!)
    assert len(app_alerts2) == 1
    assert app_alerts2[0]["id"] == intake_alert["id"]

    # 4. Verify acknowledgement marks alert seen but DOES NOT resolve finding or change scrutiny
    ack_res = client.post(
        f"/api/alerts/{intake_alert['id']}/acknowledge",
        headers={"X-User-Role": "OFFICER", "X-User-Name": "officer1"}
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # Verify underlying finding is STILL OPEN
    finding_res = client.get(f"/api/applications/{app_id}/findings")
    assert finding_res.status_code == 200
    findings = finding_res.json()
    target_finding = next(f for f in findings if f["id"] == intake_alert["finding_id"])
    assert target_finding["review_status"] == "OPEN"

    # Verify alert is still considered unresolved (seen by officer, but not resolved)
    unresolved_after_ack = [a for a in client.get("/api/alerts?status_filter=UNRESOLVED").json() if a["id"] == intake_alert["id"]]
    assert len(unresolved_after_ack) == 1
    assert unresolved_after_ack[0]["status"] == "ACKNOWLEDGED"

    # 5. Genuinely resolve the finding via reviewer action with justification
    action_res = client.post(f"/api/findings/{target_finding['id']}/action", json={
        "action_type": "RESOLVE",
        "justification_remarks": "Verified State Government capacity expansion approval order dated 15-Jan-2026.",
        "reviewer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
    })
    assert action_res.status_code == 200
    assert action_res.json()["review_status"] == "RESOLVED"

    # 6. Verify alert is now REMOVED from the current attention list
    unresolved_after_resolve = [a for a in client.get("/api/alerts?status_filter=UNRESOLVED").json() if a["id"] == intake_alert["id"]]
    assert len(unresolved_after_resolve) == 0

    # 7. Verify alert history is preserved for audit trail
    all_alerts = client.get("/api/alerts?status_filter=ALL").json()
    hist_alert = next(a for a in all_alerts if a["id"] == intake_alert["id"])
    assert hist_alert["status"] == "RESOLVED"

    # 8a. Gating blocks premature approval recommendation before mandatory documents are submitted
    blocked_dec = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_APPROVAL",
            "justification_remarks": "Premature approval attempt without mandatory documents.",
            "officer_name": "Prof. R. K. Verma (Competent Authority)"
        },
        headers={"X-User-Role": "APPROVER", "X-User-Name": "approver1"}
    )
    assert blocked_dec.status_code == 422
    assert "Approval blocked" in blocked_dec.json()["detail"]

    # 8b. Record Final Decision (RECOMMEND_REJECTION) and verify clean application state
    dec_res = client.post(
        f"/api/applications/{app_id}/decision",
        json={
            "decision": "RECOMMEND_REJECTION",
            "justification_remarks": "Mandatory documentation not furnished by statutory deadline.",
            "officer_name": "Prof. R. K. Verma (Competent Authority)"
        },
        headers={"X-User-Role": "APPROVER", "X-User-Name": "approver1"}
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "REJECTED"
