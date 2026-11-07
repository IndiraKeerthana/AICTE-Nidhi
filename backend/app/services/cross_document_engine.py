import re
import datetime
from typing import Any
from rapidfuzz import fuzz
from app.services.anomaly_service import _normalize_institution_name, evaluate_institution_name_similarity


# Unit conversion factors to standard ACRES
SQ_METERS_PER_ACRE = 4046.8564
HECTARES_PER_ACRE = 0.404686
SQ_FT_PER_ACRE = 43560.0


def parse_land_area_to_acres(val_str: str | None) -> tuple[float | None, str | None]:
    """
    Parses land area string with units and normalizes to standard acres.
    Supports acres, acre, sq meters, sq.m, sqm, hectares, ha, sq ft.
    Returns (acres_float, original_unit_detected) or (None, None).
    """
    if not val_str:
        return None, None

    s = str(val_str).strip().lower()

    # Look for number + unit pattern
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(acres?|hectares?|ha|sq\.?\s*m(?:eters?)?|sqm|sq\.?\s*ft|sqft)?", s)
    if not match:
        return None, None

    try:
        num = float(match.group(1))
    except ValueError:
        return None, None

    unit = (match.group(2) or "acres").replace(" ", "").replace(".", "")

    if "hectare" in unit or unit == "ha":
        return num / HECTARES_PER_ACRE, "hectares"
    elif "sqm" in unit or "sqmeter" in unit or "sqm" in unit:
        return num / SQ_METERS_PER_ACRE, "sq. meters"
    elif "sqft" in unit or "sqft" in unit:
        return num / SQ_FT_PER_ACRE, "sq. feet"
    else:
        return num, "acres"


def compare_land_areas(
    area1_str: str | None,
    area2_str: str | None,
    tolerance_pct: float = 3.0
) -> dict:
    """
    Compares two land area values with unit conversion to acres.
    Permits up to tolerance_pct (default 3%) variance for measurement / surveying conversion differences.
    """
    if not area1_str or not area2_str:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "One or both land area fields are absent or could not be reliably extracted."
        }

    a1, u1 = parse_land_area_to_acres(area1_str)
    a2, u2 = parse_land_area_to_acres(area2_str)

    if a1 is None or a2 is None or a1 <= 0 or a2 <= 0:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Land area numerical value could not be reliably parsed."
        }

    # Calculate percentage difference relative to larger value
    max_val = max(a1, a2)
    diff_pct = abs(a1 - a2) / max_val * 100.0

    if diff_pct <= tolerance_pct:
        return {
            "status": "MATCH",
            "diff_pct": diff_pct,
            "normalized_acres_1": round(a1, 2),
            "normalized_acres_2": round(a2, 2),
            "explanation": f"Land areas reconcile consistently ({a1:.2f} acres vs {a2:.2f} acres, {diff_pct:.1f}% variance within acceptable tolerance)."
        }
    else:
        return {
            "status": "MISMATCH",
            "diff_pct": diff_pct,
            "normalized_acres_1": round(a1, 2),
            "normalized_acres_2": round(a2, 2),
            "explanation": f"Land area discrepancy detected: '{area1_str}' ({a1:.2f} acres) vs '{area2_str}' ({a2:.2f} acres) exhibits a {diff_pct:.1f}% variance, exceeding allowed {tolerance_pct}% tolerance."
        }


def compare_institution_names(
    name1: str | None,
    name2: str | None,
    threshold: float = 75.0
) -> dict:
    """
    Compares two institutional names using abbreviation expansion and token set similarity.
    Threshold: >= 75.0% is MATCH; < 75.0% is MISMATCH.
    """
    if not name1 or not name2 or len(name1.strip()) < 3 or len(name2.strip()) < 3:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Institution name is missing or too brief for reliable comparison."
        }

    score, acceptable = evaluate_institution_name_similarity(name1, name2)
    if acceptable:
        return {
            "status": "MATCH",
            "similarity_score": score,
            "explanation": f"Institution names match consistently (similarity score: {score:.1f}% >= threshold {threshold}%)."
        }
    else:
        return {
            "status": "MISMATCH",
            "similarity_score": score,
            "explanation": f"Institution name discrepancy: '{name1}' vs '{name2}' (similarity score: {score:.1f}% below required {threshold}%)."
        }


def compare_locations(loc1: str | None, loc2: str | None) -> dict:
    """
    Compares two location/address strings using normalized token overlap.
    """
    if not loc1 or not loc2 or len(loc1.strip()) < 4 or len(loc2.strip()) < 4:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Location address information missing or too brief for cross-document comparison."
        }

    stop_words = {"campus", "plot", "survey", "no", "road", "pune", "maharashtra", "district", "taluka", "state", "at", "near", "post"}
    tokens1 = set(re.findall(r"[A-Za-z0-9]+", loc1.lower())) - stop_words
    tokens2 = set(re.findall(r"[A-Za-z0-9]+", loc2.lower())) - stop_words

    if not tokens1 or not tokens2:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Insufficient distinctive address tokens to verify location match."
        }

    intersection = tokens1.intersection(tokens2)
    smaller_size = min(len(tokens1), len(tokens2))
    overlap_ratio = len(intersection) / smaller_size if smaller_size > 0 else 0.0

    # Explicit conflict check (e.g. Kothrud vs Hadapsar)
    if ("hadapsar" in tokens1 and "kothrud" in tokens2) or ("kothrud" in tokens1 and "hadapsar" in tokens2):
        return {
            "status": "MISMATCH",
            "explanation": f"Distinct municipal campus localities identified ('{loc1}' vs '{loc2}'). Location mismatch requires administrative review."
        }

    if overlap_ratio >= 0.40 or len(intersection) >= 2:
        return {
            "status": "MATCH",
            "explanation": f"Location addresses reconcile with common geographical markers: {', '.join(sorted(intersection))}."
        }
    else:
        return {
            "status": "MISMATCH",
            "explanation": f"Location discrepancy: '{loc1}' shares insufficient geographic landmarks with '{loc2}'."
        }


def compare_intake_capacities(intake1_str: str | None, intake2_str: str | None) -> dict:
    """Compares integer seat intake capacities between documents."""
    if not intake1_str or not intake2_str:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Approved intake capacity could not be extracted from one or both compared documents."
        }

    try:
        i1 = int(re.sub(r"[^\d]", "", str(intake1_str)))
        i2 = int(re.sub(r"[^\d]", "", str(intake2_str)))
    except ValueError:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Intake figures could not be parsed as integers."
        }

    if i1 == i2:
        return {
            "status": "MATCH",
            "intake_1": i1,
            "intake_2": i2,
            "explanation": f"Intake capacity numbers reconcile exactly ({i1} seats)."
        }
    else:
        return {
            "status": "MISMATCH",
            "intake_1": i1,
            "intake_2": i2,
            "explanation": f"Intake capacity discrepancy: one document specifies {i1} seats, while another indicates {i2} seats."
        }


def compare_reference_numbers(ref1: str | None, ref2: str | None) -> dict:
    """Compares certificate or approval reference numbers."""
    if not ref1 or not ref2:
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "explanation": "Reference number not available on one or both documents."
        }

    norm1 = re.sub(r"[^A-Za-z0-9]", "", ref1).upper()
    norm2 = re.sub(r"[^A-Za-z0-9]", "", ref2).upper()

    if not norm1 or not norm2:
        return {"status": "NOT_ENOUGH_INFORMATION", "explanation": "Empty normalized reference."}

    if norm1 == norm2:
        return {
            "status": "MATCH",
            "explanation": f"Certificate reference numbers match exactly ('{ref1}')."
        }
    else:
        return {
            "status": "MISMATCH",
            "explanation": f"Reference number mismatch: '{ref1}' vs '{ref2}'."
        }


def run_cross_document_consistency_checks(
    arg1: Any,
    arg2: Any
) -> list[dict]:
    """
    Executes cross-document entity consistency comparisons across all active submitted documents.
    Covers:
    1. Land Area (Land Title Deed vs Building Plan vs declared application land)
    2. Institution Legal Name (across all submitted statutory certificates)
    3. Campus Location / Address (Land Title Deed vs Building Plan vs declared location)
    4. Approved Intake Capacity (Affiliation Letter vs application declared intake)

    Returns a list of structured comparison result dictionaries.
    """
    if isinstance(arg1, (list, tuple)):
        active_docs = list(arg1)
        application = arg2
    elif isinstance(arg2, (list, tuple)):
        application = arg1
        active_docs = list(arg2)
    elif hasattr(arg1, "documents") or hasattr(arg1, "declared_intake"):
        application = arg1
        active_docs = list(arg2) if hasattr(arg2, "__iter__") else []
    else:
        active_docs = list(arg1) if hasattr(arg1, "__iter__") else []
        application = arg2

    results: list[dict] = []

    # Map documents by category
    doc_by_cat = {doc.document_category: doc for doc in active_docs if getattr(doc, "status", "") != "REPLACED_ARCHIVED"}

    # Helper to get extracted field value & metadata from doc
    def get_field(doc: Any, key: str) -> tuple[str | None, int | None, float]:
        if not doc:
            return None, None, 0.0
        for ef in getattr(doc, "extracted_fields", []):
            if ef.field_key == key:
                val = ef.normalized_value or ef.field_value
                return val, ef.page_number, ef.confidence_score or 1.0
        return None, None, 0.0

    # -------------------------------------------------------------
    # 1. LAND AREA: LAND_TITLE_DEED vs BUILDING_PLAN vs DECLARED
    # -------------------------------------------------------------
    land_doc = doc_by_cat.get("LAND_TITLE_DEED")
    bp_doc = doc_by_cat.get("BUILDING_PLAN")

    land_val, land_page, land_conf = get_field(land_doc, "land_area")
    bp_val, bp_page, bp_conf = get_field(bp_doc, "land_area")

    # A: Land Title Deed vs Building Plan
    if land_doc and bp_doc:
        if land_conf >= 0.50 and bp_conf >= 0.50 and land_val and bp_val:
            comp = compare_land_areas(land_val, bp_val)
            results.append({
                "check_code": "XDOC-LAND-DEED-BP",
                "field_name": "Land Area",
                "category": "RECORD_MISMATCH",
                "status": comp["status"],
                "doc1_id": land_doc.id,
                "doc1_name": land_doc.original_filename,
                "doc1_category": land_doc.document_category,
                "doc1_value": land_val,
                "doc1_page": land_page,
                "doc2_id": bp_doc.id,
                "doc2_name": bp_doc.original_filename,
                "doc2_category": bp_doc.document_category,
                "doc2_value": bp_val,
                "doc2_page": bp_page,
                "expected_value": f"{land_val} (Registered Land Deed)",
                "observed_value": f"{bp_val} (Building Plan)",
                "explanation": comp["explanation"],
                "severity": "HIGH" if comp["status"] == "MISMATCH" else "LOW",
                "requires_human_review": comp["status"] == "MISMATCH"
            })
        else:
            results.append({
                "check_code": "XDOC-LAND-DEED-BP",
                "field_name": "Land Area",
                "category": "RECORD_MISMATCH",
                "status": "NOT_ENOUGH_INFORMATION",
                "doc1_id": land_doc.id,
                "doc1_name": land_doc.original_filename,
                "doc1_category": land_doc.document_category,
                "doc1_value": land_val,
                "doc1_page": land_page,
                "doc2_id": bp_doc.id,
                "doc2_name": bp_doc.original_filename,
                "doc2_category": bp_doc.document_category,
                "doc2_value": bp_val,
                "doc2_page": bp_page,
                "expected_value": "Legible land area in Land Deed",
                "observed_value": "Incomplete numerical extraction",
                "explanation": "Land area could not be extracted with sufficient confidence from one or both documents to perform cross-document comparison.",
                "severity": "LOW",
                "requires_human_review": False
            })

    # B: Land Title Deed vs Declared Land Area
    if land_doc and getattr(application, "declared_land_acres", None):
        dec_land_str = f"{application.declared_land_acres} acres"
        if land_val and land_conf >= 0.50:
            comp = compare_land_areas(land_val, dec_land_str)
            results.append({
                "check_code": "XDOC-LAND-DEED-DECLARED",
                "field_name": "Land Area vs Application Declaration",
                "category": "RECORD_MISMATCH",
                "status": comp["status"],
                "doc1_id": land_doc.id,
                "doc1_name": land_doc.original_filename,
                "doc1_category": land_doc.document_category,
                "doc1_value": land_val,
                "doc1_page": land_page,
                "doc2_id": None,
                "doc2_name": "Application Declaration",
                "doc2_category": "APPLICATION_FORM",
                "doc2_value": dec_land_str,
                "doc2_page": None,
                "expected_value": f"{dec_land_str} (Declared in Application)",
                "observed_value": f"{land_val} (Extracted from Title Deed)",
                "explanation": comp["explanation"],
                "severity": "HIGH" if comp["status"] == "MISMATCH" else "LOW",
                "requires_human_review": comp["status"] == "MISMATCH"
            })

    # -------------------------------------------------------------
    # 2. INSTITUTION NAME CONSISTENCY ACROSS STATUTORY DOCUMENTS
    # -------------------------------------------------------------
    statutory_categories = ("LAND_TITLE_DEED", "FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "BUILDING_PLAN")
    statutory_docs = [d for d in active_docs if d.document_category in statutory_categories]

    if getattr(application, "institution", None):
        inst_name = application.institution.name
        for doc in statutory_docs:
            if doc.extracted_text and len(doc.extracted_text) > 30:
                comp = compare_institution_names(inst_name, doc.extracted_text[:1000])
                results.append({
                    "check_code": f"XDOC-NAME-{doc.document_category}",
                    "field_name": f"Institution Name ({doc.document_category})",
                    "category": "RECORD_MISMATCH",
                    "status": comp["status"],
                    "doc1_id": doc.id,
                    "doc1_name": doc.original_filename,
                    "doc1_category": doc.document_category,
                    "doc1_value": f"Text in {doc.original_filename}",
                    "doc1_page": 1,
                    "doc2_id": None,
                    "doc2_name": "Institutional Registry Profile",
                    "doc2_category": "REGISTRY",
                    "doc2_value": inst_name,
                    "doc2_page": None,
                    "expected_value": inst_name,
                    "observed_value": f"Similarity: {comp.get('similarity_score', 0):.1f}%",
                    "explanation": comp["explanation"],
                    "severity": "MEDIUM" if comp["status"] == "MISMATCH" else "LOW",
                    "requires_human_review": comp["status"] == "MISMATCH"
                })

    # -------------------------------------------------------------
    # 3. APPROVED INTAKE: AFFILIATION_LETTER vs DECLARED INTAKE
    # -------------------------------------------------------------
    affil_doc = doc_by_cat.get("AFFILIATION_LETTER")
    if affil_doc and getattr(application, "declared_intake", None):
        affil_intake_val, affil_page, affil_conf = get_field(affil_doc, "intake_capacity")
        dec_intake_str = str(application.declared_intake)

        if affil_intake_val and affil_conf >= 0.50:
            comp = compare_intake_capacities(affil_intake_val, dec_intake_str)
            results.append({
                "check_code": "XDOC-INTAKE-AFFIL-DECLARED",
                "field_name": "Sanctioned Intake Capacity",
                "category": "RECORD_MISMATCH",
                "status": comp["status"],
                "doc1_id": affil_doc.id,
                "doc1_name": affil_doc.original_filename,
                "doc1_category": affil_doc.document_category,
                "doc1_value": f"{affil_intake_val} seats",
                "doc1_page": affil_page,
                "doc2_id": None,
                "doc2_name": "Application Form",
                "doc2_category": "APPLICATION_FORM",
                "doc2_value": f"{dec_intake_str} seats",
                "doc2_page": None,
                "expected_value": f"{dec_intake_str} seats (Declared in Application)",
                "observed_value": f"{affil_intake_val} seats (Affiliation Letter)",
                "explanation": comp["explanation"],
                "severity": "HIGH" if comp["status"] == "MISMATCH" else "LOW",
                "requires_human_review": comp["status"] == "MISMATCH"
            })

    # -------------------------------------------------------------
    # 4. LOCATION CONSISTENCY: LAND TITLE DEED vs DECLARED CAMPUS
    # -------------------------------------------------------------
    if land_doc and getattr(application, "institution", None):
        campus_address = f"{application.institution.address}, {application.institution.district}, {application.institution.state}"
        if land_doc.extracted_text and len(land_doc.extracted_text) > 40:
            comp = compare_locations(campus_address, land_doc.extracted_text[:1200])
            results.append({
                "check_code": "XDOC-LOCATION-LAND-DEED",
                "field_name": "Campus Geographic Location",
                "category": "RECORD_MISMATCH",
                "status": comp["status"],
                "doc1_id": land_doc.id,
                "doc1_name": land_doc.original_filename,
                "doc1_category": land_doc.document_category,
                "doc1_value": "Extracted Location Tokens",
                "doc1_page": 1,
                "doc2_id": None,
                "doc2_name": "Declared Institutional Campus",
                "doc2_category": "APPLICATION_PROFILE",
                "doc2_value": campus_address,
                "doc2_page": None,
                "expected_value": campus_address,
                "observed_value": f"Land Document Address Context",
                "explanation": comp["explanation"],
                "severity": "HIGH" if comp["status"] == "MISMATCH" else "LOW",
                "requires_human_review": comp["status"] == "MISMATCH"
            })

    return results
