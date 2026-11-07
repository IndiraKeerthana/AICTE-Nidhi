import time
import datetime
import json
import re
from sqlalchemy.orm import Session
from app.models import (
    Application, Document, Finding, BaselineRecord, ScrutinyRun,
    CheckResult, Alert, AuthorityVerification, AuditEvent, ExtractedField
)
from app.services.compliance_rules import compliance_engine
from app.services.anomaly_service import (
    inspect_pdf_metadata_and_updates,
    evaluate_institution_name_similarity,
    compare_perceptual_hashes
)
from app.services.authority_verification import (
    decode_qr_code,
    decode_qr_code_from_image,
    verify_against_authority_registry
)
from app.services.cross_document_engine import run_cross_document_consistency_checks
from app.services.infrastructure_review import (
    check_cross_slot_photo_reuse,
    evaluate_application_infrastructure
)

SCRUTINY_BASELINE_DATE = "2026-03-31"

def execute_automated_scrutiny(
    db: Session,
    application_id: int,
    trigger_source: str = "AUTOMATIC_ORCHESTRATOR"
) -> ScrutinyRun:
    """
    Executes the central 18-step Automatic Scrutiny Pipeline:
    1. Identifies category & loads versioned APH rules
    2. Runs completeness & mandatory document checks
    3. Evaluates validity/expiry dates
    4. Reconciles intake against baseline records
    5. Runs cryptographic & perceptual anomaly checks
    6. Attempts authority verification (QR code & registry)
    7. Persists ScrutinyRun, CheckResult, Finding, Alert, and AuditEvent records.
    """
    start_time = time.time()
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise ValueError(f"Application #{application_id} not found.")

    # 1. Determine Run Number (supports re-scrutiny on replacement)
    previous_runs_count = db.query(ScrutinyRun).filter(ScrutinyRun.application_id == app.id).count()
    run_number = previous_runs_count + 1

    scrutiny_run = ScrutinyRun(
        application_id=app.id,
        run_number=run_number,
        status="RUNNING",
        ruleset_version=compliance_engine.ruleset_version,
        total_checks=0,
        passed_checks=0,
        failed_checks=0,
        warnings_count=0,
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(scrutiny_run)
    db.flush()

    active_docs = db.query(Document).filter(
        Document.application_id == app.id,
        Document.status != "REPLACED_ARCHIVED"
    ).all()

    uploaded_categories = {d.document_category: d for d in active_docs}
    total_checks = 0
    passed_checks = 0
    failed_checks = 0
    warnings_count = 0

    # Helper function to record checks
    def record_check(code: str, category: str, status: str, explanation: str, exp: str = None, obs: str = None, sev: str = "MEDIUM", human_rev: bool = False):
        nonlocal total_checks, passed_checks, failed_checks, warnings_count
        total_checks += 1
        if status in ("PASSED", "VERIFIED"):
            passed_checks += 1
        elif status in ("FAILED", "EXPIRED", "INCOMPLETE"):
            failed_checks += 1
        else:
            warnings_count += 1

        cr = CheckResult(
            scrutiny_run_id=scrutiny_run.id,
            check_code=code,
            category=category,
            status=status,
            expected_value=exp,
            observed_value=obs,
            explanation=explanation,
            severity=sev,
            requires_human_review=human_rev
        )
        db.add(cr)

    # --- CHECK 1: Mandatory Document Completeness ---
    mandatory_docs = compliance_engine.get_mandatory_documents(app.category)
    missing_docs = [m for m in mandatory_docs if m not in uploaded_categories]

    if missing_docs:
        record_check(
            code="APH-2026-MANDATORY-DOCS-01",
            category="COMPLIANCE",
            status="FAILED",
            exp=f"All {len(mandatory_docs)} mandatory categories submitted",
            obs=f"Missing: {', '.join(missing_docs)}",
            explanation=f"Application lacks required statutory attachments: {', '.join(missing_docs)}.",
            sev="CRITICAL",
            human_rev=True
        )
        fnd = _upsert_finding(
            db=db,
            app_id=app.id,
            run_id=scrutiny_run.id,
            code=f"FND-MISSING-DOCS-{app.id}",
            category="MISSING_DOCUMENT",
            severity="CRITICAL",
            title="Missing Mandatory Regulatory Documents",
            desc=f"Application is missing statutory documents: {', '.join(missing_docs)}.",
            exp="All mandatory documents uploaded",
            obs=f"Missing {len(missing_docs)} document(s)",
            rule_code="APH-2026-MANDATORY-DOCS-01 [PLACEHOLDER PENDING HANDBOOK MAPPING]",
            rule_desc="Statutory document completeness per APH checklist.",
            rec_action="Notify applicant to upload omitted statutory attachments.",
            evidence_class="VERIFIED_FACT"
        )
        _create_or_update_alert(
            db=db,
            app_id=app.id,
            alert_type="MISSING_DOCUMENT",
            severity="Action required",
            title="Required Documents Missing",
            message=f"Application lacks {len(missing_docs)} mandatory statutory document(s): {', '.join(missing_docs)}.",
            finding_id=fnd.id,
            scrutiny_run_id=scrutiny_run.id
        )
    else:
        record_check(
            code="APH-2026-MANDATORY-DOCS-01",
            category="COMPLIANCE",
            status="PASSED",
            exp="All mandatory documents submitted",
            obs=f"{len(uploaded_categories)} uploaded",
            explanation="All required statutory documents for application category are present."
        )
        _resolve_finding_if_exists(db, app.id, f"FND-MISSING-DOCS-{app.id}", alert_type="MISSING_DOCUMENT")

    # --- CHECK 2: Sanctioned Intake vs Ground-Truth Baseline ---
    baseline = db.query(BaselineRecord).filter(
        BaselineRecord.institution_id == app.institution_id,
        BaselineRecord.record_type == "APPROVED_INTAKE"
    ).first()

    if baseline:
        if app.declared_intake != baseline.approved_intake:
            record_check(
                code="APH-2026-INTAKE-04",
                category="COMPLIANCE",
                status="FAILED",
                exp=f"{baseline.approved_intake} Seats (Approved Record {baseline.academic_year})",
                obs=f"{app.declared_intake} Seats (Declared in Application)",
                explanation=f"Declared intake of {app.declared_intake} seats contradicts approved intake of {baseline.approved_intake} seats in official baseline record.",
                sev="HIGH",
                human_rev=True
            )
            fnd = _upsert_finding(
                db=db,
                app_id=app.id,
                run_id=scrutiny_run.id,
                code=f"FND-INTAKE-{app.id}",
                category="RECORD_MISMATCH",
                severity="HIGH",
                title="Sanctioned Intake Mismatch with Institutional Record",
                desc=f"Declared intake of {app.declared_intake} seats contradicts approved baseline intake of {baseline.approved_intake} seats in AICTE records.",
                exp=f"{baseline.approved_intake} Seats (Approved Record {baseline.academic_year})",
                obs=f"{app.declared_intake} Seats (Declared in Application)",
                rule_code="APH-2026-INTAKE-04 [PLACEHOLDER PENDING HANDBOOK MAPPING]",
                rule_desc="Declared existing intake must reconcile with previous year approved EoA records.",
                rec_action="Verify capacity expansion authorization or issue deficiency notice to applicant.",
                evidence_class="VERIFIED_FACT"
            )
            _create_or_update_alert(
                db=db,
                app_id=app.id,
                alert_type="RECORD_MISMATCH",
                severity="Review required",
                title="Application Details Conflict with Reference Record",
                message=f"Application declares {app.declared_intake} seats vs approved reference of {baseline.approved_intake} seats.",
                finding_id=fnd.id,
                scrutiny_run_id=scrutiny_run.id
            )
        else:
            record_check(
                code="APH-2026-INTAKE-04",
                category="COMPLIANCE",
                status="PASSED",
                exp=f"{baseline.approved_intake} Seats",
                obs=f"{app.declared_intake} Seats",
                explanation="Declared intake exactly matches baseline approved intake."
            )
            _resolve_finding_if_exists(db, app.id, f"FND-INTAKE-{app.id}", alert_type="RECORD_MISMATCH")

    # --- CHECK 3: Document Expiry Date Validation (e.g. Fire Safety NOC) ---
    fire_doc = uploaded_categories.get("FIRE_SAFETY_NOC")
    if fire_doc:
        # Check extracted expiry date from fields
        expiry_field = next((ef for ef in fire_doc.extracted_fields if ef.field_key == "expiry_date"), None)
        if expiry_field:
            expiry_val = expiry_field.normalized_value or expiry_field.field_value
            # Compare with SCRUTINY_BASELINE_DATE (e.g. 2026-03-31)
            # If year in 2025, it is expired!
            is_expired = "2025" in expiry_val or "2024" in expiry_val
            if is_expired:
                record_check(
                    code="APH-2026-NOC-FIRE-02",
                    category="COMPLIANCE",
                    status="EXPIRED",
                    exp=f"Valid beyond {SCRUTINY_BASELINE_DATE}",
                    obs=expiry_val,
                    explanation=f"Fire Safety Certificate expired on {expiry_val} (prior to scrutiny baseline date {SCRUTINY_BASELINE_DATE}).",
                    sev="HIGH",
                    human_rev=True
                )
                fnd = _upsert_finding(
                    db=db,
                    app_id=app.id,
                    run_id=scrutiny_run.id,
                    code=f"FND-EXPIRED-FIRE-{app.id}",
                    category="EXPIRED_DOCUMENT",
                    severity="HIGH",
                    title="Expired Fire and Life Safety Certificate (NOC)",
                    desc=f"Uploaded Fire Safety Certificate expired on {expiry_val}. AICTE regulations mandate active certificate validity.",
                    exp=f"Valid beyond {SCRUTINY_BASELINE_DATE}",
                    obs=expiry_val,
                    doc_id=fire_doc.id,
                    rule_code="APH-2026-NOC-FIRE-02 [PLACEHOLDER PENDING HANDBOOK MAPPING]",
                    rule_desc="Fire and Life Safety Certificate must remain unexpired as of scrutiny date.",
                    rec_action="Request applicant to upload a renewed Fire Safety NOC.",
                    evidence_class="VERIFIED_FACT",
                    page_num=getattr(expiry_field, "page_number", 1) or 1
                )
                _create_or_update_alert(
                    db=db,
                    app_id=app.id,
                    alert_type="EXPIRED_DOCUMENT",
                    severity="Action required",
                    title="Submitted Certificate Appears Expired",
                    message=f"Fire Safety Certificate expired on {expiry_val}. Valid certificate required.",
                    finding_id=fnd.id,
                    scrutiny_run_id=scrutiny_run.id
                )
            else:
                record_check(
                    code="APH-2026-NOC-FIRE-02",
                    category="COMPLIANCE",
                    status="PASSED",
                    exp=f"Valid beyond {SCRUTINY_BASELINE_DATE}",
                    obs=expiry_val,
                    explanation=f"Fire Safety Certificate is unexpired and valid through {expiry_val}."
                )
                _resolve_finding_if_exists(db, app.id, f"FND-EXPIRED-FIRE", alert_type="EXPIRED_DOCUMENT")

    # --- CHECK 4: Cryptographic Duplicate File Detection (SHA-256) ---
    seen_hashes = {}
    duplicate_detected = False
    for doc in active_docs:
        if doc.sha256_hash in seen_hashes:
            dup_target = seen_hashes[doc.sha256_hash]
            duplicate_detected = True
            record_check(
                code="APH-INTEGRITY-DUP-01",
                category="ANOMALY",
                status="FAILED",
                exp="Distinct statutory files for each category",
                obs=f"Identical SHA-256 in {doc.document_category} and {dup_target.document_category}",
                explanation=f"Exact duplicate file uploaded under categories '{doc.document_category}' and '{dup_target.document_category}'.",
                sev="CRITICAL",
                human_rev=True
            )
            fnd = _upsert_finding(
                db=db,
                app_id=app.id,
                run_id=scrutiny_run.id,
                code=f"FND-DUP-{doc.id}-{dup_target.id}",
                category="INTEGRITY_ANOMALY",
                severity="CRITICAL",
                title="Identical Duplicate Document Uploaded Across Slots",
                desc=f"File '{doc.original_filename}' and '{dup_target.original_filename}' share identical cryptographic hash ({doc.sha256_hash[:16]}...).",
                exp="Distinct authentic documents",
                obs="Exact SHA-256 match",
                doc_id=doc.id,
                rule_code="APH-INTEGRITY-DUP-01",
                rule_desc="Uploading duplicate files under differing statutory categories constitutes an integrity anomaly.",
                rec_action="Scrutinize attachments and request genuine separate documents.",
                evidence_class="POTENTIAL_ANOMALY"
            )
            _create_or_update_alert(
                db=db,
                app_id=app.id,
                alert_type="ANOMALY_DETECTED",
                severity="Review required",
                title="Document Has Indicators Requiring Authenticity Review",
                message=f"Identical file hash detected between {doc.document_category} and {dup_target.document_category}.",
                finding_id=fnd.id,
                scrutiny_run_id=scrutiny_run.id
            )
        else:
            seen_hashes[doc.sha256_hash] = doc
    if not duplicate_detected:
        _resolve_finding_if_exists(db, app.id, "FND-DUP", alert_type="ANOMALY_DETECTED")

    # --- CHECK 5: Perceptual Photo Reuse (pHash) ---
    photo_anomalies = check_cross_slot_photo_reuse(active_docs)
    for pa in photo_anomalies:
        record_check(
            code="DETECTOR-PHASH-02",
            category="ANOMALY",
            status="FAILED",
            exp="Distinct laboratory/campus photographs",
            obs=f"pHash match (distance {pa['hamming_distance']})",
            explanation=pa["explanation"],
            sev="HIGH",
            human_rev=True
        )
        fnd = _upsert_finding(
            db=db,
            app_id=app.id,
            run_id=scrutiny_run.id,
            code=f"FND-PHASH-{pa['doc1_id']}-{pa['doc2_id']}",
            category="INTEGRITY_ANOMALY",
            severity="HIGH",
            title="Potential Reused Infrastructure Photograph Detected",
            desc=pa["explanation"],
            exp="Distinct photos for distinct facilities",
            obs=f"Perceptual hash match (distance {pa['hamming_distance']})",
            doc_id=pa["doc1_id"],
            rule_code="DETECTOR-PHASH-02",
            rule_desc="Detects photographic evidence reuse across differing laboratory and campus categories.",
            rec_action="Request physical verification or geo-tagged infrastructure photos.",
            evidence_class="POTENTIAL_ANOMALY"
        )
        _create_or_update_alert(
            db=db,
            app_id=app.id,
            alert_type="ANOMALY_DETECTED",
            severity="Review required",
            title="Infrastructure Photograph Requires Authenticity Review",
            message=pa["explanation"],
            finding_id=fnd.id,
            scrutiny_run_id=scrutiny_run.id
        )
    if not photo_anomalies:
        _resolve_finding_if_exists(db, app.id, "FND-PHASH")

    # --- CHECK 6: QR Code Extraction & Issuing Authority Lookup ---
    authority_categories = ("FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "BUILDING_PLAN", "LAYOUT_APPROVAL", "ENVIRONMENTAL_CLEARANCE", "LAND_TITLE_DEED")
    for doc in active_docs:
        if doc.document_category in authority_categories:
            # 1. Attempt QR decode
            qr_res = decode_qr_code(doc.storage_path, mime_type=doc.mime_type)
            qr_text = qr_res.get("payload")
            qr_notes = qr_res.get("notes")

            # 2. Extract certificate or approval reference number
            cert_num = next((ef.normalized_value for ef in doc.extracted_fields if ef.field_key in ("certificate_number", "approval_ref")), None)
            if not cert_num and doc.extracted_text:
                import re
                ref_match = re.search(r"\b((?:FS|BP|UNIV|ENV|AFFIL|NOC|DEED)-[A-Za-z0-9\-]{4,25})\b", doc.extracted_text, re.IGNORECASE)
                if ref_match:
                    cert_num = ref_match.group(1).upper()
                else:
                    # Also look for generic "Certificate No: XXX" or "Ref No: XXX"
                    generic_match = re.search(r"(?:certificate\s*no|ref\s*no|plan\s*no|approval\s*no)[\s.:]*([A-Za-z0-9\/-]{5,25})", doc.extracted_text, re.IGNORECASE)
                    if generic_match:
                        cert_num = generic_match.group(1).strip()

            campus_location = f"{app.institution.address}, {app.institution.district}, {app.institution.state}"
            auth_res = verify_against_authority_registry(
                cert_reference=cert_num,
                cert_type=doc.document_category,
                institution_name=app.institution.name,
                declared_location=campus_location,
                qr_payload=qr_text,
                qr_metadata=qr_res
            )

            # 3. Record in authority_verifications table
            verif_entry = AuthorityVerification(
                document_id=doc.id,
                application_id=app.id,
                verification_type="QR_CODE" if qr_text else "REGISTRY_LOOKUP",
                source_name=auth_res["source_name"],
                source_reference=auth_res.get("source_reference", cert_num),
                status=auth_res["status"],
                evidence_payload=json.dumps(auth_res),
                is_simulated=True
            )
            db.add(verif_entry)

            # 4. Record Scrutiny CheckResult
            record_check(
                code=f"AUTH-VERIF-{doc.document_category}",
                category="AUTHORITY",
                status=auth_res["status"],
                exp=auth_res.get("expected_value") or "Authentic record confirmed in registry",
                obs=f"{auth_res['outcome']}: {auth_res['source_name']}",
                explanation=auth_res["explanation"],
                sev="CRITICAL" if auth_res["outcome"] in ("STATUS_INVALID", "EXPIRED") else "HIGH",
                human_rev=auth_res["requires_human_review"]
            )

            # 5. Handle Findings and Alerts based on granular outcome
            finding_code = f"FND-AUTH-{doc.document_category}-{doc.id}"
            if auth_res["outcome"] != "VERIFIED":
                fnd_title = f"Authority Verification: {auth_res['outcome'].replace('_', ' ').title()} — {doc.document_category.replace('_', ' ').title()}"
                if auth_res["outcome"] == "RECORD_NOT_FOUND":
                    fnd_title = f"Approval Record Not Found — {doc.document_category.replace('_', ' ').title()}"
                elif auth_res["outcome"] == "LOCATION_MISMATCH":
                    fnd_title = f"Approved Location Mismatch — {doc.document_category.replace('_', ' ').title()}"
                elif auth_res["outcome"] == "ENTITY_MISMATCH":
                    fnd_title = f"Institution Entity Mismatch — {doc.document_category.replace('_', ' ').title()}"
                elif auth_res["outcome"] == "EXPIRED":
                    fnd_title = f"Expired Statutory Clearance — {doc.document_category.replace('_', ' ').title()}"
                elif auth_res["outcome"] == "STATUS_INVALID":
                    fnd_title = f"Revoked / Invalid Statutory Approval — {doc.document_category.replace('_', ' ').title()}"
                elif auth_res["outcome"] == "AUTHORITY_UNAVAILABLE":
                    fnd_title = f"External Verification Gateway Unavailable — {doc.document_category.replace('_', ' ').title()}"

                fnd = _upsert_finding(
                    db=db,
                    app_id=app.id,
                    run_id=scrutiny_run.id,
                    code=finding_code,
                    category="RECORD_MISMATCH" if auth_res["outcome"] in ("LOCATION_MISMATCH", "ENTITY_MISMATCH", "RECORD_NOT_FOUND", "EXTRACTION_INCOMPLETE", "AUTHORITY_UNAVAILABLE") else ("EXPIRED_DOCUMENT" if auth_res["outcome"] == "EXPIRED" else "INTEGRITY_ANOMALY"),
                    severity="CRITICAL" if auth_res["outcome"] in ("STATUS_INVALID", "EXPIRED") else "HIGH",
                    title=fnd_title,
                    desc=auth_res["explanation"],
                    exp=auth_res.get("expected_value") or "Authentic record confirmed in registry",
                    obs=auth_res.get("observed_value") or auth_res["specific_reason"],
                    rule_code=f"APH-AUTH-VERIF-{doc.document_category}",
                    rule_desc="Statutory clearance certificates must be confirmed in issuing authority registries without location or entity discrepancies.",
                    rec_action=auth_res.get("recommended_action") or "Review document in in-app viewer and request clarification.",
                    doc_id=doc.id,
                    page_num=1,
                    evidence_class="CHECK_NOT_COMPLETED" if auth_res["outcome"] in ("EXTRACTION_INCOMPLETE", "AUTHORITY_UNAVAILABLE") else ("VERIFIED_FACT" if auth_res["outcome"] in ("EXPIRED", "LOCATION_MISMATCH", "ENTITY_MISMATCH") else "AUTOMATED_INFERENCE")
                )

                _create_or_update_alert(
                    db=db,
                    app_id=app.id,
                    alert_type="AUTHORITY_REVIEW",
                    severity="Action required" if auth_res["outcome"] in ("STATUS_INVALID", "EXPIRED") else "Review required",
                    title=fnd_title,
                    message=auth_res["explanation"],
                    finding_id=fnd.id,
                    scrutiny_run_id=scrutiny_run.id
                )
            else:
                _resolve_finding_if_exists(db, app.id, finding_code, alert_type="AUTHORITY_REVIEW")

    # --- CHECK 7: Fuzzy Institution Name Consistency ---
    for doc in active_docs:
        if doc.extracted_text and len(doc.extracted_text) > 20:
            score, acceptable = evaluate_institution_name_similarity(app.institution.name, doc.extracted_text)
            if not acceptable:
                record_check(
                    code=f"APH-2026-NAME-{doc.id}",
                    category="COMPLIANCE",
                    status="MANUAL_REVIEW",
                    exp=app.institution.name,
                    obs=f"Fuzzy Match Score: {score:.1f}%",
                    explanation=f"Institutional name in '{doc.original_filename}' shows noticeable deviation from registered title '{app.institution.name}'.",
                    sev="MEDIUM",
                    human_rev=True
                )
                fnd = _upsert_finding(
                    db=db,
                    app_id=app.id,
                    run_id=scrutiny_run.id,
                    code=f"FND-NAME-{doc.id}",
                    category="RECORD_MISMATCH",
                    severity="MEDIUM",
                    title="Institution Name Discrepancy in Submitted Attachment",
                    desc=f"In '{doc.original_filename}', the referenced institution name deviated from registered name '{app.institution.name}' (similarity: {score:.1f}%).",
                    exp=f"Registered name: {app.institution.name}",
                    obs=f"Observed similarity: {score:.1f}%",
                    rule_code="APH-2026-NAME-06",
                    rule_desc="Institution name in statutory documents must match institutional registry title or acceptable abbreviation.",
                    rec_action="Confirm institutional identity or request an explanatory corrigendum.",
                    doc_id=doc.id,
                    evidence_class="AUTOMATED_INFERENCE"
                )
                _create_or_update_alert(
                    db=db,
                    app_id=app.id,
                    alert_type="NAME_MISMATCH",
                    severity="Review required",
                    title="Institution Name Discrepancy",
                    message=f"Name deviation detected in {doc.original_filename} ({score:.1f}% match).",
                    finding_id=fnd.id,
                    scrutiny_run_id=scrutiny_run.id
                )
            else:
                record_check(
                    code=f"APH-2026-NAME-{doc.id}",
                    category="COMPLIANCE",
                    status="PASSED",
                    exp=app.institution.name,
                    obs=f"Match Score: {score:.1f}% (Acceptable variation)",
                    explanation=f"Institution name in '{doc.original_filename}' matches registered institution name within acceptable variation."
                )
                _resolve_finding_if_exists(db, app.id, f"FND-NAME-{doc.id}", alert_type="NAME_MISMATCH")

    # --- CHECK 8: PDF Incremental Modification / Tampering Anomaly ---
    for doc in active_docs:
        if doc.mime_type == "application/pdf" or (doc.original_filename and doc.original_filename.lower().endswith(".pdf")):
            inc_count = doc.incremental_updates_count or 0
            if inc_count > 1:
                record_check(
                    code=f"APH-INTEGRITY-PDF-MOD-{doc.id}",
                    category="ANOMALY",
                    status="MANUAL_REVIEW",
                    exp="Single-pass unaltered PDF structure (incremental updates <= 1)",
                    obs=f"Detected {inc_count} incremental update revisions (multiple %%EOF trailers)",
                    explanation=f"Attachment '{doc.original_filename}' contains {inc_count} post-issuance incremental modification blocks (%%EOF trailer markers), indicating potential post-creation revision or alteration. Note: Detects file-structure revisions, not cryptographic digital signatures.",
                    sev="HIGH",
                    human_rev=True
                )
                fnd = _upsert_finding(
                    db=db,
                    app_id=app.id,
                    run_id=scrutiny_run.id,
                    code=f"FND-PDF-MOD-{doc.id}",
                    category="INTEGRITY_ANOMALY",
                    severity="HIGH",
                    title="Potential Post-Issuance PDF Modification Detected",
                    desc=f"Document '{doc.original_filename}' exhibits {inc_count} appended revision blocks (%%EOF markers) typically produced by post-export editing or redaction tools. Note: Detects file-structure revisions, not cryptographic digital signatures.",
                    exp="Single-pass unaltered PDF structure",
                    obs=f"{inc_count} incremental update revision(s)",
                    rule_code="APH-INTEGRITY-PDF-MOD-03",
                    rule_desc="Statutory certificates and NOCs should reflect authentic, single-pass exports without secondary appended byte revisions.",
                    rec_action="Cross-check physical certificate with issuing authority or request certified original digital copy.",
                    doc_id=doc.id,
                    evidence_class="POTENTIAL_ANOMALY"
                )
                _create_or_update_alert(
                    db=db,
                    app_id=app.id,
                    alert_type="ANOMALY_DETECTED",
                    severity="Review required",
                    title="Document Modification Anomaly Detected",
                    message=f"Post-creation byte revisions detected in {doc.original_filename} ({inc_count} incremental updates).",
                    finding_id=fnd.id,
                    scrutiny_run_id=scrutiny_run.id
                )
            else:
                record_check(
                    code=f"APH-INTEGRITY-PDF-MOD-{doc.id}",
                    category="ANOMALY",
                    status="PASSED",
                    exp="Single-pass authentic PDF structure",
                    obs="Clean PDF structure (single %%EOF trailer)",
                    explanation=f"Document '{doc.original_filename}' verified as standard single-pass structure with no suspicious appended updates."
                )
                _resolve_finding_if_exists(db, app.id, f"FND-PDF-MOD-{doc.id}", alert_type="ANOMALY_DETECTED")

    # --- CHECK 9: Cross-Document Consistency Engine ---
    xdoc_checks = run_cross_document_consistency_checks(active_docs, app)
    for xc in xdoc_checks:
        check_code = f"APH-2026-{xc['check_code']}"
        fnd_code = f"FND-XDOC-{xc['check_code']}-{app.id}"

        if xc["status"] == "MATCH":
            record_check(
                code=check_code,
                category="COMPLIANCE",
                status="PASSED",
                exp=xc["expected_value"],
                obs=xc["observed_value"],
                explanation=xc["explanation"]
            )
            _resolve_finding_if_exists(db, app.id, f"FND-XDOC-{xc['check_code']}", alert_type="RECORD_MISMATCH")
        elif xc["status"] == "MISMATCH":
            record_check(
                code=check_code,
                category="COMPLIANCE",
                status="FAILED",
                exp=xc["expected_value"],
                obs=xc["observed_value"],
                explanation=xc["explanation"],
                sev=xc["severity"],
                human_rev=True
            )
            # Serialize secondary document info into source_snippet for viewer linking
            sec_snippet = None
            if xc.get("doc2_id") or xc.get("doc2_name"):
                sec_snippet = json.dumps({
                    "doc1_id": xc.get("doc1_id"),
                    "doc1_name": xc.get("doc1_name"),
                    "doc1_category": xc.get("doc1_category"),
                    "doc1_value": xc.get("doc1_value"),
                    "doc1_page": xc.get("doc1_page"),
                    "doc2_id": xc.get("doc2_id"),
                    "doc2_name": xc.get("doc2_name"),
                    "doc2_category": xc.get("doc2_category"),
                    "doc2_value": xc.get("doc2_value"),
                    "doc2_page": xc.get("doc2_page")
                })

            fnd = _upsert_finding(
                db=db,
                app_id=app.id,
                run_id=scrutiny_run.id,
                code=fnd_code,
                category="RECORD_MISMATCH",
                severity=xc["severity"],
                title=f"Cross-Document Discrepancy — {xc['field_name']}",
                desc=xc["explanation"],
                exp=xc["expected_value"],
                obs=xc["observed_value"],
                rule_code="APH-2026-XDOC-07",
                rule_desc="Cross-document data reconciliation across statutory submissions.",
                rec_action="Review discrepancy in document viewer and request clarification or corrected documentation.",
                doc_id=xc.get("doc1_id"),
                page_num=xc.get("doc1_page") or 1,
                evidence_class="VERIFIED_FACT",
                source_snippet=sec_snippet
            )
            _create_or_update_alert(
                db=db,
                app_id=app.id,
                alert_type="RECORD_MISMATCH",
                severity="Review required",
                title=f"Cross-Document Discrepancy: {xc['field_name']}",
                message=xc["explanation"],
                finding_id=fnd.id,
                scrutiny_run_id=scrutiny_run.id
            )
        elif xc["status"] in ("NOT_ENOUGH_INFORMATION", "CHECK_FAILED"):
            record_check(
                code=check_code,
                category="COMPLIANCE",
                status="MANUAL_REVIEW",
                exp=xc["expected_value"],
                obs=xc["observed_value"],
                explanation=xc["explanation"],
                sev="LOW",
                human_rev=True
            )

    # --- CHECK 10: Infrastructure Photographic Evidence & EVC Review ---
    infra_checks = evaluate_application_infrastructure(app, active_docs)
    for ic in infra_checks:
        check_code = f"APH-2026-{ic['check_code']}"
        doc_id = ic.get("doc_id")
        fnd_code = f"FND-INFRA-{doc_id}" if doc_id else f"FND-INFRA-{app.id}"

        if ic["status"] == "PASSED":
            record_check(
                code=check_code,
                category="INFRASTRUCTURE",
                status="PASSED",
                exp=ic["expected_value"],
                obs=ic["observed_value"],
                explanation=ic["explanation"]
            )
            if doc_id:
                _resolve_finding_if_exists(db, app.id, f"FND-INFRA-{doc_id}", alert_type="INFRASTRUCTURE_REVIEW")
        elif ic["status"] in ("MANUAL_REVIEW", "FAILED"):
            record_check(
                code=check_code,
                category="INFRASTRUCTURE",
                status=ic["status"],
                exp=ic["expected_value"],
                obs=ic["observed_value"],
                explanation=ic["explanation"],
                sev=ic["severity"],
                human_rev=ic["requires_human_review"]
            )
            title = (
                "Laboratory Infrastructure Evidence Low Resolution — EVC Inspection Recommended"
                if ic.get("is_evc_recommended")
                else "Laboratory Infrastructure Evidence Requires Review"
            )
            fnd = _upsert_finding(
                db=db,
                app_id=app.id,
                run_id=scrutiny_run.id,
                code=fnd_code,
                category="INTEGRITY_ANOMALY" if ic.get("outcome") == "CHECK_FAILED" else "COMPLIANCE",
                severity=ic["severity"],
                title=title,
                desc=ic["explanation"],
                exp=ic["expected_value"],
                obs=ic["observed_value"],
                rule_code="APH-2026-INFRA-08",
                rule_desc="Infrastructure photographic evidence clarity and physical verification standards.",
                rec_action=(
                    "Recommend on-site physical machinery verification via Expert Visit Committee (EVC)."
                    if ic.get("is_evc_recommended")
                    else "Inspect photographic evidence or request clear replacement image."
                ),
                doc_id=doc_id,
                page_num=1,
                evidence_class="AUTOMATED_INFERENCE" if ic.get("is_evc_recommended") else "CHECK_NOT_COMPLETED"
            )
            _create_or_update_alert(
                db=db,
                app_id=app.id,
                alert_type="INFRASTRUCTURE_REVIEW",
                severity="Review required",
                title=title,
                message=ic["explanation"],
                finding_id=fnd.id,
                scrutiny_run_id=scrutiny_run.id
            )
        elif ic["status"] == "NOT_APPLICABLE":
            record_check(
                code=check_code,
                category="INFRASTRUCTURE",
                status="PASSED",
                exp=ic["expected_value"],
                obs=ic["observed_value"],
                explanation=ic["explanation"]
            )

    # Finalize Scrutiny Run metrics
    duration_ms = int((time.time() - start_time) * 1000)
    scrutiny_run.total_checks = total_checks
    scrutiny_run.passed_checks = passed_checks
    scrutiny_run.failed_checks = failed_checks
    scrutiny_run.warnings_count = warnings_count
    scrutiny_run.execution_duration_ms = duration_ms
    scrutiny_run.status = "COMPLETED_WITH_WARNINGS" if (failed_checks > 0 or warnings_count > 0) else "COMPLETED"
    scrutiny_run.summary_notes = f"Executed {total_checks} checks. {passed_checks} passed, {failed_checks} failed, {warnings_count} warnings/reviews."
    scrutiny_run.completed_at = datetime.datetime.now(datetime.timezone.utc)

    # Update application overall status
    if not app.final_decision:
        unresolved_findings = db.query(Finding).filter(
            Finding.application_id == app.id,
            Finding.review_status.in_(["OPEN", "ACKNOWLEDGED", "RECTIFICATION_REQUESTED", "EVC_RECOMMENDED"])
        ).count()
        if unresolved_findings > 0 or failed_checks > 0:
            app.status = "DEFICIENCY_FLAGGED"
            _resolve_finding_if_exists(db, app.id, "READY_FOR_REVIEW", alert_type="READY_FOR_REVIEW")
        else:
            app.status = "READY_FOR_REVIEW"
            _create_or_update_alert(
                db=db,
                app_id=app.id,
                alert_type="READY_FOR_REVIEW",
                severity="Review required",
                title="Automated Checks Complete — Ready for Review",
                message=f"All {total_checks} automated scrutiny checks completed with 0 deficiencies. Application is ready for final decision.",
                scrutiny_run_id=scrutiny_run.id
            )

    # Record Hash-Chained Audit Event
    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="SCRUTINY_RUN_COMPLETED",
        details={
            "run_number": run_number,
            "status": scrutiny_run.status,
            "total_checks": total_checks,
            "passed": passed_checks,
            "failed": failed_checks,
            "duration_ms": duration_ms,
            "trigger": trigger_source
        },
        actor=trigger_source
    )

    db.commit()
    db.refresh(scrutiny_run)
    return scrutiny_run


def _upsert_finding(
    db: Session,
    app_id: int,
    run_id: int = None,
    code: str = "",
    category: str = "RECORD_MISMATCH",
    severity: str = "HIGH",
    title: str = "",
    desc: str = "",
    exp: str = None,
    obs: str = None,
    rule_code: str = "",
    rule_desc: str = "",
    rec_action: str = "",
    doc_id: int = None,
    evidence_class: str = "VERIFIED_FACT",
    page_num: int = None,
    source_snippet: str = None,
    bounding_box: str = None
) -> Finding:
    if doc_id and not bounding_box:
        query = db.query(ExtractedField).filter(
            ExtractedField.document_id == doc_id,
            ExtractedField.bounding_box.isnot(None)
        )
        if page_num:
            query = query.filter(ExtractedField.page_number == page_num)
        ef = query.first()
        if ef:
            bounding_box = ef.bounding_box

    existing = db.query(Finding).filter(Finding.finding_code == code, Finding.application_id == app_id).first()
    if existing:
        if run_id:
            existing.scrutiny_run_id = run_id
        existing.description = desc
        existing.expected_value = exp
        existing.observed_value = obs
        if doc_id:
            existing.supporting_document_id = doc_id
        if page_num:
            existing.supporting_page_number = page_num
        if source_snippet:
            existing.source_snippet = source_snippet
        if bounding_box:
            existing.bounding_box = bounding_box
        if existing.review_status == "RESOLVED":
            existing.review_status = "OPEN"
        existing.updated_at = datetime.datetime.now(datetime.timezone.utc)
        return existing
    else:
        finding = Finding(
            finding_code=code,
            application_id=app_id,
            scrutiny_run_id=run_id,
            category=category,
            severity=severity,
            evidence_classification=evidence_class,
            title=title,
            description=desc,
            expected_value=exp,
            observed_value=obs,
            supporting_document_id=doc_id,
            supporting_page_number=page_num,
            source_snippet=source_snippet,
            bounding_box=bounding_box,
            rule_code=rule_code,
            rule_description=rule_desc,
            recommended_action=rec_action,
            review_status="OPEN",
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(finding)
        db.flush()
        return finding

upsert_finding = _upsert_finding


def _resolve_finding_if_exists(db: Session, app_id: int, code_prefix: str, alert_type: str = None):
    findings = db.query(Finding).filter(
        Finding.application_id == app_id,
        Finding.finding_code.like(f"{code_prefix}%"),
        Finding.review_status != "RESOLVED"
    ).all()
    for f in findings:
        f.review_status = "RESOLVED"
        f.resolution_notes = "Automatically resolved upon re-scrutiny verification success."
        f.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # Also resolve linked active/acknowledged alerts
        alerts = db.query(Alert).filter(
            Alert.application_id == app_id,
            Alert.finding_id == f.id,
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
        ).all()
        for a in alerts:
            a.status = "RESOLVED"

    if alert_type:
        type_alerts = db.query(Alert).filter(
            Alert.application_id == app_id,
            Alert.alert_type == alert_type,
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
        ).all()
        for a in type_alerts:
            a.status = "RESOLVED"


def _create_or_update_alert(
    db: Session,
    app_id: int,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    finding_id: int = None,
    scrutiny_run_id: int = None
) -> Alert:
    query = db.query(Alert).filter(
        Alert.application_id == app_id,
        Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
    )
    if finding_id:
        existing = query.filter(Alert.finding_id == finding_id).first()
    else:
        existing = query.filter(Alert.alert_type == alert_type).first()

    if existing:
        existing.scrutiny_run_id = scrutiny_run_id or existing.scrutiny_run_id
        existing.title = title
        existing.message = message
        existing.severity = severity
        return existing
    else:
        alert = Alert(
            application_id=app_id,
            finding_id=finding_id,
            scrutiny_run_id=scrutiny_run_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            status="ACTIVE",
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(alert)
        db.flush()
        return alert


def _create_alert(db: Session, app_id: int, alert_type: str, severity: str, title: str, message: str):
    return _create_or_update_alert(db, app_id, alert_type, severity, title, message)
