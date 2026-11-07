# AICTE NIDHI — Security Deposit and FDR Management Portal
**All India Council for Technical Education · Regulation Bureau**

An institutional governance portal designed for authorized AICTE Regulation Bureau officers, regional directors, and institutional stakeholders to monitor, independently verify, and govern the lifecycle of statutory security deposits and Fixed Deposit Receipts (FDRs).

---

## 1. Core Mission & Guiding Principle
> **"Instrument records and verification findings support review. The authorised authority decides."**  
> Automated verification checks, OCR field extraction, and maturity calculations empower officers with complete visibility; they never execute unilateral adverse actions or releases without authorized officer sign-off.

---

## 2. Key Capabilities

### A. Dynamic Runtime Validity Monitoring
- **Decoupled State Machine**: Decouples contractual validity (`ACTIVE_VALID`, `EXPIRING_SOON`, `MATURED`, `UNKNOWN_INCOMPLETE`) from administrative lifecycle states (`DRAFT`, `SUBMITTED`, `PENDING_VERIFICATION`, `ACTIVE`, `RENEWAL_REQUIRED`, `RENEWAL_IN_PROGRESS`, `MATURED`, `RELEASE_REQUESTED`, `RELEASED`, `SUPERSEDED`, `ARCHIVED`).
- **Dynamic Calculation**: Remaining days and status are evaluated relative to runtime date (`today`), avoiding stale static database timestamps.
- **Configurable Warning Threshold**: Proactive 30-day early notification window for expiring instruments.

### B. Independent Multi-Tier Verification Engine
- **Cross-Document Discrepancy Checks**: Compares recorded metadata against OCR-extracted values from FDR receipts (Amount, Issuing Bank, FDR Number, Maturity Date).
- **Mandatory Attachment Checklist**: Enforces presence of essential statutory documents (FDR Receipt, Bank Joint Lien Letter, Joint Holdership Declaration).
- **Calendar & Mathematical Consistency**: Verifies date ordering (maturity date succeeding issue date) and tenure limits.
- **SHA-256 Duplicate Check**: Prevents identical physical certificates from being registered under multiple slots or institutions.
- **Simulated Core Banking Integration**: Simulates external bank confirmation gateways with clear `[SIMULATED]` prototype disclosures.

### C. Renewal & Replacement Instrument Linking
- **Continuity of Security**: When an FDR matures, the portal tracks renewal initiation and links the new replacement FDR to the original superseded instrument.
- **Parent-Child Linkage**: Full audit trail preserving the historical chain of custody across tenures.

### D. Release & Refund Governance
- **5-Point Statutory Clearance Checklist**:
  1. Completion of prescribed operational lock-in period (e.g. 8–10 years per APH norms)
  2. No pending AICTE regulatory inquiries or student fee grievances
  3. Annual compliance affidavits and audited balance sheets up to date
  4. In-principle recommendation from Regional Committee / Bureau Head
  5. Formal surrender of physical FDR and verified bank account mandate for refund
- **Two-Stage Decision Gating**: Officer review recommendation followed by Bureau Head final approval.

### E. Audit-Grade Reporting & CSV Data Export
- **Portfolio Analytics**: Aggregates total corpus value held under joint lien, scheduled commercial bank portfolio allocations, and maturity schedules.
- **RFC 4180 CSV Export**: Streamed on-demand with formula injection sanitization (`=`, `+`, `-`, `@`).

---

## 3. The 12 Synthetic Demonstration Scenarios

The portal includes 12 realistic demonstration scenarios pre-generated relative to runtime date, stored with real PDF FDR certificates in the secure document vault:

| # | FDR Number | Bank | Status | Validity | Description |
|---|------------|------|--------|----------|-------------|
| **1** | `FDR-SBIN-2024-1001` | State Bank of India | `ACTIVE` | `ACTIVE_VALID` | Clean active FDR, all checks verified, 520 days remaining |
| **2** | `FDR-PNB-2022-2002` | Punjab National Bank | `RENEWAL_REQUIRED` | `EXPIRING_SOON` | Approaching maturity (12 days left), renewal notice triggered |
| **3** | `FDR-HDFC-2021-3003` | HDFC Bank | `MATURED` | `MATURED` | Matured 20 days ago, overdue replacement prompt |
| **4** | `FDR-BOB-2025-4004` | Bank of Baroda | `SUBMITTED` | `ACTIVE_VALID` | Missing mandatory Bank Lien Letter |
| **5** | `FDR-CANARA-2024-5005` | Canara Bank | `PENDING_VERIFICATION` | `ACTIVE_VALID` | Amount Mismatch (Recorded ₹1.2 Cr vs Extracted ₹1.12 Cr) |
| **6** | `FDR-UBI-2024-6006` | Union Bank of India | `PENDING_VERIFICATION` | `ACTIVE_VALID` | Instrument number discrepancy in supporting letter |
| **7** | `FDR-SBIN-2023-7001-ORIG` | State Bank of India | `SUPERSEDED` | `MATURED` | Original instrument superseded by replacement FDR |
| **8** | `FDR-SBIN-2026-7007-RENEWED`| State Bank of India | `ACTIVE` | `ACTIVE_VALID` | Active replacement instrument linked to scenario 7 |
| **9** | `FDR-PNB-2016-8008` | Punjab National Bank | `RELEASE_REQUESTED` | `ACTIVE_VALID` | Full release request awaiting officer checklist review |
| **10**| `FDR-HDFC-2017-9009` | HDFC Bank | `RELEASE_REQUESTED` | `ACTIVE_VALID` | Release request returned for institution rectification |
| **11**| `FDR-BOB-2015-1010` | Bank of Baroda | `RELEASED` | `MATURED` | 10-year completed release case with final decision record |
| **12**| `FDR-RURAL-2025-1111` | Maharashtra Gramin Bank | `SUBMITTED` | `ACTIVE_VALID` | Regional rural bank with external gateway unavailable |

---

## 4. Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, PDF.js (`pdfjs-dist`) Canvas Viewer.
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite WAL mode, Pydantic v2, PyMuPDF (`pymupdf`), OpenCV, QRCode.
- **Storage Vault**: Isolated non-public directory (`vault/documents/`) with SHA-256 cryptographic hashing.

---

## 5. Quickstart & Execution

### Backend Setup
```powershell
# Navigate to backend directory
cd backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Seed baseline users and 12 demonstration scenarios
python scripts/seed_fdr_scenarios.py --force

# Run FastAPI backend server (Port 8000)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup
```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies and build
npm install
npm run build

# Run Vite development server (Port 5173)
npm run dev
```

### Running Backend Tests
```powershell
# Run the test suite
cd backend
pytest tests/ -v
```
All 11 tests pass with 100% success rate covering lifecycle transitions, dynamic validity, verification discrepancies, renewals, releases, and CSV exports.
