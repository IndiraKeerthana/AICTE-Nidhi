import json
import datetime
import re
from urllib.parse import urlparse, parse_qs
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Simulated Issuing Authority Registry Database (Synthetic ground-truth for SIH testing)
# Clearly identified as synthetic mock records. Not connected to live authority databases.
SIMULATED_AUTHORITY_REGISTRY = {
    # --- SCENARIO A: Valid Matching Records (VERIFIED) ---
    "FS-2026-SARASWATI-01": {
        "approval_ref": "FS-2026-SARASWATI-01",
        "issuing_authority": "Municipal Directorate of Fire & Emergency Services",
        "approval_type": "FIRE_SAFETY_NOC",
        "institution_name": "Saraswati College of Engineering & Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2025-06-01",
        "valid_till": "2027-06-30",
        "status": "ACTIVE",
        "status_reason": "Regular periodic inspection completed satisfactorily (SYNTHETIC DEMO DATA).",
        "supporting_metadata": "Sanctioned educational occupancy approved. Hydrant network functional."
    },
    "UNIV-AFFIL-SARASWATI-01": {
        "approval_ref": "UNIV-AFFIL-SARASWATI-01",
        "issuing_authority": "State Technical University Examination & Affiliation Board",
        "approval_type": "AFFILIATION_LETTER",
        "institution_name": "Saraswati College of Engineering & Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2025-05-15",
        "valid_till": "2027-06-30",
        "status": "ACTIVE",
        "status_reason": "Permanent affiliation renewed for undergraduate engineering programmes (SYNTHETIC DEMO DATA).",
        "supporting_metadata": "Sanctioned B.Tech CSE intake: 120 seats."
    },
    "FS-2026-1044": {
        "approval_ref": "FS-2026-1044",
        "issuing_authority": "Municipal Directorate of Fire & Emergency Services",
        "approval_type": "FIRE_SAFETY_NOC",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2024-06-01",
        "valid_till": "2027-06-30",
        "status": "ACTIVE",
        "status_reason": "Regular periodic inspection completed satisfactorily.",
        "supporting_metadata": "Sanctioned building height: 14.8m; Adequate hydrants and two 20,000L static water tanks certified."
    },
    "BP-2025-MUN-881": {
        "approval_ref": "BP-2025-MUN-881",
        "issuing_authority": "Municipal Corporation Town Planning Department",
        "approval_type": "BUILDING_PLAN",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2023-11-20",
        "valid_till": "2028-11-19",
        "status": "ACTIVE",
        "status_reason": "Commencement and occupancy sanctioned for educational institutional use.",
        "supporting_metadata": "Sanctioned instructional built-up area: 4,850 sq.m; administrative area: 1,200 sq.m."
    },
    "UNIV-AFFIL-2025-662": {
        "approval_ref": "UNIV-AFFIL-2025-662",
        "issuing_authority": "State Technical University Examination & Affiliation Board",
        "approval_type": "AFFILIATION_LETTER",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2025-05-15",
        "valid_till": "2026-06-30",
        "status": "ACTIVE",
        "status_reason": "Permanent affiliation renewed for undergraduate engineering programmes.",
        "supporting_metadata": "Sanctioned B.Tech CSE intake: 60 seats; ECE: 60 seats."
    },
    "ENV-2025-CLEAR": {
        "approval_ref": "ENV-2025-CLEAR",
        "issuing_authority": "State Environment Impact Assessment Authority (SEIAA)",
        "approval_type": "ENVIRONMENTAL_CLEARANCE",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2024-02-10",
        "valid_till": "2029-02-09",
        "status": "ACTIVE",
        "status_reason": "Environmental clearance granted under Category B2 (Educational Institution).",
        "supporting_metadata": "Zero-discharge sewage treatment plant (STP) capacity: 45 KLD mandated."
    },

    # --- SCENARIO C: Entity / Institution Mismatch (ENTITY_MISMATCH) ---
    "BP-2023-OTHER-INST": {
        "approval_ref": "BP-2023-OTHER-INST",
        "issuing_authority": "Municipal Corporation Town Planning Department",
        "approval_type": "BUILDING_PLAN",
        "institution_name": "Maharashtra Academy of Engineering & Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2023-04-12",
        "valid_till": "2028-04-11",
        "status": "ACTIVE",
        "status_reason": "Approval issued to Maharashtra Academy of Engineering Trust.",
        "supporting_metadata": "Registered entity differs from applicant institution."
    },

    # --- SCENARIO D: Approved Location Mismatch (LOCATION_MISMATCH) ---
    "UNIV-AFFIL-VANGUARD-LOC-ERR": {
        "approval_ref": "UNIV-AFFIL-VANGUARD-LOC-ERR",
        "issuing_authority": "State Technical University Examination & Affiliation Board",
        "approval_type": "AFFILIATION_LETTER",
        "institution_name": "Vanguard Institute of Applied Technology",
        "approved_location": "Plot 88, MIDC Hinjewadi Phase 3, Pune, Maharashtra",
        "issue_date": "2024-05-20",
        "valid_till": "2027-05-19",
        "status": "ACTIVE",
        "status_reason": "Affiliation order sanctioned for Hinjewadi campus premises only (SYNTHETIC DEMO DATA).",
        "supporting_metadata": "Declared application campus is Katraj-Kondhwa Road."
    },
    "BP-2024-DIFF-LOC": {
        "approval_ref": "BP-2024-DIFF-LOC",
        "issuing_authority": "Municipal Corporation Town Planning Department",
        "approval_type": "BUILDING_PLAN",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Plot 45, Sector 9, Hadapsar Industrial Area, Pune, Maharashtra",
        "issue_date": "2024-01-18",
        "valid_till": "2029-01-17",
        "status": "ACTIVE",
        "status_reason": "Sanctioned for auxiliary property at Hadapsar campus.",
        "supporting_metadata": "Survey number differs from declared primary campus."
    },

    # --- SCENARIO F: Expired Approval Record (EXPIRED) ---
    "FS-2024-VANGUARD-EXP": {
        "approval_ref": "FS-2024-VANGUARD-EXP",
        "issuing_authority": "Municipal Directorate of Fire & Emergency Services",
        "approval_type": "FIRE_SAFETY_NOC",
        "institution_name": "Vanguard Institute of Applied Technology",
        "approved_location": "Campus Sector 12, Katraj-Kondhwa Road, Pune, Maharashtra",
        "issue_date": "2021-01-16",
        "valid_till": "2024-01-15",
        "status": "EXPIRED",
        "status_reason": "Statutory three-year validity expired on 15/01/2024 without recorded renewal (SYNTHETIC DEMO DATA).",
        "supporting_metadata": "Renewal application pending inspection."
    },
    "FS-2025-9981": {
        "approval_ref": "FS-2025-9981",
        "issuing_authority": "Municipal Directorate of Fire & Emergency Services",
        "approval_type": "FIRE_SAFETY_NOC",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2024-09-16",
        "valid_till": "2025-09-15",
        "status": "EXPIRED",
        "status_reason": "Annual fire safety certification expired without renewal filing.",
        "supporting_metadata": "Requires annual inspection renewal certificate."
    },

    # --- SCENARIO F: Revoked Approval Record (STATUS_INVALID) ---
    "BP-2022-REVOKED": {
        "approval_ref": "BP-2022-REVOKED",
        "issuing_authority": "Municipal Corporation Town Planning Department",
        "approval_type": "BUILDING_PLAN",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2022-08-10",
        "valid_till": "2027-08-09",
        "status": "REVOKED",
        "status_reason": "Revoked by Municipal Commissioner on 2024-03-12 due to unauthorized structural alteration in refuge area.",
        "supporting_metadata": "Revocation Order No. MC/TP/REV-2024-19."
    },

    # --- SCENARIO F: Rejected Approval Record (STATUS_INVALID) ---
    "BP-2024-REJECTED": {
        "approval_ref": "BP-2024-REJECTED",
        "issuing_authority": "Municipal Corporation Town Planning Department",
        "approval_type": "BUILDING_PLAN",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2024-05-18",
        "valid_till": "2024-05-18",
        "status": "REJECTED",
        "status_reason": "Rejected on 2024-05-18 due to inadequate instructional carpet area and non-conformance with road setback norms.",
        "supporting_metadata": "Town Planning Committee Resolution 44/2024."
    },

    # --- SCENARIO G: Authority Gateway Timeout / Offline (AUTHORITY_UNAVAILABLE) ---
    "ENV-GATEWAY-TIMEOUT": {
        "approval_ref": "ENV-GATEWAY-TIMEOUT",
        "issuing_authority": "State Environment Impact Assessment Authority (SEIAA)",
        "approval_type": "ENVIRONMENTAL_CLEARANCE",
        "institution_name": "Sample Institute of Technology",
        "approved_location": "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "issue_date": "2024-01-01",
        "valid_till": "2029-01-01",
        "status": "GATEWAY_TIMEOUT",
        "status_reason": "External issuing authority portal connection timed out.",
        "supporting_metadata": "Gateway unavailable."
    }
}

AUTHORITY_NAMES_BY_TYPE = {
    "FIRE_SAFETY_NOC": "Municipal Directorate of Fire & Emergency Services",
    "BUILDING_PLAN": "Municipal Corporation Town Planning Department",
    "LAYOUT_APPROVAL": "Municipal Corporation Town Planning Department",
    "AFFILIATION_LETTER": "State Technical University Examination & Affiliation Board",
    "ENVIRONMENTAL_CLEARANCE": "State Environment Impact Assessment Authority (SEIAA)",
    "LAND_TITLE_DEED": "State Revenue Department (Sub-Registrar of Land Records)"
}


def _decode_qr_from_cv_image(cv_img: np.ndarray) -> str | None:
    """
    Decodes QR code from a BGR numpy array using multi-pass OpenCV detection.
    Pass 1: Original BGR image
    Pass 2: Grayscale
    Pass 3: Otsu thresholding
    """
    if cv_img is None or cv_img.size == 0:
        return None

    detector = cv2.QRCodeDetector()

    # Pass 1: Raw BGR
    try:
        data, _, _ = detector.detectAndDecode(cv_img)
        if data and data.strip():
            return data.strip()
    except Exception:
        pass

    # Pass 2: Grayscale
    gray = None
    try:
        if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv_img
        data, _, _ = detector.detectAndDecode(gray)
        if data and data.strip():
            return data.strip()
    except Exception:
        gray = None

    # Pass 3: Thresholded
    if gray is not None:
        try:
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            data, _, _ = detector.detectAndDecode(thresh)
            if data and data.strip():
                return data.strip()
        except Exception:
            pass

    return None


def decode_qr_code(
    file_path: str,
    mime_type: str | None = None,
    max_pages: int = 3,
    target_dpi: int = 150,
    max_dimension: int = 3000
) -> dict:
    """
    Decodes 2D QR codes from PDF or image documents.
    For PDFs: renders pages using PyMuPDF in-memory and passes to OpenCV (does NOT call cv2.imread on PDF).
    For Images: checks resolution and resizes if dimension exceeds max_dimension.

    Limits:
    - PDF pages: first `max_pages` pages (default: 3)
    - Image size: scaled proportionally if max dimension > `max_dimension` (default: 3000)
    - Rendering resolution: `target_dpi` (default: 150)

    Returns:
    {
        "attempted": bool,
        "found": bool,
        "payload": str | None,
        "page_number": int | None,
        "pages_scanned": int,
        "source_type": "PDF" | "IMAGE" | "UNKNOWN",
        "notes": str,
        "error": str | None
    }
    """
    res = {
        "attempted": True,
        "found": False,
        "payload": None,
        "page_number": None,
        "pages_scanned": 0,
        "source_type": "UNKNOWN",
        "notes": "",
        "error": None
    }

    path_obj = Path(file_path)
    if not path_obj.exists():
        res["notes"] = f"File does not exist: {file_path}"
        res["error"] = "FILE_NOT_FOUND"
        return res

    # Determine if PDF
    is_pdf = False
    if mime_type == "application/pdf" or path_obj.suffix.lower() == ".pdf":
        is_pdf = True
    else:
        # Check magic bytes
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                if header.startswith(b"%PDF"):
                    is_pdf = True
        except Exception:
            pass

    if is_pdf:
        res["source_type"] = "PDF"
        if not PYMUPDF_AVAILABLE:
            res["notes"] = "PyMuPDF (fitz) is not available on host. Cannot render PDF for QR decoding."
            res["error"] = "DEPENDENCY_MISSING"
            return res

        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            pages_to_check = min(total_pages, max_pages)

            for page_idx in range(pages_to_check):
                res["pages_scanned"] = page_idx + 1
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=target_dpi)
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

                payload = _decode_qr_from_cv_image(cv_img)
                if payload:
                    res["found"] = True
                    res["payload"] = payload
                    res["page_number"] = page_idx + 1
                    res["notes"] = f"QR code successfully detected and decoded on page {page_idx + 1} of PDF."
                    doc.close()
                    return res

            doc.close()
            res["notes"] = f"No readable QR code found in first {pages_to_check} page(s) of PDF (total {total_pages} pages)."
            return res
        except Exception as e:
            res["notes"] = f"Error rendering PDF for QR decoding: {str(e)}"
            res["error"] = str(e)
            return res

    # Handle as Image
    res["source_type"] = "IMAGE"
    try:
        with Image.open(file_path) as pil_img:
            w, h = pil_img.size
            if w > max_dimension or h > max_dimension:
                pil_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
            rgb_img = pil_img.convert("RGB")
            cv_img = cv2.cvtColor(np.array(rgb_img), cv2.COLOR_RGB2BGR)

        res["pages_scanned"] = 1
        payload = _decode_qr_from_cv_image(cv_img)
        if payload:
            res["found"] = True
            res["payload"] = payload
            res["page_number"] = 1
            res["notes"] = "QR code successfully detected and decoded from image."
            return res
        else:
            res["notes"] = "No readable QR code found in image."
            return res
    except Exception as e:
        res["notes"] = f"Error reading image for QR decoding: {str(e)}"
        res["error"] = str(e)
        return res


def decode_qr_code_from_image(image_path: str) -> tuple[str | None, str]:
    """
    Decodes 2D QR codes using OpenCV QRCodeDetector.
    Maintained for backward compatibility. Supports both PDF and image documents.
    Returns: (decoded_text_or_none, detector_status_notes)
    """
    res = decode_qr_code(image_path)
    return res.get("payload"), res.get("notes", "")


def _extract_reference_from_payload(payload: str) -> str | None:
    """
    Extracts an approval/certificate reference from a QR payload.
    Supports:
    - JSON strings (e.g. {"cert_id": "...", "ref_no": "...", "approval_ref": "..."})
    - URLs with query params (e.g. ?cert=..., ?ref=..., ?id=..., ?approval_no=...)
    - URLs with path parameters (e.g. /verify/FS-2026-1044)
    - Plain statutory reference strings (e.g. FS-2026-1044, BP-2025-MUN-881)
    """
    if not payload:
        return None
    p = payload.strip()

    # 1. Try JSON
    if (p.startswith("{") and p.endswith("}")) or (p.startswith("[") and p.endswith("]")):
        try:
            d = json.loads(p)
            if isinstance(d, dict):
                for k in ("cert_id", "ref_no", "approval_ref", "certificate_number", "approval_no", "ref", "id", "cert"):
                    val = d.get(k)
                    if val and isinstance(val, str) and val.strip():
                        return val.strip()
        except Exception:
            pass

    # 2. Try URL
    if "://" in p or p.startswith("http") or p.startswith("www."):
        try:
            url_str = p if "://" in p else f"https://{p}"
            parsed_url = urlparse(url_str)
            qs = parse_qs(parsed_url.query)
            for k in ("cert", "ref", "id", "approval_ref", "cert_id", "ref_no", "approval_no", "certificate_no"):
                if k in qs and qs[k]:
                    return qs[k][0].strip()
            # If no query parameter, check path segments
            path_parts = [part for part in parsed_url.path.split("/") if part]
            for part in reversed(path_parts):
                if re.match(r"^(?:FS|BP|UNIV|ENV|AFFIL|NOC|DEED)-[A-Za-z0-9\-]+$", part, re.IGNORECASE):
                    return part.strip()
        except Exception:
            pass

    # 3. Regex search for known statutory prefix pattern
    match = re.search(r"\b((?:FS|BP|UNIV|ENV|AFFIL|NOC|DEED)-[A-Za-z0-9\-]{4,30})\b", p, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 4. Regex for query string params if malformed URL
    ref_match = re.search(r"[?&](?:ref|cert|id|approval_no)=([A-Za-z0-9\-_]+)", p, re.IGNORECASE)
    if ref_match:
        return ref_match.group(1).strip()

    return p

def _norm_location_tokens(loc_str: str) -> set[str]:
    """Extract normalized alphanumeric tokens from location string, excluding common administrative stop words."""
    if not loc_str:
        return set()
    return set(re.findall(r"[A-Za-z0-9]+", loc_str.lower())) - {"campus", "plot", "survey", "no", "road", "pune", "maharashtra"}


def verify_against_authority_registry(
    cert_reference: str | None,
    cert_type: str = "FIRE_SAFETY_NOC",
    institution_name: str | None = None,
    declared_location: str | None = None,
    qr_payload: str | None = None,
    qr_metadata: dict | None = None
) -> dict:
    """
    Simulated External Authority Cross-Verification Engine.
    Cross-checks extracted document certificate references against the synthetic issuing authority registry.
    
    Strictly distinguishes failure reasons per Section 10:
    - VERIFIED: Matching authority record, matching institution, matching location, active status.
    - RECORD_NOT_FOUND: Reference does not exist in mock registry. Explains without accusing of fraud.
    - REFERENCE_MISMATCH: Extracted certificate reference differs from declared reference.
    - ENTITY_MISMATCH: Reference belongs to another institution in registry.
    - LOCATION_MISMATCH: Approved location in registry differs from declared campus.
    - STATUS_INVALID: Registry records approval as revoked, rejected or invalid.
    - EXPIRED: Applicable validity period ended.
    - EXTRACTION_INCOMPLETE: Required reference could not be reliably extracted.
    - AUTHORITY_UNAVAILABLE: Verification gateway offline or unreachable.
    
    Always includes simulated disclosure: 'SIMULATED EXTERNAL CHECK — SYNTHETIC DATA'.
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    issuing_authority = AUTHORITY_NAMES_BY_TYPE.get(cert_type, "Issuing Authority Gateway")
    source_name = f"{issuing_authority} [SIMULATED]"

    # Resolve lookup key and source
    lookup_key = cert_reference
    lookup_source = "EXTRACTED_TEXT" if cert_reference else "UNRESOLVED"
    if qr_payload:
        extracted_from_qr = _extract_reference_from_payload(qr_payload)
        if extracted_from_qr:
            lookup_key = extracted_from_qr
            lookup_source = "QR_CODE"

    # Resolve QR metadata
    qr_attempted = False
    qr_found = False
    qr_notes = "QR decoding not invoked."
    qr_page = None
    qr_pages_scanned = 0
    if qr_metadata:
        qr_attempted = qr_metadata.get("attempted", False)
        qr_found = qr_metadata.get("found", False)
        qr_notes = qr_metadata.get("notes", "")
        qr_page = qr_metadata.get("page_number")
        qr_pages_scanned = qr_metadata.get("pages_scanned", 0)
    elif qr_payload:
        qr_attempted = True
        qr_found = True
        qr_notes = "QR code payload supplied."

    def _attach_meta(result_dict: dict) -> dict:
        result_dict["lookup_source"] = lookup_source
        result_dict["qr_attempted"] = qr_attempted
        result_dict["qr_found"] = qr_found
        result_dict["qr_payload"] = qr_payload
        result_dict["qr_notes"] = qr_notes
        result_dict["qr_page_number"] = qr_page
        result_dict["qr_pages_scanned"] = qr_pages_scanned
        result_dict["is_simulated"] = True
        return result_dict

    # Case 1: Incomplete Extraction (no reference found in document)
    if not lookup_key or lookup_key.strip() in ("", "UNKNOWN", "NOT_FOUND"):
        return _attach_meta({
            "outcome": "EXTRACTION_INCOMPLETE",
            "status": "SOURCE_UNAVAILABLE",
            "source_name": source_name,
            "source_reference": "UNRESOLVED",
            "is_simulated": True,
            "requires_human_review": True,
            "specific_reason": "Approval reference number could not be reliably extracted from the uploaded document.",
            "expected_value": "Valid approval reference number (e.g. FS-YYYY-XXXX, BP-YYYY-XXXX)",
            "observed_value": "No legible certificate reference detected in document",
            "what_remains_uncertain": "Whether the document contains a valid reference in an unread section or seal.",
            "recommended_action": "Inspect document using in-app viewer to manually locate certificate reference.",
            "matched_record": None,
            "attempt_timestamp": now_iso,
            "explanation": f"Approval reference could not be extracted for {cert_type}. Manual inspection is required."
        })

    lookup_clean = lookup_key.strip()

    # Case 2: Authority Service Unavailable / Gateway Timeout (Scenario G)
    if lookup_clean == "ENV-GATEWAY-TIMEOUT" or "TIMEOUT" in lookup_clean or "OFFLINE" in lookup_clean:
        return _attach_meta({
            "outcome": "AUTHORITY_UNAVAILABLE",
            "status": "SOURCE_UNAVAILABLE",
            "source_name": source_name,
            "source_reference": lookup_clean,
            "is_simulated": True,
            "requires_human_review": True,
            "specific_reason": f"Connection to {issuing_authority} registry portal timed out after 3 retry attempts.",
            "expected_value": f"Response from {issuing_authority} Registry Gateway",
            "observed_value": "HTTP 504 Gateway Timeout (Service temporarily unreachable)",
            "what_remains_uncertain": "Current registration status of this certificate on the state authority portal.",
            "recommended_action": "Re-run cross-verification once the authority gateway returns online, or confirm via direct departmental channel.",
            "matched_record": None,
            "attempt_timestamp": now_iso,
            "explanation": f"Mock authority gateway for {issuing_authority} is temporarily unreachable. Check could not be completed."
        })

    # Case 3: Record Not Found in Registry (Scenario B)
    if lookup_clean not in SIMULATED_AUTHORITY_REGISTRY:
        return _attach_meta({
            "outcome": "RECORD_NOT_FOUND",
            "status": "MISMATCH_DETECTED",
            "source_name": source_name,
            "source_reference": lookup_clean,
            "is_simulated": True,
            "requires_human_review": True,
            "specific_reason": f"Approval reference '{lookup_clean}' was not found in the synthetic registry of {issuing_authority}.",
            "expected_value": f"Authentic registration record in {issuing_authority} database",
            "observed_value": f"Reference '{lookup_clean}' not indexed in registry",
            "what_remains_uncertain": "Whether the discrepancy is caused by a clerical typing variance, an unindexed regional authority division, or an unverified submission.",
            "recommended_action": "Review the uploaded document in the in-app viewer and request clarification or certified original from the institution.",
            "matched_record": None,
            "attempt_timestamp": now_iso,
            "explanation": (
                f"No matching record found in {issuing_authority} registry for reference '{lookup_clean}'. "
                "This does not automatically establish an improper submission; manual confirmation with the issuing authority is recommended."
            )
        })

    record = SIMULATED_AUTHORITY_REGISTRY[lookup_clean]

    # Case 4: Invalid Status — Revoked or Rejected (Scenario F)
    rec_status = record.get("status", "ACTIVE")
    if rec_status in ("REVOKED", "REJECTED"):
        return _attach_meta({
            "outcome": "STATUS_INVALID",
            "status": "MISMATCH_DETECTED",
            "source_name": source_name,
            "source_reference": lookup_clean,
            "is_simulated": True,
            "requires_human_review": True,
            "specific_reason": f"Authority registry records approval '{lookup_clean}' as {rec_status}. {record.get('status_reason', '')}",
            "expected_value": "Active / Valid statutory approval status",
            "observed_value": f"Recorded as {rec_status} in {issuing_authority} registry",
            "what_remains_uncertain": "Whether a subsequent stay order, rectification order, or appeal has been granted.",
            "recommended_action": "Flag for scrutiny committee review. Issue deficiency notice regarding invalid approval status.",
            "matched_record": record,
            "attempt_timestamp": now_iso,
            "explanation": f"The synthetic authority registry records this approval as {rec_status}: {record.get('status_reason', '')}"
        })

    # Case 5: Expired Validity (Scenario F)
    if rec_status == "EXPIRED":
        return _attach_meta({
            "outcome": "EXPIRED",
            "status": "EXPIRED",
            "source_name": source_name,
            "source_reference": lookup_clean,
            "is_simulated": True,
            "requires_human_review": True,
            "specific_reason": f"Certificate validity ended on {record.get('valid_till')}. {record.get('status_reason', '')}",
            "expected_value": "Valid unexpired statutory certificate (valid through current academic year)",
            "observed_value": f"Expired on {record.get('valid_till')}",
            "what_remains_uncertain": "Whether an in-process renewal application has been acknowledged by the authority.",
            "recommended_action": "Issue deficiency notice requesting renewed certificate or formal renewal acknowledgement.",
            "matched_record": record,
            "attempt_timestamp": now_iso,
            "explanation": f"Issuing authority confirms certificate '{lookup_clean}' expired on {record.get('valid_till')}."
        })

    # Case 6: Institution / Entity Mismatch (Scenario C)
    if institution_name and record.get("institution_name"):
        from app.services.anomaly_service import evaluate_institution_name_similarity
        score, acceptable = evaluate_institution_name_similarity(record["institution_name"], institution_name)
        if not acceptable:
            return _attach_meta({
                "outcome": "ENTITY_MISMATCH",
                "status": "MISMATCH_DETECTED",
                "source_name": source_name,
                "source_reference": lookup_clean,
                "is_simulated": True,
                "requires_human_review": True,
                "specific_reason": (
                    f"Approval reference '{lookup_clean}' in registry is issued to '{record['institution_name']}', "
                    f"which differs from applicant institution '{institution_name}' (similarity: {score:.1f}%)."
                ),
                "expected_value": f"Registered Institution: {institution_name}",
                "observed_value": f"Authority Record Holder: {record['institution_name']}",
                "what_remains_uncertain": "Whether the applicant institution operates under a parent educational trust with a differing legal title.",
                "recommended_action": "Examine trust deed or request institutional corrigendum explaining legal entity relationship.",
                "matched_record": record,
                "attempt_timestamp": now_iso,
                "explanation": (
                    f"Approval reference belongs to a different institution ('{record['institution_name']}') in the authority registry. "
                    "Manual verification of institutional ownership is required."
                )
            })

    # Case 7: Approved Location Mismatch (Scenario D)
    if declared_location and record.get("approved_location"):
        dec_tokens = _norm_location_tokens(declared_location)
        rec_tokens = _norm_location_tokens(record["approved_location"])
        common = dec_tokens.intersection(rec_tokens)

        # If location tokens show stark disagreement (e.g. Hadapsar vs Kothrud)
        if ("hadapsar" in rec_tokens and "kothrud" in dec_tokens) or (len(common) == 0 and len(rec_tokens) > 0 and len(dec_tokens) > 0):
            return _attach_meta({
                "outcome": "LOCATION_MISMATCH",
                "status": "MISMATCH_DETECTED",
                "source_name": source_name,
                "source_reference": lookup_clean,
                "is_simulated": True,
                "requires_human_review": True,
                "specific_reason": (
                    f"The property location recorded in the authority registry ('{record['approved_location']}') "
                    f"differs from the declared campus location ('{declared_location}')."
                ),
                "expected_value": f"Campus Location: {declared_location}",
                "observed_value": f"Authority Registered Location: {record['approved_location']}",
                "what_remains_uncertain": "Whether the institution operates multi-campus premises or relocated with municipal approval.",
                "recommended_action": "Request land conversion and municipal campus relocation order or clarification.",
                "matched_record": record,
                "attempt_timestamp": now_iso,
                "explanation": (
                    f"Approved location in {issuing_authority} registry ('{record['approved_location']}') "
                    f"differs from application campus ('{declared_location}')."
                )
            })

    # Case 8: Successful Verification (Scenario A)
    return _attach_meta({
        "outcome": "VERIFIED",
        "status": "VERIFIED",
        "source_name": source_name,
        "source_reference": lookup_clean,
        "is_simulated": True,
        "requires_human_review": False,
        "specific_reason": f"Approval record confirmed in {issuing_authority} registry. Institution name, location, and validity verified.",
        "expected_value": f"Valid approval registered to {record.get('institution_name', institution_name)}",
        "observed_value": f"Confirmed Active (Valid till {record.get('valid_till', 'End of AY')})",
        "what_remains_uncertain": "None. Regulatory fields reconcile satisfactorily.",
        "recommended_action": "Statutory verification complete. Proceed with scrutiny review.",
        "matched_record": record,
        "attempt_timestamp": now_iso,
        "explanation": f"Authenticity verified via {source_name}. [SIMULATED EXTERNAL CHECK — SYNTHETIC DATA] Certificate valid till {record.get('valid_till', 'End of AY')}."
    })
