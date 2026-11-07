# AICTE NIDHI — Demonstration Readiness & Technical Report

**Official Application Name:** AICTE NIDHI  
**Full Name:** AICTE Security Deposit and FDR Management Portal  
**Target User Persona:** Non-technical AICTE Government Scrutiny & Approval Official  
**Repository Location:** `D:\VerifyAI`  
**Date of Audit & Final Sprint:** 27 October 2026  
**Build & Verification Status:** **PASSED — 27/27 TESTS PASSED (100%), FRONTEND PRODUCTION BUILD PASSED (0 ERRORS)**

---

## 1. Executive Summary & Product Philosophy

AICTE-Drishti is an administrative decision-support system designed to assist authorised AICTE officers in application scrutiny. It is not an automated replacement for the AICTE portal, and automated verification checks never independently approve or reject an application.

The application addresses five fundamental administrative questions without requiring technical or programming expertise:

1. **Which application arrived first?**
   - The queue in the Dashboard and All Applications is sorted strictly by actual persisted submission timestamp (**oldest first / FIFO**). The earliest submission appears at the top of the queue with an "Earliest" badge. Artificial priority columns, priority badges, and subjective fraud scores have been completely eliminated.
2. **Which applications are ready for my decision?**
   - A dedicated **Ready for Approval** queue dynamically queries applications where all required scrutiny stages have been completed, all mandatory documents are received, no blocking deficiencies remain, and the application is genuinely awaiting an authorised officer's decision.
3. **What is missing or needs attention?**
   - **Area B** displays a plain-English checklist (`Received`, `Missing`, `Needs review`, `Verified`, `Check incomplete`). **Received does not mean verified.**
   - **Area C** organizes checks into three distinct groups: *Documents still required* (with explicit workflow blocking notices), *Checks that need attention* (distinguishing confirmed discrepancies from possible anomalies or incomplete checks), and *Requirements completed*.
4. **What evidence supports each finding?**
   - Each finding card explains what was checked, what was found, expected vs observed values, why the difference matters, and what remains uncertain.
   - An **"Inspect Document (Page X)"** action opens the attachment in an in-app viewer (PDF streaming directly to `#page=N` or image inspection with 60%–200% zoom controls) without leaving AICTE-Drishti.
5. **What action should I take next?**
   - **Area E** provides dedicated administrative actions: *Request Additional Information (Deficiency Notice)*, *Send for Re-Scrutiny*, and *Record Statutory Decision* (requiring justification remarks).

---

## 2. Mock External-Authority Cross-Verification & Section 10 Outcomes

Because live government issuing authority registries are inaccessible during the hackathon, AICTE-Drishti implements a synthetic authority registry with clear disclosures:

> **SIMULATED EXTERNAL CHECK — SYNTHETIC DATA**

### Granular Verification Outcomes (Section 10)
Rather than collapsing results into a generic "Not Verified" state, the system distinguishes specific outcomes supported by evidence:

| Outcome Code | Meaning & Display Title | Evidence Classification | Handling & Next Action |
| :--- | :--- | :--- | :--- |
| `VERIFIED` | Required fields, authority reference, institution name, and location match active registry record. | `VERIFIED_FACT` | Statutory verification complete. Proceed with scrutiny. |
| `RECORD_NOT_FOUND` | No matching record exists in the synthetic registry. | `AUTOMATED_INFERENCE` | Explains typing variance, unindexed division, or unconfirmed approval without making an accusation of fraud. Recommends manual confirmation. |
| `LOCATION_MISMATCH` | Approval exists and belongs to the institution, but the approved campus location differs. | `VERIFIED_FACT` | Shows expected vs observed campus location. Recommends requesting municipal relocation or land conversion order. |
| `ENTITY_MISMATCH` | Approval exists, but belongs to a different synthetic institution in the registry. | `VERIFIED_FACT` | Shows registered institution vs declared institution. Recommends examining parent trust deed. |
| `STATUS_INVALID` | Approval record is marked as `REVOKED` or `REJECTED` in the registry. | `VERIFIED_FACT` | Flags for scrutiny committee review and issues deficiency notice. |
| `EXPIRED` | Certificate validity date has expired. | `VERIFIED_FACT` | Identifies elapsed date; recommends requesting renewed clearance. |
| `AUTHORITY_UNAVAILABLE` | Gateway connection timed out or service offline. | `CHECK_NOT_COMPLETED` | Clearly indicates check could not be completed; does not accuse applicant. |
| `EXTRACTION_INCOMPLETE` | Certificate reference could not be reliably extracted from the uploaded document. | `CHECK_NOT_COMPLETED` | Directs officer to inspect document via the in-app viewer. |
| `POSSIBLE_TAMPERING` | Multi-pass incremental PDF modifications detected. | `POTENTIAL_ANOMALY` | Identifies specific signal and its limitations without declaring fraud. |
| `DUPLICATE_OR_REUSED_DOCUMENT` | Identical cryptographic SHA-256 hash or perceptual photo reuse across slots. | `POTENTIAL_ANOMALY` | Discloses duplicate match without making unsupported criminal claims. |

---

## 3. Files Modified & Created

| File Path | Status | Key Changes |
| :--- | :--- | :--- |
| `backend/app/services/authority_verification.py` | Modified | Added simulated issuing authority registry covering Scenarios A–G (Building Plans, Fire Safety NOCs, Affiliation Letters, Environmental Clearances). Moved `_norm_location_tokens` to module scope and resolved variable scoping. |
| `backend/app/services/orchestrator.py` | Modified | Check 6 expanded to cross-verify all configured authority document categories; persisted in `authority_verifications` table; updated `_upsert_finding` to record `page_num` and `supporting_page_number`; mapped outcomes cleanly. |
| `backend/app/models/__init__.py` | Preserved | Verified `AuthorityVerification`, `Finding`, `ScrutinyRun`, `CheckResult`, `Document`, `Application`, and `Alert` models and relationships. |
| `backend/app/api/runs.py` | Modified | Ensured scrutiny run and findings endpoints return granular verification payloads and page references. |
| `backend/tests/test_authority_verification_scenarios.py` | Created | Pytest test suite covering Scenarios A, B, C, D, F, and G. |
| `backend/scripts/verify_end_to_end_demo.py` | Created | 10-step automated verification script validating the end-to-end scrutiny and decision lifecycle. |
| `frontend/src/components/Sidebar.tsx` | Modified | Updated navigation to 5 primary items with *Ready for Approval* as item 3; session card displays "AICTE Official". |
| `frontend/src/components/Header.tsx` | Modified | Removed role-switcher dropdown and demo identities; displayed static "AICTE Official" session badge. |
| `frontend/src/components/DashboardOverview.tsx` | Rewritten | Removed "Needs Your Attention" panel and emergency widgets; implemented clean 4-count workload overview; implemented clear natural-language Current Status labels and separate Next Action column; FIFO oldest-first queue sort. |
| `frontend/src/components/ApplicationDetails.tsx` | Rewritten | Removed Sections A–F literal headers; removed Section F audit timeline UI; implemented Areas A–E with refined "Checks That Need Attention" (focused strictly on submitted requirements needing confirmation/review, with direct in-app viewer actions and responsible parties), and `SIMULATED EXTERNAL CHECK — SYNTHETIC DATA` disclosure. |
| `frontend/src/components/DocumentViewerModal.tsx` | Created | In-app modal viewer supporting PDF streaming (`#page=N`), zoomable images, and extracted text drawer. |
| `frontend/src/App.tsx` | Modified | Handled `ready_for_approval` view; wired single officer session; maintained persistent prototype banner and governance footer. |

---

## 4. Database Schema & Persistence

The prototype uses SQLite (`backend/verifyai.db`). The following persistent models support verification and scrutiny:

1. **`authority_verifications`**:
   - `id`: Primary key
   - `application_id`: Foreign key to `applications.id`
   - `document_id`: Foreign key to `documents.id`
   - `verification_type`: `REGISTRY_LOOKUP` or `QR_CODE`
   - `source_name`: Simulated authority gateway name
   - `source_reference`: Approval or certificate reference
   - `status`: Verification outcome status (`VERIFIED`, `MISMATCH_DETECTED`, `SOURCE_UNAVAILABLE`)
   - `evidence_payload`: Full JSON payload with expected vs observed fields, specific reasons, and recommendations
   - `is_simulated`: `True`
   - `created_at`: Timestamp
2. **`findings`**:
   - Stores finding code, severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), category, `evidence_classification` (`VERIFIED_FACT`, `AUTOMATED_INFERENCE`, `POTENTIAL_ANOMALY`, `CHECK_NOT_COMPLETED`), `title`, `description`, `expected_value`, `observed_value`, `supporting_document_id`, `supporting_page_number`, `recommended_action`, and `review_status`.
3. **`reviewer_actions`**:
   - Persists all officer actions (`REQUEST_DEFICIENCY`, `OVERRIDE`, `RESOLVE`, `RECOMMEND_APPROVAL`, `RECOMMEND_REJECTION`) along with mandatory justification remarks and reviewer designation.

---

## 5. API Endpoints

| Endpoint | Method | Role & Description |
| :--- | :--- | :--- |
| `/api/applications` | GET, POST | List all applications (sorted by submission timestamp) or create a new application. |
| `/api/applications/{id}` | GET | Get full application details, including documents, check results, findings, and alerts. |
| `/api/applications/{id}/documents` | POST | Upload a document attachment; triggers automatic OCR, hashing, integrity checks, and authority verification. |
| `/api/applications/{id}/documents/{doc_id}/raw` | GET | Stream raw document bytes for in-app PDF viewing and image inspection. |
| `/api/applications/{id}/scrutiny/run` | POST | Trigger or re-run automated scrutiny pipeline for an application. |
| `/api/applications/{id}/actions` | POST | Persist an officer action (Deficiency Notice, Finding Resolution, or Final Statutory Decision). |
| `/api/alerts` | GET | Retrieve active administrative alerts for officer navigation. |
| `/api/health` | GET | System health check (database, OCR engine, and storage status). |

---

## 6. Test & Build Execution Results

### A. Full Backend Pytest Suite
```powershell
cd D:\VerifyAI\backend
.\.venv\Scripts\pytest.exe --show-capture=no
```
**Actual Result:**
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1
rootdir: D:\VerifyAI\backend
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 27 items

tests\test_actions_audit.py .                                            [  3%]
tests\test_applications.py .                                             [  7%]
tests\test_authority_verification_scenarios.py ........                  [ 37%]
tests\test_detectors_demo.py ...                                         [ 48%]
tests\test_documents.py ..                                               [ 55%]
tests\test_health.py ..                                                  [ 62%]
tests\test_integration_and_pipeline.py ...                               [ 74%]
tests\test_officer_alerts_workflow.py .                                  [ 77%]
tests\test_verification.py .                                             [ 81%]
tests\test_workflow_and_rbac.py .....                                    [100%]

======================= 27 passed, 3 warnings in 2.49s ========================
```

### B. End-to-End Demo Script
```powershell
cd D:\VerifyAI\backend
.\.venv\Scripts\python.exe scripts/verify_end_to_end_demo.py
```
**Actual Result:**
```
======================================================================
ALL 10 DEMO STEPS + CLEAN APPLICATION VERIFIED WITH ZERO ERRORS!
======================================================================
```

### C. Frontend Production Build
```powershell
cd D:\VerifyAI\frontend
npm run build
```
**Actual Result:**
```
> aicte-drishti-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 1584 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.98 kB │ gzip:  0.58 kB
dist/assets/index-_to5m5my.css   42.79 kB │ gzip:  7.63 kB
dist/assets/index-C396Ytru.js   326.08 kB │ gzip: 82.06 kB
✓ built in 2.74s
```

---

## 7. Demonstration Guide: Scenarios A through I

### Scenario A: Successful External Verification
- **Test Reference:** `BP-2025-MUN-881` or `FS-2026-1044`
- **Application Details:** Sample Institute of Technology, Survey 104/2A, Kothrud, Pune.
- **Observed Behavior:** Status indicates `VERIFIED`. Authority record holder matches applicant institution and approved location. Clear disclosure: `SIMULATED EXTERNAL CHECK — SYNTHETIC DATA`.

### Scenario B: Approval Record Not Found
- **Test Reference:** `BP-2024-NONEXISTENT`
- **Observed Behavior:** Outcome displays `Approval Record Not Found`. Explains that the reference was not indexed in the synthetic municipal town planning registry, notes that this may be a clerical typing variance or an unindexed regional office, and recommends manual officer confirmation.

### Scenario C: Institution / Entity Mismatch
- **Test Reference:** `BP-2023-OTHER-INST`
- **Observed Behavior:** Outcome displays `Institution Entity Mismatch`. Identifies that the certificate reference exists in the registry but is issued to "Apex Technical Academy" rather than "Sample Institute of Technology". Shows expected vs observed values.

### Scenario D: Location Mismatch
- **Test Reference:** `BP-2024-DIFF-LOC`
- **Observed Behavior:** Outcome displays `Approved Location Mismatch`. Identifies that the municipal registry record is registered for "Plot 45, Hadapsar Industrial Area" while the applicant's declared campus is "Survey 104/2A, Kothrud". Recommends requesting a municipal campus relocation order.

### Scenario E: Possible Tampering
- **Test Reference:** Document with appended revisions after initial generation.
- **Observed Behavior:** Detected by PDF structural analyzer (`incremental_updates_count > 1`). Finding explains that appended revisions were detected without declaring automatic fraud, recommending that the officer inspect the document pages using the in-app viewer.

### Scenario F: Expired or Revoked Statutory Approval
- **Test Reference:** `BP-2022-REVOKED` (Revoked) or `FS-2021-EXP` (Expired)
- **Observed Behavior:** Outcome displays `Revoked / Invalid Statutory Approval` or `Expired Statutory Clearance`. Explains the specific cancellation or expiry date and recommends issuing a deficiency notice.

### Scenario G: Incomplete Verification / Gateway Unavailable
- **Test Reference:** `ENV-GATEWAY-TIMEOUT`
- **Observed Behavior:** Outcome displays `External Verification Gateway Unavailable`. Indicates HTTP 504 Gateway Timeout on the simulated authority portal; does not penalize or accuse the applicant.

### Scenario H: Missing Mandatory Document (Process Gating)
- **Observed Behavior:** When a mandatory document (e.g. `FIRE_SAFETY_NOC`) is not uploaded:
  1. Area C displays under **Documents still required**: *"Application cannot proceed yet. The Fire Safety NOC is missing. The institution must submit it before scrutiny can continue."*
  2. The application is blocked from entering `READY_FOR_REVIEW`.
  3. Uploading the document re-runs scrutiny and updates affected findings without resolving unrelated issues.

### Scenario I: Officer Decision
- **Observed Behavior:**
  1. An application appears in **Ready for Approval** only when all checks pass and all mandatory documents are present.
  2. The officer reviews evidence, enters mandatory justification remarks, and records the final statutory decision (*Recommend Approval* or *Recommend Rejection*).
  3. The decision is persisted in `reviewer_actions`, the application status updates to *Decision recorded*, and the application is dynamically removed from the *Ready for Approval* queue.

### Scenario J: Findings and Supporting Evidence (Area D Redesign)
- **Observed Behavior:**
  1. Replaced crowded, technical 5-column grid with clean, concise, officer-friendly cards categorized into 5 distinct groups:
     - **Missing Mandatory Documents** (Status: *Documents missing*)
     - **Discrepancies & Baseline Differences** (Status: *Difference found*)
     - **Submitted Requirements Awaiting Verification or Approval** (Status: *Awaiting verification* or *Validity expired*)
     - **Potential Document Integrity Issues** (Status: *Further review required*)
     - **Incomplete Checks & Gateway Limitations** (Status: *Check incomplete*)
  2. Each card is structured around the officer's three core questions:
     - **What was found**: Clear, plain-language description
     - **Why does it matter**: Regulatory relevance and statutory rationale
     - **What should happen next**: Concrete next action for the officer
  3. Simple 2-column comparison (*Expected standard* vs *Observed in submission*) displayed only when relevant and available.
  4. Supporting documents open in the in-app document viewer via a dedicated **View evidence** button.
  5. Expandable **Technical details** drawer hides verification source, standard classification, and raw text snippets by default to keep cards concise.
  6. Replaced generic *Take Action* button with context-specific actions: **Review finding**, **Request clarification**, and **View evidence**.
  7. Production build (`npm run build`) and full backend pytest suite (27/27) pass with zero errors.

---

## 8. Known Limitations & Prototype Boundaries

1. **Simulated Authority Registries:** All municipal town planning, fire safety, and state university registries are synthetic mock databases. No connection to live government or confidential databases is claimed or attempted.
2. **OCR Engine:** Relies on PyMuPDF and local PDF parsing. Scanned handwritten physical papers without embedded text or OCR engine require manual inspection using the in-app viewer.
3. **Legal Responsibility:** The software is strictly an advisory decision-support system. All statutory decisions are made and recorded by the authorised human officer.

---

## 9. Commands to Run Frontend & Backend

### 1. Backend Service (FastAPI)
```powershell
cd D:\VerifyAI\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Health Check: `http://127.0.0.1:8000/api/health`
- OpenAPI Documentation: `http://127.0.0.1:8000/docs`

### 2. Frontend Development Server (React + Vite)
```powershell
cd D:\VerifyAI\frontend
npm run dev
```
- Web Application URL: `http://localhost:5173`

---
*AICTE-Drishti — AI flags and explains. The authorised officer decides.*

