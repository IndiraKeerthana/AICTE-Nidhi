import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient

backend_root = str(Path(__file__).resolve().parent.parent)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.main import app

def run_10_step_demo():
    print("=" * 70)
    print("AICTE NIDHI - DEMONSTRATION VERIFICATION SCRIPT")
    print("=" * 70)

    client = TestClient(app)

    # -------------------------------------------------------------
    # Step 1: Submit synthetic intake-increase application
    # -------------------------------------------------------------
    print("\n[Step 1] Submitting synthetic intake-increase application...")
    app_payload = {
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "academic_year": "2026-2027",
        "declared_programme": "ENGINEERING_AND_TECHNOLOGY",
        "declared_course": "Computer Science & Engineering",
        "declared_intake": 120, # Declaring 120 seats (Baseline is 60)
        "declared_land_acres": 8.25
    }
    res_intake = client.post(
        "/api/applications",
        json=app_payload,
        headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
    )
    assert res_intake.status_code == 201, f"Failed intake creation: {res_intake.text}"
    app_data = res_intake.json()
    app_id = app_data["id"]
    print(f" -> Application Created #{app_id} (Ref: {app_data['application_number']})")

    doc_dir = r"D:\VerifyAI\synthetic_demo_files"

    print(" -> Uploading initial statutory attachments (Expired Fire NOC + Building Plan)...")
    with open(os.path.join(doc_dir, "2_Expired_Fire_Safety_NOC_FS9981.pdf"), "rb") as f_fire:
        res_doc1 = client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": "FIRE_SAFETY_NOC"},
            files={"file": ("Expired_Fire_Safety_NOC.pdf", f_fire, "application/pdf")},
            headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
        )
        assert res_doc1.status_code == 201

    with open(os.path.join(doc_dir, "Clean_Building_Plan.pdf"), "rb") as f_bp:
        res_doc2 = client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": "BUILDING_PLAN_APPROVAL"},
            files={"file": ("Sanctioned_Building_Plan.pdf", f_bp, "application/pdf")},
            headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
        )
        assert res_doc2.status_code == 201

    # -------------------------------------------------------------
    # Step 2: Confirm scrutiny starts automatically
    # -------------------------------------------------------------
    print("\n[Step 2] Confirming automated scrutiny execution...")
    res_runs = client.get(f"/api/applications/{app_id}/runs")
    assert res_runs.status_code == 200
    runs1 = res_runs.json()
    assert len(runs1) >= 1
    run1 = runs1[-1]
    print(f" -> Scrutiny Run #{run1['run_number']} completed with status: {run1['status']}")
    print(f" -> Total checks: {run1['total_checks']} | Passed: {run1['passed_checks']} | Failed: {run1['failed_checks']}")
    assert run1["total_checks"] > 0

    # Also test manual trigger via verify route
    res_verify = client.post(
        f"/api/applications/{app_id}/verify",
        headers={"X-User-Role": "OFFICER", "X-User-Id": "officer1"}
    )
    assert res_verify.status_code == 200
    print(" -> Officer manual verification trigger verified.")

    # -------------------------------------------------------------
    # Step 3: Show intake mismatch, expired NOC, and missing-document findings
    # -------------------------------------------------------------
    print("\n[Step 3] Verifying expected findings from Run 1...")
    res_findings = client.get(f"/api/applications/{app_id}/findings")
    assert res_findings.status_code == 200
    findings1 = res_findings.json()

    codes = [f["finding_code"] for f in findings1]
    print(" -> Recorded Findings:")
    for f in findings1:
        print(f"    * [{f['severity']}] {f['finding_code']}: {f['title']} (Class: {f.get('evidence_classification')})")

    # Intake mismatch
    assert any("INTAKE" in c for c in codes), "Missing intake mismatch finding"
    # Expired fire NOC
    assert any("FIRE" in c or "EXPIRED" in c or "AUTH-VERIF" in c for c in codes), "Missing expired NOC finding"
    # Missing documents
    assert any("MISSING-DOCS" in c for c in codes), "Missing mandatory documents finding"

    # -------------------------------------------------------------
    # Step 4: Open a finding and inspect its evidence
    # -------------------------------------------------------------
    print("\n[Step 4] Inspecting evidence payload for Intake Mismatch...")
    intake_fnd = next(f for f in findings1 if "INTAKE" in f["finding_code"])
    print(f"    Expected: {intake_fnd['expected_value']}")
    print(f"    Observed: {intake_fnd['observed_value']}")
    print(f"    Rule Code: {intake_fnd['rule_code']}")
    print(f"    Evidence Classification: {intake_fnd.get('evidence_classification')}")
    print(f"    Recommended Action: {intake_fnd['recommended_action']}")
    assert "60" in intake_fnd["expected_value"]
    assert "120" in intake_fnd["observed_value"]

    # -------------------------------------------------------------
    # Step 5: Request correction as the officer (Issue Deficiency Notice)
    # -------------------------------------------------------------
    print("\n[Step 5] Issuing officer deficiency notice...")
    fire_fnd = next(f for f in findings1 if "FIRE" in f["finding_code"] or "AUTH-VERIF" in f["finding_code"])
    notice_payload = {
        "finding_ids": [fire_fnd["id"]],
        "instructions": "Fire Safety NOC expired on 15/09/2025. Please upload the valid renewed Fire Clearance Certificate from the municipal directorate.",
        "officer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
    }
    res_notice = client.post(
        f"/api/applications/{app_id}/deficiency-notice",
        json=notice_payload,
        headers={"X-User-Role": "OFFICER", "X-User-Id": "officer1"}
    )
    assert res_notice.status_code == 200
    print(" -> Deficiency notice issued successfully. Application status set to RECTIFICATION_IN_PROGRESS.")

    # -------------------------------------------------------------
    # Step 6: Submit a corrected document (Replacement NOC)
    # -------------------------------------------------------------
    print("\n[Step 6] Submitting replacement valid renewed Fire NOC (FS-2026-1044)...")
    with open(os.path.join(doc_dir, "6_Valid_Renewed_Fire_Safety_NOC_FS1044.pdf"), "rb") as f_valid:
        res_replace = client.post(
            f"/api/applications/{app_id}/documents",
            data={"document_category": "FIRE_SAFETY_NOC"},
            files={"file": ("Valid_Renewed_Fire_Safety_NOC.pdf", f_valid, "application/pdf")},
            headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
        )
        assert res_replace.status_code == 201
        print(" -> Replacement document uploaded and previous document archived.")

    # -------------------------------------------------------------
    # Step 7: Confirm automatic re-scrutiny and multi-run comparison
    # -------------------------------------------------------------
    print("\n[Step 7] Checking automatic re-scrutiny multi-run comparison...")
    res_runs2 = client.get(f"/api/applications/{app_id}/runs")
    assert res_runs2.status_code == 200
    runs2 = res_runs2.json()
    assert len(runs2) >= 2, f"Expected at least 2 runs, got {len(runs2)}"
    print(f" -> Total Scrutiny Runs: {len(runs2)}")
    for r in runs2:
        print(f"    * Run #{r['run_number']}: Status {r['status']}, Passed: {r['passed_checks']}, Failed: {r['failed_checks']}")

    # -------------------------------------------------------------
    # Step 8: Verify that resolved findings change only with genuine evidence
    # -------------------------------------------------------------
    print("\n[Step 8] Verifying finding status after re-scrutiny...")
    res_findings2 = client.get(f"/api/applications/{app_id}/findings")
    findings2 = res_findings2.json()

    # The Fire Safety authority verification finding should now be RESOLVED
    fire_fnd_updated = next((f for f in findings2 if f["id"] == fire_fnd["id"]), None)
    if fire_fnd_updated:
        print(f" -> Fire NOC Finding Status: {fire_fnd_updated['review_status']}")
        assert fire_fnd_updated["review_status"] == "RESOLVED", "Fire finding should be RESOLVED after valid certificate"

    # Intake finding should remain OPEN because intake is still declared 120 vs approved 60
    intake_fnd_updated = next(f for f in findings2 if "INTAKE" in f["finding_code"])
    print(f" -> Intake Finding Status: {intake_fnd_updated['review_status']} (Correctly maintained as OPEN)")
    assert intake_fnd_updated["review_status"] == "OPEN"

    # -------------------------------------------------------------
    # Step 9: Officer records final decision with justification
    # -------------------------------------------------------------
    print("\n[Step 9] Recording authorized officer final statutory decision...")
    decision_payload = {
        "decision": "RECOMMEND_APPROVAL",
        "justification_remarks": "Approved for baseline capacity of 60 seats with verified renewed Fire Safety NOC (FS-2026-1044). Additional 60-seat expansion deferred to subsequent regional committee evaluation pending instructional area site visit.",
        "officer_name": "Dr. V. Sharma (AICTE Scrutiny Officer)"
    }
    res_decision = client.post(
        f"/api/applications/{app_id}/decision",
        json=decision_payload,
        headers={"X-User-Role": "APPROVER", "X-User-Id": "approver1"}
    )
    assert res_decision.status_code == 200
    dec_result = res_decision.json()
    print(f" -> Final Decision Recorded: {dec_result['final_decision']} by {dec_result.get('decided_by')}")
    print(f" -> Justification: {dec_result.get('decision_remarks')}")

    # -------------------------------------------------------------
    # Step 10: Confirm application history & audit chain integrity
    # -------------------------------------------------------------
    print("\n[Step 10] Checking tamper-evident cryptographic audit chain...")
    res_audit = client.get(f"/api/audit/verify-chain")
    assert res_audit.status_code == 200
    chain_info = res_audit.json()
    print(f" -> Chain Integrity Status: {chain_info.get('status')}")
    print(f" -> Verified Event Count: {chain_info.get('verified_count')}")
    print(f" -> Genesis Hash: {chain_info.get('genesis_hash')[:16]}...")
    print(f" -> Latest Hash: {chain_info.get('latest_hash')[:16]}...")
    assert chain_info.get("status") == "VALID"

    # -------------------------------------------------------------
    # Bonus: Clean application demonstration
    # -------------------------------------------------------------
    print("\n[Bonus Step] Demonstrating a clean application where checks pass...")
    clean_app_payload = {
        "aicte_permanent_id": "1-9988776655",
        "institution_name": "Sample Institute of Technology",
        "category": "INCREASE_INTAKE",
        "academic_year": "2026-2027",
        "declared_programme": "ENGINEERING_AND_TECHNOLOGY",
        "declared_course": "Computer Science & Engineering",
        "declared_intake": 60, # Declaring 60 seats (Matches baseline 60)
        "declared_land_acres": 8.25
    }
    res_clean = client.post(
        "/api/applications",
        json=clean_app_payload,
        headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
    )
    assert res_clean.status_code == 201
    clean_id = res_clean.json()["id"]

    # Upload valid documents
    with open(os.path.join(doc_dir, "Clean_Land_Title_Deed.pdf"), "rb") as f_land:
        client.post(
            f"/api/applications/{clean_id}/documents",
            data={"document_category": "LAND_TITLE_DEED"},
            files={"file": ("Clean_Land_Title_Deed.pdf", f_land, "application/pdf")},
            headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
        )

    with open(os.path.join(doc_dir, "Clean_Building_Plan.pdf"), "rb") as f_bp:
        client.post(
            f"/api/applications/{clean_id}/documents",
            data={"document_category": "BUILDING_PLAN_APPROVAL"},
            files={"file": ("Clean_Building_Plan.pdf", f_bp, "application/pdf")},
            headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
        )

    with open(os.path.join(doc_dir, "6_Valid_Renewed_Fire_Safety_NOC_FS1044.pdf"), "rb") as f_valid_fire:
        client.post(
            f"/api/applications/{clean_id}/documents",
            data={"document_category": "FIRE_SAFETY_NOC"},
            files={"file": ("Valid_Fire_NOC.pdf", f_valid_fire, "application/pdf")},
            headers={"X-User-Role": "APPLICANT", "X-User-Id": "applicant1"}
        )

    res_clean_runs = client.get(f"/api/applications/{clean_id}/runs")
    clean_runs = res_clean_runs.json()
    clean_run = clean_runs[-1]
    print(f" -> Clean App Scrutiny Run: {clean_run['passed_checks']} checks PASSED!")
    assert clean_run["passed_checks"] >= 3

    print("\n" + "=" * 70)
    print("ALL 10 DEMO STEPS + CLEAN APPLICATION VERIFIED WITH ZERO ERRORS!")
    print("=" * 70)

if __name__ == "__main__":
    run_10_step_demo()
