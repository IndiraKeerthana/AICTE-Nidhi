import datetime

INTEGRATION_SERVICES = [
    {
        "id": "aicte_portal",
        "name": "AICTE Central Application Portal Adapter",
        "category": "UPSTREAM_INTAKE",
        "mode": "DEMO_SIMULATOR",
        "status": "OPERATIONAL_IN_DEMO_MODE",
        "is_simulated": True,
        "endpoint": "/api/integration/v1/applications",
        "external_target": "AICTE National e-Governance Portal (Production access pending official credentials)",
        "protocol": "REST / JSON Webhook (X-Integration-Key & X-Idempotency-Key)",
        "last_checked": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": "Receives institutional applications via authenticated webhook. Operates in demonstrative mode; production switch requires official AICTE API key."
    },
    {
        "id": "fire_safety_directorate",
        "name": "State Fire & Emergency Services Directorate",
        "category": "ISSUING_AUTHORITY",
        "mode": "DEMO_SIMULATOR",
        "status": "OPERATIONAL_IN_DEMO_MODE",
        "is_simulated": True,
        "endpoint": "Simulated In-Memory Authority Registry",
        "external_target": "State Fire Services Citizen Portal Gateway",
        "protocol": "Synchronous Verification API",
        "last_checked": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": "Verifies Fire NOC certificate number, valid tenure, and issuing municipal authority against synthetic reference ground truth."
    },
    {
        "id": "state_university_registry",
        "name": "State Technical University Affiliation Portal",
        "category": "ISSUING_AUTHORITY",
        "mode": "DEMO_SIMULATOR",
        "status": "OPERATIONAL_IN_DEMO_MODE",
        "is_simulated": True,
        "endpoint": "Simulated University Affiliation Records",
        "external_target": "University Board Affiliation Registry",
        "protocol": "REST Registry Verification",
        "last_checked": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": "Reconciles college affiliation orders, approved intake per branch, and academic year validity against university baseline."
    },
    {
        "id": "digilocker_nad",
        "name": "DigiLocker / National Academic Depository (NAD)",
        "category": "STATUTORY_REPOSITORY",
        "mode": "UNAVAILABLE",
        "status": "UNAVAILABLE",
        "is_simulated": False,
        "endpoint": "https://api.digitallocker.gov.in/v1 [UNCONFIGURED]",
        "external_target": "Government of India DigiLocker Requester Gateway",
        "protocol": "OAuth 2.0 / MeitY REST",
        "last_checked": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": "Official repository for verified marksheets and deeds. Marked as 'Verification unavailable' until official requester credentials are provided."
    },
    {
        "id": "qr_signature_engine",
        "name": "2D QR Code & Cryptographic Document Inspector",
        "category": "LOCAL_ENGINE",
        "mode": "LOCAL_ACTIVE",
        "status": "CONNECTED",
        "is_simulated": False,
        "endpoint": "OpenCV QRCodeDetector + PyMuPDF Engine",
        "external_target": "Local Native Sandbox",
        "protocol": "In-process Native Inspection",
        "last_checked": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": "Active local processing engine that parses embedded 2D QR payloads and detects incremental PDF alterations without internet dependency."
    }
]

def get_all_integration_statuses() -> list[dict]:
    # Update timestamp
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = []
    for s in INTEGRATION_SERVICES:
        item = dict(s)
        item["last_checked"] = now
        results.append(item)
    return results
