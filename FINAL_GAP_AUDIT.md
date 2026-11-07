# AICTE NIDHI — Final Problem Statement Gap Audit
**Smart India Hackathon 2026 | Problem Statement 26261**  
**Project:** AICTE NIDHI (Security Deposit and FDR Management Portal)  
**Repository Path:** `D:\VerifyAI`  
**Audit Local Date:** 28 October 2026  
**Auditor:** Antigravity AI (DeepMind Pair Programmer)  
**Audit Standard:** Code-First & Empirical Test Execution (No documentation claims taken on faith)

---

## 1. Executive Summary

This comprehensive audit evaluates the actual implementation of **AICTE-Drishti** against the SIH 2026 Problem Statement 26261 requirements, published documentation, test suite outputs, and production builds.

### 1.1 Overall Audit Verdict
AICTE-Drishti is an **exceptionally strong, functional, and visually polished demonstration prototype**. It successfully establishes a genuine end-to-end vertical slice from application intake to automated multi-module scrutiny, evidence generation, in-app document viewing, deficiency rectification, and authorized officer decision-making. The user experience strictly upholds the core institutional principle: **"The system flags and explains. The authorised officer decides."**

However, an exhaustive line-by-line inspection of the backend services, rules engine, document parser, and database layer reveals **critical technical gaps, unverified features, architectural compromises, and documentation discrepancies** that must not be claimed as complete or production-ready during evaluation:
1. **Scanned PDF OCR is Incomplete:** While `pytesseract` is imported and used on standalone image uploads, scanned PDFs with `< 30` characters are flagged with `ocr_needed = True` and `extraction_method = "OCR_TESSERACT"`, but **PDF pages are never rasterized to pixmaps or passed to Tesseract**. Scanned PDFs produce empty extracted text.
2. **Digital Signatures are Missing:** Cryptographic digital signature validation (PKCS#7, PAdES, e-Sign, X.509 certificates) is completely unbuilt.
3. **QR Code Extraction Fails on PDFs:** OpenCV's `QRCodeDetector` is invoked directly on the PDF file path via `cv2.imread()`, which fails silently on PDF files and falls back to regex.
4. **Regulatory Rules Hardcoding vs YAML:** While `rules_aph_2025_2026.yaml` declares versioned rules (including Land Area norms `APH-2026-LAND-03` and Faculty-to-Student Ratio `APH-2026-FSR-05`), the backend orchestrator **hardcodes 8 specific procedural checks** and ignores the YAML land and faculty rules entirely.
5. **No Backend Approval Gating:** The officer decision endpoint (`POST /api/applications/{id}/decision`) allows an officer to mark an application as `APPROVED` even when mandatory documents are missing or critical discrepancy findings remain unresolved.
6. **Simulated Authority Adapters:** All external authority verification (Municipal Fire NOCs, Town Planning Building Plans, University Affiliations, Environmental Clearances) runs against a hardcoded in-memory Python dictionary (`SIMULATED_AUTHORITY_REGISTRY`). No live or sandboxed government portal APIs are connected.
7. **Security & Session Vulnerability:** Authentication is simulated via unverified HTTP headers (`X-User-Role`, `X-User-Id`). If headers are omitted, the backend defaults to granting full **OFFICER** privileges to any caller. No cryptographic tokens or passwords exist.
8. **Audit Verification Payload Gap:** The audit integrity verification endpoint (`GET /api/audit/verify-chain`) only checks pointer equality (`previous_hash == last_event.event_hash`). It does not recompute payload hashes, because the microsecond ISO timestamp used during hash generation is not stored as a distinct column in SQLite.

---

## 2. Requirement Traceability Matrix (RTM)

### Classification Categories
- **[VERIFIED]** — Implemented in code and verified with passing reproducible tests.
- **[INSUFFICIENT_TEST]** — Implemented in code, but existing tests do not adequately exercise edge cases or negative paths.
- **[PARTIAL]** — Substantially implemented, but missing critical sub-components or full workflow integration.
- **[MISSING]** — Required by the problem statement or claimed in documentation, but absent from actual code.
- **[BLOCKED]** — Dependent on external government/agency infrastructure not accessible in the hackathon sandbox.
- **[N/A_PROTOTYPE]** — Expected in full enterprise production, but intentionally synthetic in the local prototype.

| Req ID | Requirement Description | Relevant Source Files & Endpoints | Existing Tests | Actual Test Result | Remaining Gap | Recommended Next Step | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-01** | Application Intake & Category Checklist | `backend/app/api/applications.py`, `backend/app/rules/rules_aph_2025_2026.yaml`, `frontend/src/components/ApplicationIntake.tsx` | `test_applications.py::test_create_and_list_application` | **PASSED (0.05s)** | Only static mandatory documents checked; conditional documents (Minority, PWD) are ignored. | Evaluate conditional requirements dynamically based on declared flags. | **[PARTIAL]** |
| **REQ-02** | Secure Document Storage Vault | `backend/app/services/storage.py`, `POST /api/applications/{id}/documents` | `test_documents.py::test_invalid_file_upload`, `test_valid_pdf_upload_and_duplicate_detection` | **PASSED (0.28s)** | Validates extension and size, but lacks magic byte inspection; entire file read into RAM at once. | Add `python-magic` or header byte checks; stream uploads to disk in 64KB chunks. | **[VERIFIED]** |
| **REQ-03** | PyMuPDF Vector Text & Geometry Extraction | `backend/app/services/document_parser.py` | `test_documents.py::test_valid_pdf_upload_and_duplicate_detection` | **PASSED (0.28s)** | Extracts raw page text and character count. Geometry bounding boxes are not extracted (`bounding_box = None`). | Store bounding boxes `(x0, y0, x1, y1)` for extracted entities in `extracted_fields`. | **[PARTIAL]** |
| **REQ-04** | OCR Fallback for Scanned PDF Pages | `backend/app/services/document_parser.py` | None | **NOT VERIFIED** | When PDF text `< 30` chars, sets `ocr_needed=True` and `extraction_method="OCR_TESSERACT"`, but **never rasterizes PDF pages to pixmaps or calls pytesseract**. Text remains empty. | Use `page.get_pixmap()` to render PDF pages to PIL images and invoke `pytesseract.image_to_string()`. | **[PARTIAL]** |
| **REQ-05** | Structured Entity Extraction (Regex) | `backend/app/services/document_parser.py` | `test_documents.py` | **PASSED (0.28s)** | Extracts only 4 scalar fields: `intake_capacity`, `land_area`, `expiry_date`, `certificate_number`. No table parsing. | Add layout-aware entity extractors or table parser for structured tabular data. | **[PARTIAL]** |
| **REQ-06** | Table Extraction from Statutory PDFs | None (`document_parser.py` regex only) | None | **NOT APPLICABLE** | No table parsing library (`pdfplumber`, `camelot`, `tabula`) installed or invoked. | Integrate `pdfplumber` to extract academic cadre rosters and course intake tables. | **[MISSING]** |
| **REQ-07** | Cross-Record Reconciliation (Intake) | `backend/app/services/orchestrator.py` (Check 2), `baseline_service.py` | `test_verification.py::test_synthetic_intake_mismatch_verification` | **PASSED (0.34s)** | Accurately flags `APH-2026-INTAKE-04` when declared intake (120) exceeds baseline (60). | Expand baseline records beyond intake to include land area, address, and sanctioned courses. | **[VERIFIED]** |
| **REQ-08** | Cross-Document Land Area Reconciliation | Claimed in `PRODUCTION_READINESS_AUDIT.md`, absent in `orchestrator.py` | None | **NOT APPLICABLE** | `orchestrator.py` does not compare land area across Title Deed vs Building Plan vs declared land. | Add Check 9 in orchestrator comparing `declared_land_acres` against extracted `land_area`. | **[MISSING]** |
| **REQ-09** | Exact SHA-256 Duplicate File Detection | `backend/app/services/storage.py`, `orchestrator.py` (Check 4) | `test_documents.py::test_valid_pdf_upload_and_duplicate_detection` | **PASSED (0.28s)** | Detects duplicate hashes across document slots; flags `APH-INTEGRITY-DUP-01` (`CRITICAL`). | Fully working. | **[VERIFIED]** |
| **REQ-10** | Perceptual Image Hash Reuse (`pHash`) | `backend/app/services/anomaly_service.py`, `orchestrator.py` (Check 5) | `test_detectors_demo.py::test_phash_tampering_and_duplicates` | **PASSED (0.24s)** | Computes 64-bit DCT perceptual hash on images; flags photo reuse when Hamming distance `<= 5`. | Extract embedded photos from PDF page image streams, not only standalone JPG/PNG uploads. | **[VERIFIED]** |
| **REQ-11** | PDF Incremental Update & Tamper Anomaly | `backend/app/services/anomaly_service.py`, `orchestrator.py` (Check 8) | `test_detectors_demo.py::test_phash_tampering_and_duplicates` | **PASSED (0.24s)** | Counts `%%EOF` markers; flags `APH-INTEGRITY-PDF-MOD` when markers `> 2`. | Correlate `ModDate` vs `CreationDate` in metadata for additional tamper confirmation. | **[VERIFIED]** |
| **REQ-12** | 2D QR Code Decoding | `backend/app/services/authority_verification.py` (`decode_qr_code_from_image`) | `test_detectors_demo.py::test_phash_tampering_and_duplicates` | **PASSED (0.24s)** | Works on standalone image files via OpenCV. **Fails on PDF files** because `cv2.imread()` cannot load PDF paths. | Extract image streams from PDF via PyMuPDF before passing to OpenCV QR detector. | **[PARTIAL]** |
| **REQ-13** | Cryptographic Digital Signature Verification | None | None | **NOT APPLICABLE** | PKCS#7 / PAdES / e-Sign certificate validation is completely absent. | Integrate `pyHanko` or PyMuPDF `doc.get_sigflags()` to verify cryptographic signatures. | **[MISSING]** |
| **REQ-14** | Mock Authority Verification (8 Outcomes) | `backend/app/services/authority_verification.py`, `orchestrator.py` (Check 6) | `test_authority_verification_scenarios.py` (8 tests) | **8/8 PASSED (0.42s)** | Validates Scenarios A–G (Verified, Record Not Found, Location Mismatch, Entity Mismatch, Invalid Status, Expired, Authority Unavailable, Extraction Incomplete). | Production requires live mTLS DigiLocker / municipal API gateways; currently synthetic in-memory. | **[BLOCKED]** / **[VERIFIED (MOCK)]** |
| **REQ-15** | Versioned Regulatory Rules Engine | `backend/app/rules/rules_aph_2025_2026.yaml`, `compliance_rules.py` | `test_integration_and_pipeline.py::test_compliance_engine_loading` | **PASSED (0.12s)** | YAML loader works and returns category metadata. Orchestrator hardcodes checks rather than evaluating YAML rules dynamically. | Build dynamic YAML AST evaluator so rules like `APH-2026-LAND-03` run automatically. | **[PARTIAL]** |
| **REQ-16** | Infrastructure Photo Resolution Review | `backend/app/services/infrastructure_review.py` | None | **NOT VERIFIED** | Function `review_infrastructure_evidence` exists, but is **never called in orchestrator or API routes**. | Wire `review_infrastructure_evidence` into `orchestrator.py` under a dedicated infrastructure check. | **[PARTIAL]** |
| **REQ-17** | Structured Findings & Evidence Linking | `Finding` model, `ApplicationDetails.tsx` | `test_verification.py`, `test_officer_alerts_workflow.py` | **PASSED (0.35s)** | Stores expected vs observed values, severity, rule code, and supporting page number. | Add bounding-box coordinates for visual highlighting in the document viewer. | **[VERIFIED]** |
| **REQ-18** | In-App Document Inspection Viewer | `frontend/src/components/DocumentViewerModal.tsx`, `GET /api/documents/{id}/stream` | Manual UI verification, Frontend Build | **PASSED (Vite Build 0 errors)** | Streams PDF directly with `#page=N` deep-linking and image zoom controls (60%–200%). | Add canvas overlay for bounding box highlight polygons. | **[VERIFIED]** |
| **REQ-19** | Deficiency Notice Issuance Workflow | `backend/app/api/applications.py`, `DeficiencyNoticeModal.tsx` | `test_officer_alerts_workflow.py::test_issue_deficiency_notice_and_alerts` | **PASSED (0.18s)** | Transitions status to `DEFICIENCY_COMMUNICATED`, updates findings to `DEFICIENCY_PENDING`, records audit event. | Fully working. | **[VERIFIED]** |
| **REQ-20** | Replacement Document Upload & Re-Scrutiny | `backend/app/api/documents.py`, `orchestrator.py` | `test_portal_integration_end_to_end_and_idempotency` | **PASSED (0.38s)** | Archives previous document (`REPLACED_ARCHIVED`), ingests replacement, re-executes automated scrutiny run. | Fully working. | **[VERIFIED]** |
| **REQ-21** | Officer Final Decision Recording | `backend/app/api/decision.py`, `FinalDecisionModal.tsx` | `test_actions_audit.py::test_reviewer_action_and_hash_chained_audit` | **PASSED (0.22s)** | Records decision (`RECOMMEND_APPROVAL`, `RECOMMEND_REJECTION`) with mandatory written justification (min 10 chars). | Backend lacks gating to prevent approving applications with unresolved critical findings. | **[PARTIAL]** |
| **REQ-22** | Cryptographic Hash-Chained Audit Trail | `AuditEvent` model, `backend/app/api/audit.py` | `test_actions_audit.py::test_reviewer_action_and_hash_chained_audit` | **PASSED (0.22s)** | SHA-256 chains every event. `/api/audit/verify-chain` verifies continuity. | Verify endpoint only checks `previous_hash` pointer, not payload hash recomputation. | **[PARTIAL]** |
| **REQ-23** | Priority Alerts & FIFO Application Queue | `backend/app/api/alerts.py`, `DashboardOverview.tsx` | `test_officer_alerts_workflow.py` | **PASSED (0.18s)** | Chronological oldest-first FIFO queue. Plain-English status and separate Next Action column. | Fully working. | **[VERIFIED]** |
| **REQ-24** | Ready for Approval Gating Queue | `DashboardOverview.tsx`, `Sidebar.tsx` | Frontend Build | **PASSED (Vite Build 0 errors)** | Filters applications where mandatory docs exist, scrutiny is complete, and no active findings remain. | Backend does not enforce this gating before allowing `POST /applications/{id}/decision`. | **[PARTIAL]** |
| **REQ-25** | Portal Integration API & Idempotency | `backend/app/api/integration.py`, `PortalSimulator.tsx` | `test_integration_and_pipeline.py::test_portal_integration_end_to_end_and_idempotency` | **PASSED (0.38s)** | Validates `X-Integration-Key`, deduplicates repeated submissions via `X-Idempotency-Key`. | Fully working. | **[VERIFIED]** |
| **REQ-26** | Role-Based Access Control (RBAC) | `backend/app/api/auth.py` | `test_workflow_and_rbac.py` (5 tests) | **5/5 PASSED (0.25s)** | Enforces permissions for APPLICANT, OFFICER, APPROVER, ADMIN. APPLICANT restricted to own institution. | Auth is simulated via unverified HTTP headers (`X-User-Role`); no passwords or JWT tokens. | **[PARTIAL]** |
| **REQ-27** | Empirical Benchmarking & Metrics | `backend/scripts/benchmark_eval.py`, `BenchmarkViewer.tsx` | `test_health.py::test_benchmark_endpoint`, execution of `benchmark_eval.py` | **PASSED (P=0.714, R=1.0, F1=0.833)** | Measures Precision, Recall, F1, Confusion Matrix, and Scrutiny Latency against synthetic fixtures. | Ground-truth dataset has only 5 fixtures; script writes to dev database rather than test database. | **[PARTIAL]** |
| **REQ-28** | Institutional Design & Branding | `frontend/src/*`, `Header.tsx`, `Sidebar.tsx` | Frontend Build (`npm run build`) | **PASSED (Vite Build 0 errors)** | AICTE-Drishti branding, "Officer" display identity, navy/slate theme, 3 horizontal category tabs. | Fully working. | **[VERIFIED]** |

---

## 3. Verified Working Functionality

The following systems have been verified through automated pytest runs, script executions, and production frontend compilation:

1. **Application Intake & Idempotent Submission (`POST /api/applications`, `/api/integration/v1/applications`):**
   - Correctly creates institutional applications with unique reference numbers (`APP-2026-XXXXXX`) and tracking IDs (`TRK-XXXXXXXXXXXX`).
   - Safely ignores duplicate requests bearing the same `X-Idempotency-Key`, returning the cached application response without inserting redundant database records.
2. **Deterministic Baseline Intake Reconciler (Check 2):**
   - Automatically compares declared intake capacity (e.g. 120 seats) against the synthetic ground-truth baseline (60 seats).
   - Generates high-severity finding `APH-2026-INTAKE-04` with expected value (60) vs observed value (120).
3. **Cryptographic Binary Duplicate Detection (Check 4):**
   - Computes SHA-256 checksums immediately upon document upload into the isolated vault (`vault/documents/{app_id}/`).
   - Automatically detects identical files uploaded across different statutory document slots and generates critical finding `APH-INTEGRITY-DUP-01`.
4. **Perceptual Image Hash Reuse (`pHash`, Check 5):**
   - Computes 64-bit DCT perceptual hashes using `imagehash.phash()` on laboratory/campus photographs.
   - Detects reused photographs across distinct slots (e.g., Computer Lab photo reused for Mechanical Workshop) using Hamming distance `<= 5`.
5. **PDF Incremental Update & Tamper Detection (Check 8):**
   - Scans raw byte streams for `%%EOF` trailer markers.
   - Accurately flags suspicious post-issuance append modifications (`%%EOF > 2`) as `POTENTIAL_ANOMALY` without making unsupported accusations of fraud.
6. **Comprehensive Synthetic External Authority Registry (Check 6):**
   - Supports 8 granular verification outcomes across Scenarios A through G:
     - `VERIFIED` (Matching approval ref, institution, and location)
     - `RECORD_NOT_FOUND` (Unindexed reference)
     - `LOCATION_MISMATCH` (Approved at Hadapsar instead of Kothrud)
     - `ENTITY_MISMATCH` (Issued to different educational trust)
     - `STATUS_INVALID` (Registry status is `REVOKED` or `REJECTED`)
     - `EXPIRED` (Certificate validity date in the past)
     - `AUTHORITY_UNAVAILABLE` (Simulated HTTP 504 Gateway Timeout)
     - `EXTRACTION_INCOMPLETE` (Unreadable or missing certificate reference)
   - Prominently embeds disclosure: `SIMULATED EXTERNAL CHECK — SYNTHETIC DATA`.
7. **Document Viewer with Page-Specific Deep Linking:**
   - [DocumentViewerModal.tsx](file:///d:/VerifyAI/frontend/src/components/DocumentViewerModal.tsx) streams files authenticated via `/api/documents/{id}/stream` and automatically opens PDFs to `#page=N` based on finding metadata.
8. **Document Replacement & Targeted Re-Scrutiny:**
   - Uploading a replacement file archives the previous document (`status = 'REPLACED_ARCHIVED'`), unlinks previous findings, and automatically executes a fresh scrutiny pass (`trigger_source = 'RECTIFICATION_UPLOAD'`).
9. **FIFO Chronological Queue & Officer Workload Dashboard:**
   - Applications are displayed in strict chronological submission order (oldest first / FIFO), eliminating arbitrary fraud scores or priority rankings.
   - Statuses are translated into plain-language institutional categories: *Ready for review*, *Awaiting documents*, *Changes requested*, *Under scrutiny*, *Approved*, and *Rejected*.
10. **Horizontal Request Types Navigation:**
    - Exactly 3 categories (`INCREASE_INTAKE`, `NEW_INSTITUTE`, `EXTENSION_APPROVAL`) displayed in a single horizontal row, with details expanding cleanly below.
11. **Institutional Theme & Identity Alignment:**
    - All visible instances renamed to **AICTE-Drishti**.
    - Officer identity standardized to **Officer** across sidebar profile, header, session badge, profile switch menu, dashboard greeting, and statutory footer: *"AI flags and explains. The authorised officer decides."*

---

## 4. Partially Implemented and Missing Functionality

### 4.1 Scanned PDF OCR Fallback (Area B) — PARTIAL
- **Existing Implementation:** In [backend/app/services/document_parser.py](file:///d:/VerifyAI/backend/app/services/document_parser.py#L71-L79), when extracted text length is `< 30` characters, the code sets:
  ```python
  if len(extracted_text.strip()) < 30:
      ocr_needed = True
      if TESSERACT_AVAILABLE:
          extraction_method = "OCR_TESSERACT"
          ocr_performed = True
  ```
- **Actual Gap:** The code **never rasterizes PDF pages to images or calls `pytesseract` on the PDF**. It merely sets the string flag `ocr_performed = True` while `extracted_text` remains empty. Tesseract is only executed on standalone image files (`image/png`, `image/jpeg`).
- **Impact:** Scanned PDF certificates produce no extracted text and cannot match baseline or authority records.

### 4.2 Table & Cadre Roster Extraction (Area B) — MISSING
- **Actual Gap:** No table parsing library (`pdfplumber`, `camelot`, `tabula`) is present in `requirements.txt` or code. Regex extractors only look for 4 scalar values.
- **Impact:** Detailed faculty rosters, student-cadre ratios, and course-wise intake matrices cannot be parsed from multi-column tables.

### 4.3 QR Code Extraction on PDF Files (Area D) — PARTIAL
- **Existing Implementation:** In [backend/app/services/authority_verification.py](file:///d:/VerifyAI/backend/app/services/authority_verification.py#L157-L175), `decode_qr_code_from_image` calls `cv2.imread(image_path)`.
- **Actual Gap:** In [backend/app/services/orchestrator.py](file:///d:/VerifyAI/backend/app/services/orchestrator.py#L360), `decode_qr_code_from_image(doc.storage_path)` is passed the storage path of a PDF file. `cv2.imread()` fails on PDF files, returning `None`. QR decoding only works on raw JPG/PNG uploads.
- **Impact:** QR codes embedded on official PDF approval letters are never decoded; the system falls back to regex matching.

### 4.4 Cryptographic Digital Signature Verification (Area D) — MISSING
- **Actual Gap:** No PKCS#7, PAdES, or X.509 digital signature validation logic exists.
- **Impact:** Digitally signed government PDFs (e.g. DSC-signed Fire NOCs) cannot be validated cryptographically.

### 4.5 Cross-Document Land Area Reconciliation (Area C) — MISSING
- **Actual Gap:** `PRODUCTION_READINESS_AUDIT.md` previously claimed land reconciliation between Land Deeds and Building Plans was working. Inspection of `orchestrator.py` reveals that **no land area cross-document comparison check exists**. The only baseline check in `orchestrator.py` is for intake capacity.

### 4.6 YAML Compliance Rules vs Orchestrator Hardcoding (Area F) — PARTIAL
- **Existing Implementation:** `backend/app/rules/rules_aph_2025_2026.yaml` declares version `2025-2026.v1` with rules for Land Norms (`APH-2026-LAND-03`) and Faculty-to-Student Ratio (`APH-2026-FSR-05`).
- **Actual Gap:** The orchestrator in `backend/app/services/orchestrator.py` **does not execute rules dynamically from YAML**. It hardcodes 8 procedural checks. `APH-2026-LAND-03` and `APH-2026-FSR-05` are completely ignored and never evaluated during scrutiny.
- **Impact:** Compliance rules defined in YAML cannot be updated or added without modifying backend Python code.

### 4.7 Infrastructure Evidence Review (Area G) — PARTIAL
- **Actual Gap:** In [backend/app/services/infrastructure_review.py](file:///d:/VerifyAI/backend/app/services/infrastructure_review.py#L4), `review_infrastructure_evidence` (which checks image resolution `>= 600x400`) is defined but **is never called in `orchestrator.py` or any API router**.
- **Impact:** Uploading an illegible or 100x100 thumbnail infrastructure photo does not generate a scrutiny finding.

### 4.8 Backend Decision Gating & State Machine (Area I) — PARTIAL
- **Actual Gap:** In [backend/app/api/decision.py](file:///d:/VerifyAI/backend/app/api/decision.py#L48-L54), `record_final_decision` allows an officer to record `RECOMMEND_APPROVAL` on any application regardless of unresolved critical findings or missing documents. Furthermore, finalized applications (`APPROVED`, `REJECTED`) can be repeatedly re-decided.
- **Impact:** The backend does not enforce the business rule that approvals require zero unresolved critical deficiencies.

---

## 5. Critical Security and Data-Integrity Blockers

> [!CAUTION]
> The following vulnerabilities prevent the current codebase from being deployed to any multi-user or network-accessible environment.

### 5.1 Simulated Header-Based Authentication & Spoofing
- **Vulnerability:** In [backend/app/api/auth.py](file:///d:/VerifyAI/backend/app/api/auth.py#L18-L45), user identity and role are extracted directly from client HTTP request headers (`X-User-Role`, `X-User-Id`).
- **Risk:** Any client can bypass all access controls by sending `X-User-Role: ADMIN`. Furthermore, if headers are omitted, line 28 defaults to `username = "officer1"` and `role = "OFFICER"`, meaning unauthenticated HTTP requests automatically inherit full Scrutiny Officer privileges.
- **Required Fix:** Replace header-based identity resolution with signed JWT bearer tokens (`Authorization: Bearer <token>`) validated against secure password hashes.

### 5.2 Extension-Only File Validation (MIME Spoofing)
- **Vulnerability:** In [backend/app/services/storage.py](file:///d:/VerifyAI/backend/app/services/storage.py#L33-L40), file validation checks `ext in valid_extensions`.
- **Risk:** An attacker can upload an executable (`malicious.exe`) renamed as `malicious.pdf`. Because magic bytes (`%PDF-`) are not inspected, the file is saved into the storage vault.
- **Required Fix:** Use `python-magic` or inspect binary file headers (`%PDF-1.`, `\x89PNG`, `\xFF\xD8\xFF`) before writing files to disk.

### 5.3 Memory Exhaustion (DoS) on File Ingestion
- **Vulnerability:** In `storage.py` line 18, `file.file.read()` reads the entire file into server RAM at once.
- **Risk:** Multiple concurrent 25 MB uploads will cause high memory pressure and potential Out-Of-Memory (OOM) crashes in memory-constrained environments.
- **Required Fix:** Stream files in 64 KB chunks directly to disk and calculate SHA-256 incrementally.

### 5.4 Audit Hash-Chain Verification Payload Bypass
- **Vulnerability:** In [backend/app/api/audit.py](file:///d:/VerifyAI/backend/app/api/audit.py#L43-L53), `verify_hash_chain_integrity` only checks:
  ```python
  if e.previous_hash != prev_hash:
      return {"status": "TAMPER_DETECTED"}
  prev_hash = e.event_hash
  ```
- **Risk:** It does **not** re-calculate `SHA256(prev_hash + event_type + details_json + actor + timestamp)`. If a malicious actor alters `details_json` directly in the database without changing `previous_hash` or `event_hash`, `/api/audit/verify-chain` reports `VALID`.
- **Root Cause:** The `now_iso` timestamp used in `AuditEvent.create_chained` is not stored as an exact string column in the database; `created_at` is a SQLAlchemy `DateTime` object that loses microsecond string formatting.
- **Required Fix:** Persist `timestamp_iso` as a dedicated column in `audit_events` and recompute the full payload hash during chain verification.

### 5.5 Shared SQLite Database Concurrency & Benchmark Pollution
- **Vulnerability:** Both `backend/scripts/benchmark_eval.py` and `backend/scripts/verify_end_to_end_demo.py` import `from app.database import SessionLocal` and execute operations directly against the active development database `backend/verifyai.db`.
- **Risk:** Running benchmark scripts inserts hundreds of synthetic benchmark records (`BENCH-...`, `APP-2026-...`) into the primary application database, distorting dashboard metrics and risking SQLite write lock contention (`database is locked`).
- **Required Fix:** Configure scripts to run against in-memory SQLite (`sqlite:///:memory:`) or dedicated ephemeral database fixtures.

---

## 6. External Integrations That Remain Simulated

The following external integrations are strictly simulated through mock adapters and synthetic databases:

| External System | Statutory Regulatory Purpose | Current Prototype Implementation | Missing Production Requirements |
| :--- | :--- | :--- | :--- |
| **DigiLocker API** | Issuing authority document verification & e-Sign validation | Simulated via local storage vault and mock reference lookups | Production API credentials, OAuth2 token exchange, and XML payload parser |
| **State Fire Services Gateway** | Verification of Fire Safety NOCs and tenure validity | Simulated in-memory dictionary (`SIMULATED_AUTHORITY_REGISTRY["FS-..."]`) | State citizen portal REST APIs, mTLS bilateral certificates, and webhook listeners |
| **Municipal Town Planning Portal** | Verification of Building Plans and sanctioned built-up area | Simulated in-memory dictionary (`SIMULATED_AUTHORITY_REGISTRY["BP-..."]`) | Municipal corporation GIS / Town Planning department API integration |
| **State Affiliating University Portal** | Verification of university affiliation orders and approved branches | Simulated in-memory dictionary (`SIMULATED_AUTHORITY_REGISTRY["UNIV-..."]`) | University examination board registry API integration |
| **State Environmental Clearance (SEIAA)** | Verification of environmental clearances for large campuses | Simulated in-memory dictionary (`SIMULATED_AUTHORITY_REGISTRY["ENV-..."]`) | Ministry of Environment PARIVESH portal integration |
| **State Land Revenue Registry** | Verification of Khasra/Survey numbers, title deeds, and non-agricultural conversion orders | Not implemented; regex extracts land area only | State Bhoomi / Bhulekh Land Records API integration |
| **Central AICTE Core Approval Portal** | Master institutional database and regional committee approvals | Local REST adapter (`/api/integration/v1/...`) with pre-shared API key | Central AICTE Oracle/PostgreSQL database connector and queue (Kafka/RabbitMQ) |

---

## 7. Regulatory Requirements That Remain Unconfirmed

Because no local official AICTE Approval Process Handbook (APH) PDF or authoritative clause database is provided in the repository, the following regulatory parameters remain placeholders:

1. **Handbook Clause Suffixes:**
   - All rule codes generated in findings carry the disclaimer: `[PLACEHOLDER PENDING HANDBOOK MAPPING]` (e.g., `APH-2026-MANDATORY-DOCS-01`, `APH-2026-INTAKE-04`, `APH-2026-NOC-FIRE-02`).
2. **Campus Land Norm Thresholds:**
   - YAML declares 7.50 acres for Rural and 2.50 acres for Urban (`APH-2026-LAND-03`), but these values are not verified against official 2026 Gazette notifications and are not evaluated by the orchestrator.
3. **Faculty-to-Student Ratio (FSR):**
   - Norm of 1:15 vs 1:20 is declared in YAML (`APH-2026-FSR-05`), but course-specific ratios (e.g. Pharmacy 1:15, Architecture 1:10, Management 1:20) are not mapped.
4. **Instructional Built-Up Area Norms:**
   - Calculations for carpet area per student, laboratory square meter requirements, and administrative space norms are not implemented.
5. **Cadre Ratio Norms:**
   - The statutory cadre ratio (1 Professor : 2 Associate Professors : 6 Assistant Professors) is declared in document checklists, but not evaluated against faculty roster submissions.

---

## 8. Test and Build Results with Commands

### 8.1 Backend Automated Test Suite (`pytest`)
- **Command:** `d:\VerifyAI\backend\.venv\Scripts\pytest.exe backend/tests -v`
- **Execution Date:** 28 October 2026, 22:28 IST
- **Result:** **27 passed, 3 warnings in 2.87s (100% Pass Rate)**
- **Breakdown by Test Module:**
  - `test_actions_audit.py`: 1 test passed (Reviewer actions and audit trail)
  - `test_applications.py`: 1 test passed (Application creation and queue listing)
  - `test_authority_verification_scenarios.py`: 8 tests passed (Scenarios A through G mock verification)
  - `test_detectors_demo.py`: 3 tests passed (Duplicate SHA-256, pHash photo reuse, PDF tampering)
  - `test_documents.py`: 2 tests passed (File size limits and valid PDF ingestion)
  - `test_health.py`: 2 tests passed (Health and benchmark endpoints)
  - `test_integration_and_pipeline.py`: 3 tests passed (Portal adapter, idempotency, rule engine)
  - `test_officer_alerts_workflow.py`: 1 test passed (Deficiency notices and priority alerts)
  - `test_verification.py`: 1 test passed (Baseline intake discrepancy 120 vs 60)
  - `test_workflow_and_rbac.py`: 5 tests passed (RBAC enforcement and institutional isolation)

### 8.2 Frontend Production Build (`tsc && vite build`)
- **Command:** `npm --prefix frontend run build`
- **Execution Date:** 28 October 2026, 22:28 IST
- **Result:** **Exited with code 0 (0 compilation errors, 0 warnings)**
- **Output Artifacts:**
  - `dist/index.html`: 1.13 kB (gzip: 0.64 kB)
  - `dist/assets/index-CqitrlBm.css`: 43.70 kB (gzip: 7.71 kB)
  - `dist/assets/index-C0d3Clgh.js`: 346.16 kB (gzip: 86.41 kB)
  - Transformation: 1,584 modules transformed in 3.19s.

### 8.3 10-Step End-to-End Scrutiny Demo Script
- **Command:** `d:\VerifyAI\backend\.venv\Scripts\python.exe backend/scripts/verify_end_to_end_demo.py`
- **Result:** **All 10 steps passed with zero errors.**
  - Step 1: Intake application created (`APP-2026-...`)
  - Step 2: Intake baseline mismatch flagged (120 vs 60)
  - Step 3: Expired Fire NOC uploaded & flagged
  - Step 4: Duplicate Building Plan uploaded & flagged (`CRITICAL`)
  - Step 5: Affiliation letter with institution name variation uploaded & verified (fuzzy match)
  - Step 6: Tampered PDF uploaded & flagged (`%%EOF > 2`)
  - Step 7: Reused Lab photo uploaded & flagged via pHash (Hamming distance `<= 5`)
  - Step 8: Priority alerts generated & acknowledged
  - Step 9: Deficiency notice issued & valid replacement NOC uploaded (triggering automated re-scrutiny)
  - Step 10: Final statutory approval recorded with mandatory written justification

### 8.4 Empirical Benchmark Evaluation Script
- **Command:** `$env:PYTHONPATH="backend"; d:\VerifyAI\backend\.venv\Scripts\python.exe backend/scripts/benchmark_eval.py`
- **Result:** **Execution completed successfully.**
  - **Dataset:** 5 synthetic ground-truth defect fixtures
  - **Precision:** `0.7143` (5 True Positives, 2 False Positives: `APH-AUTH-VERIF-BUILDING_PLAN`, `APH-AUTH-VERIF-FIRE_SAFETY_NOC`)
  - **Recall:** `1.0000` (5 True Positives, 0 False Negatives)
  - **F1 Score:** `0.8333`
  - **Scrutiny Pipeline Latency:** Average `68.81 ms` (p50: `42.82 ms`, p95: `164.66 ms`)
  - **Throughput Acceleration vs Manual 45-minute Baseline:** `~39,235x`

---

## 9. Outdated Documentation and Branding Inconsistencies

During the audit, the following discrepancies between markdown documentation and the actual codebase were identified:

1. **`REQUIREMENTS_TRACEABILITY.md` (Line 14):**
   - *Claim:* "18-Step Scrutiny Orchestrator | Central scrutiny pipeline creating versioned ScrutinyRun".
   - *Reality:* `backend/app/services/orchestrator.py` executes exactly **8 scrutiny checks**, not 18.
2. **`REQUIREMENTS_TRACEABILITY.md` (Line 15):**
   - *Claim:* "Document Intelligence (PyMuPDF + OCR fallback) | PyMuPDF text & geometry extraction, OCR flag on < 30 chars".
   - *Reality:* While `ocr_needed` is flagged, Tesseract is never invoked on PDF pages; extracted text remains empty for scanned PDFs. Bounding box geometry is always `None`.
3. **`PRODUCTION_READINESS_AUDIT.md` (Line 348):**
   - *Claim:* "Cross-Document Correlation Engine (`orchestrator.py`): Logic reconciling Land Area across Land Registry deeds vs. Architect Certificates vs. Application intake declarations works well...".
   - *Reality:* No land area comparison logic exists in `orchestrator.py`.
4. **`TESTING_AND_EVALUATION.md` (Line 9-10):**
   - *Claim:* "Total Tests Collected: 10 | Total Tests Passed: 10 / 10".
   - *Reality:* The automated test suite has expanded to **27 tests** across 10 test files.
5. **`TESTING_AND_EVALUATION.md` (Line 118) & `BenchmarkViewer.tsx`:**
   - *Claim:* Hardcodes `verifyai_automated_scrutiny_seconds: 2.8` and `963.6x Throughput Acceleration`.
   - *Reality:* The actual benchmark run executes in `68.81 ms` on local synthetic files, yielding `~39,235x` throughput acceleration.
6. **`SIH_DEMO_READINESS.md` (Line 66-68):**
   - *Claim:* Mentions session card displays "AICTE Official".
   - *Reality:* Display name was updated to **"Officer"** across all UI views.

---

## 10. Prioritised Remediation Plan

### Priority P0: Mandatory Demonstration Safeguards (Immediate Pre-Demo)
1. **Enforce Backend Decision Gating (`backend/app/api/decision.py`):**
   - In `record_final_decision`, add a validation check preventing `RECOMMEND_APPROVAL` if unresolved `CRITICAL` findings (e.g., missing mandatory documents or duplicate files) exist on the application.
   - Prevent re-deciding applications that are already in `APPROVED` or `REJECTED` status.
2. **Activate Real PyMuPDF-to-Tesseract PDF OCR (`backend/app/services/document_parser.py`):**
   - When PDF extracted text length is `< 30` characters and Tesseract is available, iterate over the first 3 pages, render each page to a pixmap via `page.get_pixmap(dpi=150)`, convert to a PIL Image, and run `pytesseract.image_to_string()`.
3. **Fix PDF QR Code Decoding (`backend/app/services/authority_verification.py` & `orchestrator.py`):**
   - When a document is a PDF, render the first page to a pixmap, convert to a NumPy array (`cv2.cvtColor`), and pass the image buffer to `cv2.QRCodeDetector()`.
4. **Isolate Benchmark & Demo Script Databases:**
   - Update `benchmark_eval.py` to create and tear down a temporary test database rather than inserting test rows into the live `verifyai.db`.

### Priority P1: Integrity & Security Hardening (Post-Screening / Phase 2)
1. **Complete Cryptographic Hash-Chain Verification (`backend/app/api/audit.py`):**
   - Add a `timestamp_iso` string column to `audit_events`.
   - In `/api/audit/verify-chain`, recompute `SHA256(previous_hash + event_type + details_json + actor + timestamp_iso)` for every event to detect any direct database modifications.
2. **File Header Magic Byte Validation (`backend/app/services/storage.py`):**
   - Inspect leading bytes (`%PDF-`, `\x89PNG`, `\xFF\xD8\xFF`) to prevent file extension spoofing.
3. **Dynamic YAML Compliance Rule Execution:**
   - Implement an automated rule evaluator in `compliance_rules.py` that dynamically executes rules declared in `rules_aph_2025_2026.yaml` (such as `APH-2026-LAND-03` and `APH-2026-FSR-05`) instead of hardcoding checks in Python.
4. **Token-Based Authentication (JWT):**
   - Replace simulated `X-User-Role` headers with standard OAuth2 / JWT bearer tokens.

### Priority P2: Enterprise Production Readiness
1. **PostgreSQL Migration & Connection Pooling:**
   - Migrate from SQLite to PostgreSQL with PgBouncer connection pooling to eliminate file-locking bottlenecks.
2. **Table Extraction Engine:**
   - Integrate `pdfplumber` for automated tabular data extraction from faculty rosters and financial balance sheets.
3. **Bounding-Box Coordinate Extraction & UI Highlight Polygons:**
   - Extract page geometry bounding boxes during PyMuPDF parsing and display highlighted overlay boxes directly in `DocumentViewerModal.tsx`.
4. **mTLS Authority Integration:**
   - Replace in-memory authority dictionary with real bilateral mTLS client connections to state government and DigiLocker APIs.

