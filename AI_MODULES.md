# AICTE NIDHI — AI & Intelligence Modules Technical Specification

AICTE NIDHI integrates seven specialized intelligence and verification modules into a unified, automatic scrutiny pipeline. This document specifies the implementation details, libraries, deterministic heuristics, and operational boundaries of each module.

---

## Module 1: Document Intelligence Service
- **Source Code**: [`backend/app/services/document_parser.py`](file:///d:/VerifyAI/backend/app/services/document_parser.py)
- **Primary Library**: PyMuPDF (`fitz` v1.25+)
- **Fallback Engine**: Tesseract OCR (`pytesseract`)

### Capabilities
1. **High-Speed Digital Parsing**: PyMuPDF extracts text streams, page counts, and bounding box coordinates for each paragraph and table.
2. **Scanned Page Detection**: Calculates text density per page. Pages with `< 30 characters` are flagged as `ocr_needed=True`.
3. **Graceful OCR Fallback**: If Tesseract is unavailable on the host system, the service sets `ocr_engine_available=False` and flags the document for manual review rather than silently dropping or failing.
4. **Structured Field Extraction**: Extracts standard statutory attributes using compiled regex heuristics:
   - Land Area (Acres / Hectares / Sq. Meters / Sq. Feet)
   - Expiry & Issue Dates (`DD/MM/YYYY`, `YYYY-MM-DD`, `DD-Mon-YYYY`)
   - Certificate & Reference Numbers
   - Registered Institution Names

### Limitations
- Handwritten notes or unformatted stamps require manual inspection.
- OCR execution adds ~400–900ms per page depending on host CPU architecture.

---

## Module 2: Intelligent Validation Engine & Decision Gating
- **Source Code**: [`backend/app/services/orchestrator.py`](file:///d:/VerifyAI/backend/app/services/orchestrator.py), [`backend/app/services/baseline_service.py`](file:///d:/VerifyAI/backend/app/services/baseline_service.py), [`backend/app/api/decision.py`](file:///d:/VerifyAI/backend/app/api/decision.py)
- **Libraries**: Python Standard Library + `rapidfuzz`

### Capabilities
1. **Cross-Record Reconciliation**: Reconciles declared application fields with central statutory baseline records:
   - *Intake Check*: Declared intake capacity is compared against the preceding Academic Year's Extension of Approval (EoA). (e.g., Declared `120` vs Baseline `60` -> Flagged).
   - *Fuzzy Institution Name Alignment*: Uses `rapidfuzz.fuzz.token_sort_ratio` to compare extracted document titles with the AICTE registry title. Scores between `40%–85%` trigger `MANUAL_REVIEW` notices.
2. **Document Expiry & Validity**: Compares extracted validity dates against scrutiny baseline dates (e.g., `2026-03-31`). Expired certificates immediately produce high-severity findings.
3. **Mandatory Category Completeness**: Compares submitted document categories against the applicable category requirements defined in the active ruleset.
4. **Strict P0 Decision Gating**:
   - `RECOMMEND_APPROVAL` is strictly blocked (HTTP 422) if mandatory statutory attachments are missing or unresolved blocking findings exist.
   - Prevents an already approved or rejected application from being decided again without an explicit reopening workflow (`POST /api/applications/{id}/return-to-review`).
   - The system never auto-approves applications; human officer approval authority remains mandatory.

---

## Module 3: Anomaly & Potential Tampering Detection
- **Source Code**: [`backend/app/services/anomaly_service.py`](file:///d:/VerifyAI/backend/app/services/anomaly_service.py)
- **Libraries**: `hashlib`, `imagehash`, `fitz`

### Required Detectors Implemented
1. **Exact Duplicate Detection (SHA-256)**: Identifies identical binary files submitted across different slots or multiple institutions.
2. **Perceptual Image Hash Reuse (`imagehash.phash`)**: Computes 64-bit discrete cosine transform (DCT) hashes of uploaded photos. A Hamming distance `<= 4` flags visually identical photographs reused across distinct laboratory categories.
3. **PDF Metadata & Incremental Updates**: Scans binary PDF streams for multiple `%%EOF` markers and conflicting `CreationDate` vs `ModDate` timestamps. Detects post-issuance modifications that warrant officer inspection.
   - *Limitation & Truth in Advertising*: This check inspects trailer `%%EOF` counts and revision blocks. It detects structural post-export alterations, but does **not** validate cryptographic digital signatures (PKI / X.509 / PAdES).

### Non-Negotiable Operational Policy
- The system never uses generic "fraud risk percentages".
- A flag is always categorized as: `"Potential document anomaly detected — further verification required."`

---

## Module 4: Issuing-Authority Verification Adapter & QR Decoding
- **Source Code**: [`backend/app/services/authority_verification.py`](file:///d:/VerifyAI/backend/app/services/authority_verification.py)
- **Libraries**: `pymupdf` (`fitz`), `opencv-python-headless` (`cv2.QRCodeDetector`), `Pillow` (`PIL`), `json`, `re`, `urllib.parse`

### Capabilities Implemented
1. **In-Memory PDF QR Code Rendering & Decoding**: Renders PDF pages in-memory to pixmaps using PyMuPDF (scans up to first 3 pages at 150 DPI) and feeds them to OpenCV multi-pass detection (raw BGR, grayscale, Otsu thresholding). Does **not** pass raw PDF paths to `cv2.imread`.
2. **Image QR Decoding with Resolution Limits**: Direct QR decoding for uploaded image formats (PNG, JPG, TIFF) with resolution safeguards (automatically scales down if dimensions exceed 3000px).
3. **Structured Outcome & Audit Tracking**: Records `attempted: bool`, `found: bool`, `page_number: int`, `pages_scanned: int`, and descriptive `notes`. Missing or unreadable QR codes gracefully fall back to text extraction and are **never** automatically classified as fraud.
4. **URL & Reference Key Resolution**: Extracts certificate IDs from JSON payloads, statutory reference prefixes, URL path segments, or URL query parameters (`?cert=`, `?ref=`, `?id=`, `?approval_no=`).
5. **Simulated Issuing Authority Gateway**:
   - `VERIFIED`: Matching authority record, matching institution, matching location, active status.
   - `EXPIRED`: Registry confirms certificate was issued but validity period ended.
   - `STATUS_INVALID`: Registry marks approval as revoked or rejected.
   - `LOCATION_MISMATCH`: Property location differs from declared campus.
   - `ENTITY_MISMATCH`: Approval belongs to another institution in registry.
   - `RECORD_NOT_FOUND`: Reference not indexed in synthetic registry (explained without fraud accusation).
   - `EXTRACTION_INCOMPLETE`: Reference could not be legibly extracted (requests manual inspection).
   - `AUTHORITY_UNAVAILABLE`: Simulated external portal offline/timeout.
6. **Synthetic Ground-Truth Isolation & Disclosure**:
   - Prototype authority checks operate strictly against synthetic mock records (`SIMULATED_AUTHORITY_REGISTRY`).
   - Every verification result explicitly carries `[SIMULATED]` in `source_name` and `is_simulated = True`.
   - Never claims live government verification when using synthetic test data.

---

## Module 5: Configurable YAML Compliance Engine & Evaluator Registry
- **Source Code**: [`backend/app/services/compliance_rules.py`](file:///d:/VerifyAI/backend/app/services/compliance_rules.py)
- **Rules Configuration**: [`backend/app/rules/rules_aph_2025_2026.yaml`](file:///d:/VerifyAI/backend/app/rules/rules_aph_2025_2026.yaml)
- **Library**: `pyyaml`

### Capabilities
1. **Decoupled, Versioned Rulesets**: Scrutiny rules are stored in human-readable YAML configurations, decoupled from backend code.
2. **Dynamic Evaluator Registry**: Evaluates rules via registered evaluator functions (`MANDATORY_DOCUMENTS`, `FIRE_SAFETY_EXPIRY`, `CAMPUS_LAND_NORM`, `INTAKE_BASELINE_RECONCILIATION`, `FACULTY_STUDENT_RATIO`, `INSTITUTION_NAME_CONSISTENCY`, `CROSS_DOCUMENT_CONSISTENCY`, `INFRASTRUCTURE_PHOTO_REVIEW`).
3. **Graceful Fallback**: Any rule configured with an un-implemented or future evaluation method returns an explicit `NOT_EVALUATED` status without crashing the pipeline.
4. **Application Category Filtering**: Filters rules by application type (`INCREASE_INTAKE`, `NEW_INSTITUTE`, `EOA_REGULAR`).
5. **Compliance Transparency**: Every executed check records rule ID, ruleset version (`2025-2026.v1`), expected criterion, observed parameter, and severity.
6. **Mandatory Disclaimer Policy**: In accordance with project instructions, all unverified handbook rules are tagged with `[PLACEHOLDER PENDING HANDBOOK MAPPING]`.

---

## Module 6: Infrastructure Evidence Review & Expert Escalation (EVC)
- **Source Code**: [`backend/app/services/infrastructure_review.py`](file:///d:/VerifyAI/backend/app/services/infrastructure_review.py)
- **API Routes**: [`backend/app/api/findings.py`](file:///d:/VerifyAI/backend/app/api/findings.py)
- **Libraries**: `Pillow`, `imagehash`

### Capabilities
1. **Image Readability & Resolution Verification**: Verifies image dimensions against minimum clarity standards (>= 600x400 px). Low-resolution or unreadable images are flagged as `INSUFFICIENT_EVIDENCE`.
2. **Cross-Slot Reuse Detection**: Compares perceptual hashes across all uploaded campus photographs to prevent applicant reuse of a single photo across multiple laboratories.
3. **Expert Visit Committee (EVC) Escalation**:
   - Distinguishes between automated digital clarity inspection and mandatory on-site physical machinery verification.
   - Automated photo scrutiny does **not** fabricate building specifications or claim an on-site inspection occurred.
   - When automated checks detect low resolution, missing physical machinery evidence, or high-risk expansion requests, the system provides an explicit `RECOMMEND_EVC` / `ESCALATE_EVC` action.
   - Escalation creates a designated `EVC_ESCALATION` alert and updates finding review status to `EVC_RECOMMENDED`.

---

## Module 7: Cross-Document Consistency Engine
- **Source Code**: [`backend/app/services/cross_document_engine.py`](file:///d:/VerifyAI/backend/app/services/cross_document_engine.py)
- **Pipeline Integration**: Check 9 in [`backend/app/services/orchestrator.py`](file:///d:/VerifyAI/backend/app/services/orchestrator.py)
- **Libraries**: `rapidfuzz`, `re`

### Capabilities
1. **Multi-Source Statutory Reconciliation**: Compares institution declarations across multiple independent uploads:
   - **Land Area**: Reconciles Land Title Deed vs Building Plan vs declared application land.
   - **Unit Normalization & Tolerance**: Converts acres, hectares, square meters, and square feet to standardized acres with a surveying tolerance of $\pm 3\%$.
   - **Institution Legal Name**: Compares registered name across all submitted certificates and NOCs using token sort similarity.
   - **Geographic Location**: Validates token overlap between Land Title Deed and declared campus address.
   - **Sanctioned Intake**: Reconciles Affiliation Letter approved intake against declared intake.
2. **Categorized Outcomes**: Each check returns `MATCH`, `MISMATCH`, `NOT_ENOUGH_INFORMATION`, `NOT_APPLICABLE`, or `CHECK_FAILED`.
3. **Evidence Linking**: Mismatches serialize secondary document IDs and page references, allowing the in-app document viewer to open conflicting documents side-by-side with genuine extracted snippets.
