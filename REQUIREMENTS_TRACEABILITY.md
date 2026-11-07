# AICTE NIDHI — Requirements Traceability Matrix (RTM)

This document provides complete end-to-end traceability from the SIH 2026 Problem Statement requirements to backend services, API routes, data models, frontend components, and automated tests.

---

## Traceability Table

| # | Specific Prompt Requirement | Backend Implementation | Database Model / File | Frontend View | Verification Test | Status |
|---|---|---|---|---|---|---|
| **1** | **Preserve Existing Architecture & Stack** | FastAPI + SQLite + SQLAlchemy | `backend/app/main.py`, `backend/app/database.py` | React 18 + Vite + Tailwind CSS | `test_health.py` | **IMPLEMENTED** |
| **2** | **Portal Integration Adapter** | REST API (`/api/integration/v1/...`) with API key auth | `backend/app/api/integration.py` | `PortalSimulator.tsx` | `test_portal_integration_unauthorized`, `test_portal_integration_end_to_end_and_idempotency` | **IMPLEMENTED** |
| **3** | **Idempotent Application Submission** | `X-Idempotency-Key` tracking and deduplication | `Application.idempotency_key` | `PortalSimulator.tsx` (Regen token) | `test_portal_integration_end_to_end_and_idempotency` | **IMPLEMENTED** |
| **4** | **18-Step Scrutiny Orchestrator** | Central scrutiny pipeline creating versioned `ScrutinyRun` | `backend/app/services/orchestrator.py` | `ApplicationDetails.tsx` (Run selector) | `test_integration_and_pipeline.py` | **IMPLEMENTED** |
| **5** | **Document Intelligence (PyMuPDF + OCR fallback)** | PyMuPDF text & geometry extraction, OCR flag on `< 30` chars | `backend/app/services/document_parser.py` | `DocumentUploadArea.tsx` | `test_documents.py` | **IMPLEMENTED** |
| **6** | **Cross-Record Validation (Intake 120 vs 60)** | Compares application declared intake against baseline EoA record | `backend/app/services/baseline_service.py`, `orchestrator.py` | `FindingsPanel.tsx` | `test_synthetic_intake_mismatch_verification` | **IMPLEMENTED** |
| **7** | **SHA-256 Duplicate File Detection** | Binary hashing in secure vault ingest | `backend/app/services/storage.py`, `anomaly_service.py` | `DocumentUploadArea.tsx` (Duplicate badge) | `test_valid_pdf_upload_and_duplicate_detection` | **IMPLEMENTED** |
| **8** | **Perceptual Image Hash Reuse (`pHash`)** | 64-bit DCT perceptual hash for lab/campus photos | `backend/app/services/anomaly_service.py` | `FindingsPanel.tsx` (Photo reuse flag) | `benchmark_eval.py` | **IMPLEMENTED** |
| **9** | **PDF Metadata & Incremental Updates** | Scan for multiple `%%EOF` and ModDate discrepancies | `backend/app/services/anomaly_service.py` | `ApplicationDetails.tsx` (Metadata inspection) | `test_documents.py` | **IMPLEMENTED** |
| **10** | **Issuing-Authority Verification Adapter** | OpenCV 2D QR decoding + simulated authority registry lookup | `backend/app/services/authority_verification.py` | `ApplicationDetails.tsx` (Authority tab) | `test_verification.py` | **IMPLEMENTED** |
| **11** | **Configurable Versioned Compliance Rules** | Decoupled YAML ruleset (`rules_aph_2025_2026.yaml`) | `backend/app/services/compliance_rules.py` | `App.tsx` (APH Norms view) | `test_integration_and_pipeline.py` | **IMPLEMENTED** |
| **12** | **Infrastructure Evidence Review** | Image resolution check (>= 600x400) + slot reuse pHash | `backend/app/services/infrastructure_review.py` | `DocumentUploadArea.tsx` | `benchmark_eval.py` | **IMPLEMENTED** |
| **13** | **Common Evidence-Linked Finding Model** | Structured findings with rule code, severity, expected vs observed, snippet | `Finding` model in `backend/app/models/__init__.py` | `FindingsPanel.tsx` | `test_verification.py` | **IMPLEMENTED** |
| **14** | **Officer Portal Scrutiny Review** | Review runs, inspect documents, side-by-side snippet | `backend/app/api/applications.py`, `runs.py` | `ApplicationDetails.tsx` | `test_alerts_and_officer_decision` | **IMPLEMENTED** |
| **15** | **Officer Final Decision Recording** | Record decision with mandatory justification remarks (min 10 chars) | `backend/app/api/decision.py` | `ReviewerActionModal.tsx` | `test_alerts_and_officer_decision` | **IMPLEMENTED** |
| **16** | **Applicant Institution Portal** | View status, review deficiency requests, upload replacement file | `backend/app/api/documents.py`, `integration.py` | `ApplicantPortal.tsx` | `test_portal_integration_end_to_end_and_idempotency` | **IMPLEMENTED** |
| **17** | **Targeted Re-Scrutiny on Replacement** | Archiving previous document and re-running scrutiny pass | `backend/app/services/orchestrator.py` | `ApplicantPortal.tsx`, `PortalSimulator.tsx` | `test_portal_integration_end_to_end_and_idempotency` | **IMPLEMENTED** |
| **18** | **Cryptographic Hash-Chained Audit Trail** | SHA-256 hash-chained event log (`AuditEvent.create_chained`) | `AuditEvent` model in `backend/app/models/__init__.py` | `AuditTimeline.tsx` | `test_reviewer_action_and_hash_chained_audit` | **IMPLEMENTED** |
| **19** | **Real-Time Priority Alerts Queue** | High/Critical alerts with acknowledgement lifecycle | `backend/app/api/alerts.py` | `DashboardOverview.tsx` | `test_alerts_and_officer_decision` | **IMPLEMENTED** |
| **20** | **Empirical Evaluation & Benchmarking** | Measure Precision, Recall, F1, Confusion Matrix, Latency | `backend/scripts/benchmark_eval.py`, `app/api/evaluation.py` | `BenchmarkViewer.tsx` | `test_benchmark_endpoint` | **IMPLEMENTED** |

---

## Architectural Principles Traceability

1. **"The system flags and explains. The AICTE officer decides."**
   - *Backend*: System findings are marked as advisory (`evidence_classification="AUTOMATED_INFERENCE"` or `"POTENTIAL_ANOMALY"`). Final statutory approvals/rejections require manual invocation of `POST /api/applications/{id}/decision` by an authorized officer with mandatory written justification.
2. **"Never invent official AICTE rules or clause numbers."**
   - *Backend & Rules*: All rule codes in `backend/app/rules/rules_aph_2025_2026.yaml` are tagged with `[PLACEHOLDER PENDING HANDBOOK MAPPING]`.
3. **"Clearly distinguish real processing, synthetic records, and simulated integrations."**
   - *Frontend & API*: Badges prominently indicate `[SIMULATED]` for synthetic baseline lookups, and `DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION` across the Integration Simulator.
4. **"Do not generate fake benchmark results."**
   - *Backend*: Metrics in `backend/evaluation_results.json` and `/api/evaluation/benchmark` are computed via `time.perf_counter()` and statistical evaluation over real synthetic ground-truth test runs.
