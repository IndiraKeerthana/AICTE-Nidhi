from PIL import Image
from typing import Any
from app.services.anomaly_service import compute_image_phash, compare_perceptual_hashes

INFRASTRUCTURE_CATEGORIES = {
    "LAB_INFRASTRUCTURE_PHOTO",
    "CAMPUS_INFRASTRUCTURE_PHOTO",
    "BUILDING_ELEVATION_PHOTO"
}


def review_infrastructure_evidence(
    storage_path: str,
    evidence_category: str = "LAB_INFRASTRUCTURE_PHOTO"
) -> dict:
    """
    Evaluates infrastructure photographic evidence using genuine digital properties:
    - Verifies image integrity and readability
    - Inspects resolution (minimum threshold: 600x400)
    - Computes perceptual hash (64-bit DCT pHash) for duplicate/reuse screening
    - Assesses whether visual evidence is sufficient or requires physical Expert Visit Committee (EVC) inspection.

    Outcomes:
    - VERIFIED: Image meets quality and resolution criteria.
    - INSUFFICIENT_EVIDENCE: Image resolution is too low (< 600x400) for visual evidence verification.
    - CHECK_FAILED: File is unreadable or corrupted.
    - EXPERT_INSPECTION_REQUIRED: Automated photo inspection cannot confirm physical machinery specs or calibration; EVC inspection recommended.
    """
    review_result = {
        "outcome": "VERIFIED",
        "status": "PASSED",
        "evidence_category": evidence_category,
        "width": 0,
        "height": 0,
        "aspect_ratio": 0.0,
        "phash": None,
        "requires_human_review": False,
        "is_evc_recommended": False,
        "evidence_reviewed": "",
        "notes": "Image resolution and evidence properties meet quality threshold."
    }

    try:
        with Image.open(storage_path) as img:
            w, h = img.size
            review_result["width"] = w
            review_result["height"] = h
            review_result["aspect_ratio"] = round(w / h, 2) if h > 0 else 0.0
            phash_val = compute_image_phash(storage_path)
            review_result["phash"] = phash_val
            review_result["evidence_reviewed"] = f"Photograph format {img.format}, dimensions {w}x{h} pixels, aspect ratio {review_result['aspect_ratio']}, pHash {phash_val or 'N/A'}."

            # Quality checks
            if w < 600 or h < 400:
                review_result["outcome"] = "INSUFFICIENT_EVIDENCE"
                review_result["status"] = "MANUAL_REVIEW"
                review_result["requires_human_review"] = True
                review_result["is_evc_recommended"] = True
                review_result["notes"] = (
                    f"Image resolution ({w}x{h}) is below the standard evidence threshold (600x400). "
                    "Photograph lacks sufficient detail to inspect computing terminals or equipment; physical inspection or higher-resolution replacement required."
                )
            else:
                review_result["outcome"] = "VERIFIED"
                review_result["status"] = "PASSED"
                review_result["notes"] = (
                    f"Photograph verified for digital clarity ({w}x{h} pixels, pHash computed). "
                    "Note: Preliminary document check verifies image properties only; it does not replace statutory physical inspection."
                )

    except Exception as e:
        review_result["outcome"] = "CHECK_FAILED"
        review_result["status"] = "FAILED"
        review_result["requires_human_review"] = True
        review_result["notes"] = f"Infrastructure photographic evidence could not be processed: {str(e)}"
        review_result["evidence_reviewed"] = f"Processing attempt error: {str(e)}"

    return review_result


def check_cross_slot_photo_reuse(documents: list) -> list[dict]:
    """
    Scans uploaded documents with perceptual hashes.
    If Hamming distance <= 4 between two different categories, flags reused infrastructure photo!
    """
    anomalies = []
    photo_docs = [d for d in documents if getattr(d, "phash_value", None) and getattr(d, "status", "") != "REPLACED_ARCHIVED"]

    for i in range(len(photo_docs)):
        for j in range(i + 1, len(photo_docs)):
            doc1 = photo_docs[i]
            doc2 = photo_docs[j]
            dist = compare_perceptual_hashes(doc1.phash_value, doc2.phash_value)
            if dist <= 4:
                anomalies.append({
                    "doc1_id": doc1.id,
                    "doc1_name": doc1.original_filename,
                    "doc1_category": doc1.document_category,
                    "doc2_id": doc2.id,
                    "doc2_name": doc2.original_filename,
                    "doc2_category": doc2.document_category,
                    "hamming_distance": dist,
                    "severity": "HIGH",
                    "explanation": (
                        f"Perceptual image hash match (Hamming distance {dist}) detected between "
                        f"'{doc1.original_filename}' ({doc1.document_category}) and '{doc2.original_filename}' ({doc2.document_category}). "
                        "Potential reused laboratory or campus photograph."
                    )
                })

    return anomalies


def evaluate_application_infrastructure(
    application: Any,
    active_docs: list[Any]
) -> list[dict]:
    """
    Evaluates infrastructure photographic evidence submitted for an application:
    - Filters applicable infrastructure evidence documents (e.g. LAB_INFRASTRUCTURE_PHOTO)
    - If no infrastructure photos are submitted:
      - If category is INCREASE_INTAKE / NEW_INSTITUTE where labs are relevant, records status
      - If category does not require photos, returns NOT_APPLICABLE
    - For each submitted photo:
      - Runs review_infrastructure_evidence
      - Recommends Expert Visit Committee (EVC) review where appropriate without fabricating physical measurements
    """
    results = []
    infra_docs = [d for d in active_docs if getattr(d, "document_category", "") in INFRASTRUCTURE_CATEGORIES or (getattr(d, "mime_type", "") or "").startswith("image/")]

    app_category = getattr(application, "category", "")

    if not infra_docs:
        # Check if infrastructure evidence is relevant to this application category
        if app_category in ("INCREASE_INTAKE", "NEW_INSTITUTE"):
            results.append({
                "check_code": "INFRA-PHOTO-REVIEW",
                "category": "INFRASTRUCTURE",
                "status": "NOT_APPLICABLE",
                "outcome": "NOT_APPLICABLE",
                "doc_id": None,
                "doc_name": None,
                "expected_value": "Optional laboratory infrastructure photographs",
                "observed_value": "No photographs uploaded",
                "explanation": "No laboratory infrastructure photographs submitted (designated as optional evidence under current handbook ruleset).",
                "severity": "LOW",
                "requires_human_review": False,
                "is_evc_recommended": False
            })
        return results

    for doc in infra_docs:
        storage_path = getattr(doc, "storage_path", None)
        if not storage_path:
            continue

        res = review_infrastructure_evidence(storage_path, doc.document_category)
        is_insufficient = res["outcome"] == "INSUFFICIENT_EVIDENCE"
        is_failed = res["outcome"] == "CHECK_FAILED"

        results.append({
            "check_code": f"INFRA-PHOTO-{doc.id}",
            "category": "INFRASTRUCTURE",
            "status": res["status"],
            "outcome": res["outcome"],
            "doc_id": doc.id,
            "doc_name": doc.original_filename,
            "expected_value": "High-resolution laboratory/campus photo (>= 600x400)",
            "observed_value": f"{res['width']}x{res['height']} px (pHash: {res['phash'][:8] if res.get('phash') else 'N/A'}...)",
            "explanation": res["notes"],
            "severity": "MEDIUM" if is_insufficient else ("HIGH" if is_failed else "LOW"),
            "requires_human_review": res["requires_human_review"],
            "is_evc_recommended": res["is_evc_recommended"]
        })

    return results
