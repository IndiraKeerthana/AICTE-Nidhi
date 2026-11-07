import io
import os
import re
import json
from pathlib import Path
from PIL import Image
from app.services.anomaly_service import compute_image_phash, inspect_pdf_metadata_and_updates
from app.config import settings

# Graceful import of fitz (PyMuPDF)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Graceful import of pytesseract
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def configure_tesseract() -> tuple[bool, str]:
    """
    Checks if pytesseract and the underlying Tesseract OCR engine binary are operational.
    Configures tesseract_cmd from settings, environment variables, or standard paths on Windows.
    Returns (is_available, status_or_version_message).
    """
    if not TESSERACT_AVAILABLE:
        return False, "pytesseract Python package is not installed."

    if not getattr(settings, "ENABLE_OCR", True):
        return False, "OCR processing is disabled in system configuration (ENABLE_OCR=False)."

    custom_cmd = getattr(settings, "TESSERACT_CMD", "") or os.environ.get("TESSERACT_CMD", "")
    if custom_cmd:
        pytesseract.pytesseract.tesseract_cmd = custom_cmd

    # On Windows, try standard default locations if not configured or not found in PATH
    if os.name == "nt":
        current_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
        if current_cmd in ("tesseract", "") or not os.path.exists(current_cmd):
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for p in common_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

    try:
        ver = pytesseract.get_tesseract_version()
        return True, f"Tesseract v{ver}"
    except Exception as e:
        return False, f"Tesseract engine binary not found or failed execution: {str(e)}"


def is_tesseract_available() -> bool:
    """Helper to check if Tesseract OCR engine is functional."""
    avail, _ = configure_tesseract()
    return avail


def extract_document_content(
    storage_path: str,
    mime_type: str,
    max_ocr_pages: int = 3,
    ocr_timeout_sec: int = 15
) -> dict:
    """
    Parses document and returns complete intelligence metadata dict:
    - extracted_text
    - page_count
    - extracted_fields
    - extraction_method
    - phash
    - metadata_json
    - incremental_updates_count
    - ocr_needed
    - ocr_performed
    - ocr_engine_available
    - status ('PROCESSED' or 'EXTRACTION_FAILED')
    - incomplete_reason
    - is_complete (bool)
    """
    extracted_text = ""
    page_count = 1
    extraction_method = "PYMUPDF"
    extracted_fields: list[dict] = []
    phash = None
    metadata_json = None
    incremental_count = 0
    ocr_needed = False
    ocr_performed = False
    doc_status = "PROCESSED"
    incomplete_reason = None

    is_tess_avail, tess_status_msg = configure_tesseract()

    if mime_type == "application/pdf":
        meta_info = inspect_pdf_metadata_and_updates(storage_path)
        metadata_json = json.dumps(meta_info)
        incremental_count = meta_info.get("incremental_updates_count", 0)

        if not PYMUPDF_AVAILABLE:
            return {
                "extracted_text": "PyMuPDF not installed on host.",
                "page_count": 0,
                "extracted_fields": [],
                "extraction_method": "FALLBACK_PLACEHOLDER",
                "phash": None,
                "metadata_json": metadata_json,
                "incremental_updates_count": incremental_count,
                "ocr_needed": False,
                "ocr_performed": False,
                "ocr_engine_available": is_tess_avail,
                "status": "EXTRACTION_FAILED",
                "incomplete_reason": "PyMuPDF library is unavailable.",
                "is_complete": False
            }

        try:
            doc = fitz.open(storage_path)
            page_count = len(doc)
        except Exception as e:
            return {
                "extracted_text": f"PDF parsing error: {str(e)}",
                "page_count": 0,
                "extracted_fields": [],
                "extraction_method": "ERROR",
                "phash": None,
                "metadata_json": metadata_json,
                "incremental_updates_count": incremental_count,
                "ocr_needed": False,
                "ocr_performed": False,
                "ocr_engine_available": is_tess_avail,
                "status": "EXTRACTION_FAILED",
                "incomplete_reason": f"Corrupted or invalid PDF: {str(e)}",
                "is_complete": False
            }

        try:
            pages_text = []
            for page_idx, page in enumerate(doc):
                text = page.get_text("text") or ""
                pages_text.append(text)
                _extract_fields_from_page(text, page_idx + 1, extracted_fields, method="PYMUPDF", page_obj=page)

            extracted_text = "\n--- Page Break ---\n".join(pages_text).strip()

            # Check if native extracted text is essentially empty across all pages (excluding page break delimiters)
            all_native_text = "".join(pages_text)
            non_ws_chars = re.sub(r"\s+", "", all_native_text)
            if len(non_ws_chars) < 30:
                ocr_needed = True

                if not is_tess_avail:
                    # Tesseract is not installed or unavailable
                    ocr_performed = False
                    extraction_method = "SCANNED_PDF_NO_OCR"
                    doc_status = "EXTRACTION_FAILED"
                    incomplete_reason = f"Document is a scanned PDF with insufficient text layer, and OCR engine is unavailable ({tess_status_msg})."
                    extracted_text = f"Incomplete extraction: Document is a scanned PDF with insufficient text layer, and OCR engine is unavailable ({tess_status_msg})."
                else:
                    # Render pages to images using PyMuPDF and run actual Tesseract OCR
                    num_pages_to_ocr = min(max_ocr_pages, page_count)
                    ocr_pages_text = []
                    ocr_errors = []
                    ocr_performed = True

                    # Clear any sparse fields from native pass
                    extracted_fields.clear()

                    for page_idx in range(num_pages_to_ocr):
                        try:
                            page = doc[page_idx]
                            pix = page.get_pixmap(dpi=150)
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            ocr_page_text = pytesseract.image_to_string(img, timeout=ocr_timeout_sec) or ""
                            ocr_pages_text.append(ocr_page_text)
                            if ocr_page_text.strip():
                                _extract_fields_from_page(ocr_page_text, page_idx + 1, extracted_fields, method="OCR_TESSERACT")
                        except Exception as ocr_err:
                            ocr_errors.append(f"Page {page_idx + 1}: {str(ocr_err)}")

                    if ocr_errors and not any(t.strip() for t in ocr_pages_text):
                        doc_status = "EXTRACTION_FAILED"
                        extraction_method = "OCR_FAILED"
                        incomplete_reason = f"OCR execution failed on scanned pages: {'; '.join(ocr_errors)}"
                        extracted_text = f"Incomplete extraction: OCR execution failed ({'; '.join(ocr_errors)})."
                    else:
                        combined_ocr = "\n--- Page Break ---\n".join(ocr_pages_text).strip()
                        non_ws_ocr = re.sub(r"\s+", "", combined_ocr)
                        if len(non_ws_ocr) >= 15:
                            # Useful text extracted
                            extraction_method = "OCR_TESSERACT"
                            doc_status = "PROCESSED"
                            extracted_text = combined_ocr
                        else:
                            # OCR ran, but pages are blank or unreadable
                            doc_status = "EXTRACTION_FAILED"
                            extraction_method = "OCR_UNREADABLE"
                            incomplete_reason = "OCR was attempted on scanned pages, but no legible or useful text could be extracted."
                            extracted_text = "Incomplete extraction: Document pages appear unreadable or blank. OCR yielded no usable text."
            else:
                # Native PyMuPDF text is sufficient
                extraction_method = "PYMUPDF"
                ocr_needed = False
                ocr_performed = False
                doc_status = "PROCESSED"

        finally:
            doc.close()

    elif mime_type.startswith("image/"):
        extraction_method = "IMAGE_ANALYSIS"
        phash = compute_image_phash(storage_path)
        try:
            with Image.open(storage_path) as img:
                width, height = img.size
                extracted_text = f"Image Evidence: {width}x{height} pixels, format {img.format}."
                ocr_needed = True

                if is_tess_avail:
                    try:
                        ocr_text = pytesseract.image_to_string(img, timeout=ocr_timeout_sec) or ""
                        ocr_performed = True
                        if ocr_text.strip():
                            extracted_text += f"\nOCR Output:\n{ocr_text.strip()}"
                            extraction_method = "OCR_TESSERACT"
                            doc_status = "PROCESSED"
                            _extract_fields_from_page(ocr_text, 1, extracted_fields, method="OCR_TESSERACT")
                        else:
                            # Valid photo attachment with no text (e.g. campus photo)
                            doc_status = "PROCESSED"
                    except Exception as e:
                        ocr_performed = True
                        extraction_method = "OCR_FAILED"
                        doc_status = "EXTRACTION_FAILED"
                        incomplete_reason = f"Image OCR error: {str(e)}"
                        extracted_text += f"\nOCR error: {str(e)}"
                else:
                    ocr_performed = False
                    extraction_method = "IMAGE_ANALYSIS_NO_OCR"
                    doc_status = "PROCESSED"
        except Exception as e:
            extracted_text = f"Image processing error: {str(e)}"
            doc_status = "EXTRACTION_FAILED"
            incomplete_reason = str(e)

    return {
        "extracted_text": extracted_text,
        "page_count": page_count,
        "extracted_fields": extracted_fields,
        "extraction_method": extraction_method,
        "phash": phash,
        "metadata_json": metadata_json,
        "incremental_updates_count": incremental_count,
        "ocr_needed": ocr_needed,
        "ocr_performed": ocr_performed,
        "ocr_engine_available": is_tess_avail,
        "status": doc_status,
        "incomplete_reason": incomplete_reason,
        "is_complete": doc_status == "PROCESSED"
    }


def _extract_fields_from_page(text: str, page_num: int, fields_list: list[dict], method: str, page_obj=None):
    """Applies robust regex extractors to identify key regulatory values and calculates genuine bounding box coordinates when page_obj is provided."""
    if not text:
        return

    def _find_bbox(search_term: str):
        if not page_obj or not search_term or not hasattr(page_obj, "search_for"):
            return None
        try:
            rects = page_obj.search_for(search_term)
            if rects:
                r = rects[0]
                pw = float(page_obj.rect.width) if hasattr(page_obj, "rect") else 595.0
                ph = float(page_obj.rect.height) if hasattr(page_obj, "rect") else 842.0
                return json.dumps({
                    "x": round(float(r.x0), 2),
                    "y": round(float(r.y0), 2),
                    "width": round(float(r.width), 2),
                    "height": round(float(r.height), 2),
                    "page_width": round(pw, 2),
                    "page_height": round(ph, 2),
                })
        except Exception:
            return None
        return None

    # 1. Intake numbers
    intake_match = re.search(r"(?:intake|approved intake|sanctioned intake|intake capacity|seats)[\s:=]*([0-9]{2,4})\b", text, re.IGNORECASE)
    if intake_match:
        val = intake_match.group(1)
        snippet = intake_match.group(0)
        bbox = _find_bbox(val) or _find_bbox(snippet)
        fields_list.append({
            "field_key": "intake_capacity",
            "field_value": val,
            "normalized_value": val,
            "confidence_score": 0.95,
            "page_number": page_num,
            "source_snippet": snippet,
            "bounding_box": bbox,
            "extraction_method": method
        })

    # 2. Land Area
    land_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:acres|acre|hectares|sq\.?\s*m(?:eters)?)", text, re.IGNORECASE)
    if land_match:
        val = land_match.group(1)
        snippet = land_match.group(0)
        bbox = _find_bbox(snippet) or _find_bbox(val)
        fields_list.append({
            "field_key": "land_area",
            "field_value": snippet,
            "normalized_value": val,
            "confidence_score": 0.90,
            "page_number": page_num,
            "source_snippet": snippet,
            "bounding_box": bbox,
            "extraction_method": method
        })

    # 3. Expiry / Validity Dates
    expiry_match = re.search(r"(?:valid up to|valid till|valid upto|expiry date|valid through|expired on)[\s.:]*([0-9]{1,4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})", text, re.IGNORECASE)
    if expiry_match:
        val = expiry_match.group(1)
        snippet = expiry_match.group(0)
        bbox = _find_bbox(val) or _find_bbox(snippet)
        fields_list.append({
            "field_key": "expiry_date",
            "field_value": val,
            "normalized_value": val,
            "confidence_score": 0.92,
            "page_number": page_num,
            "source_snippet": snippet,
            "bounding_box": bbox,
            "extraction_method": method
        })

    # 4. Certificate / NOC Reference Numbers
    cert_match = re.search(r"(?:certificate no|cert no|ref no|order no|file no)[\s.:]*([A-Za-z0-9\/-]{5,30})", text, re.IGNORECASE)
    if cert_match:
        val = cert_match.group(1)
        snippet = cert_match.group(0)
        bbox = _find_bbox(val) or _find_bbox(snippet)
        fields_list.append({
            "field_key": "certificate_number",
            "field_value": val,
            "normalized_value": val,
            "confidence_score": 0.88,
            "page_number": page_num,
            "source_snippet": snippet,
            "bounding_box": bbox,
            "extraction_method": method
        })
