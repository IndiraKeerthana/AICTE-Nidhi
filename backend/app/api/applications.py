import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    Application, Institution, Document, Finding, ReviewerAction,
    AuditEvent, BaselineRecord, ScrutinyRun, Alert, AuthorityVerification
)
from app.schemas import (
    ApplicationCreate, ApplicationResponse, ApplicationDetailResponse,
    DocumentChecklistItem, ScrutinyReportGrouped, CheckResultResponse,
    DeficiencyNoticePayload
)
from app.api.auth import get_current_user, require_role, UserInfo
from app.services.baseline_service import ensure_baseline_records, get_institution_baseline
from app.services.orchestrator import execute_automated_scrutiny, upsert_finding
from app.services.compliance_rules import compliance_engine

router = APIRouter(prefix="/applications", tags=["Applications"])

CATEGORY_DOC_TITLES = {
    "LAND_TITLE_DEED": "Land Registered Title Deed & Conversion Order",
    "BUILDING_PLAN": "Approved Building Plan & Built-up Area Certificate",
    "FIRE_SAFETY_NOC": "Fire and Life Safety Certificate (NOC)",
    "AFFILIATION_LETTER": "University Affiliation Order & Sanction Letter",
    "FACULTY_ROSTER": "Faculty Cadre Roster & Qualifications Sheet",
    "BALANCE_SHEET": "Audited Annual Financial Balance Sheet",
    "LAB_INFRASTRUCTURE_PHOTO": "Laboratory Equipment & Campus Infrastructure Photograph",
    "BOARD_RESOLUTION": "Governing Board Resolution for Approval Application"
}

@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    # Enforce role-based access: APPLICANT only sees their own institution's applications
    if current_user.role == "APPLICANT":
        if not current_user.institution_id:
            return []
        apps = (
            db.query(Application)
            .join(Institution)
            .filter(Institution.aicte_permanent_id == current_user.institution_id)
            .order_by(Application.created_at.desc())
            .all()
        )
    else:
        # Officer / Approver / Admin see all applications
        apps = db.query(Application).order_by(Application.created_at.desc()).all()

    results = []
    for app in apps:
        app_dict = {
            "id": app.id,
            "application_number": app.application_number,
            "tracking_id": app.tracking_id,
            "institution_id": app.institution_id,
            "category": app.category,
            "academic_year": app.academic_year,
            "status": app.status,
            "declared_programme": app.declared_programme,
            "declared_course": app.declared_course,
            "declared_intake": app.declared_intake,
            "declared_land_acres": app.declared_land_acres,
            "institution": app.institution,
            "documents_count": len([d for d in app.documents if d.status != "REPLACED_ARCHIVED"]),
            "findings_count": len([f for f in app.findings if f.review_status != "RESOLVED"]),
            "final_decision": app.final_decision,
            "decided_by": app.decided_by,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
        }
        results.append(app_dict)
    return results


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    # If applicant, ensure AICTE ID matches their institution
    if current_user.role == "APPLICANT" and current_user.institution_id:
        if payload.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You may only submit applications for your registered institution ({current_user.institution_id})."
            )

    # 1. Ensure institution & synthetic baseline records exist
    institution = ensure_baseline_records(
        db=db,
        aicte_id=payload.aicte_permanent_id,
        inst_name=payload.institution_name
    )

    # 2. Generate unique application number and tracking ID
    app_num = f"APP-2026-{uuid.uuid4().hex[:6].upper()}"
    tracking_id = f"TRK-{uuid.uuid4().hex[:12].upper()}"

    # 3. Create application
    app = Application(
        application_number=app_num,
        tracking_id=tracking_id,
        institution_id=institution.id,
        category=payload.category,
        academic_year=payload.academic_year,
        status="SUBMITTED",
        declared_programme=payload.declared_programme,
        declared_course=payload.declared_course,
        declared_intake=payload.declared_intake,
        declared_land_acres=payload.declared_land_acres or 8.25,
    )
    db.add(app)
    db.flush()

    # 4. Record Hash-Chained Audit Event
    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="APPLICATION_CREATED",
        details={
            "application_number": app_num,
            "tracking_id": tracking_id,
            "institution": institution.name,
            "declared_intake": payload.declared_intake,
            "category": payload.category
        },
        actor=current_user.full_name or "APPLICANT_PORTAL"
    )

    # 5. Run automatic preliminary scrutiny orchestrator
    execute_automated_scrutiny(db, app.id, trigger_source="INITIAL_APPLICATION_SUBMISSION")

    db.commit()
    db.refresh(app)

    return {
        "id": app.id,
        "application_number": app.application_number,
        "tracking_id": app.tracking_id,
        "institution_id": app.institution_id,
        "category": app.category,
        "academic_year": app.academic_year,
        "status": app.status,
        "declared_programme": app.declared_programme,
        "declared_course": app.declared_course,
        "declared_intake": app.declared_intake,
        "declared_land_acres": app.declared_land_acres,
        "institution": app.institution,
        "documents_count": len(app.documents),
        "findings_count": len(app.findings),
        "final_decision": app.final_decision,
        "decided_by": app.decided_by,
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


@router.get("/{id}", response_model=ApplicationDetailResponse)
def get_application(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Enforce applicant access restriction
    if current_user.role == "APPLICANT" and current_user.institution_id:
        if app.institution.aicte_permanent_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access restricted: You may only view applications submitted by your own institution."
            )

    baseline = get_institution_baseline(db, app.institution_id)

    # Active documents map
    active_docs_list = [d for d in app.documents if d.status != "REPLACED_ARCHIVED"]
    active_docs = {d.document_category: d for d in active_docs_list}

    # Format document previews
    doc_responses = []
    for doc in app.documents:
        preview = (doc.extracted_text[:200] + "...") if doc.extracted_text and len(doc.extracted_text) > 200 else doc.extracted_text
        doc_responses.append({
            "id": doc.id,
            "application_id": doc.application_id,
            "document_category": doc.document_category,
            "original_filename": doc.original_filename,
            "file_size_bytes": doc.file_size_bytes,
            "mime_type": doc.mime_type,
            "sha256_hash": doc.sha256_hash,
            "phash_value": doc.phash_value,
            "status": doc.status,
            "page_count": doc.page_count,
            "extracted_text_preview": preview,
            "uploaded_at": doc.uploaded_at
        })

    # Format audit events
    audit_responses = []
    for event in app.audit_events:
        try:
            details_dict = json.loads(event.details_json)
        except Exception:
            details_dict = {"raw": event.details_json}

        audit_responses.append({
            "id": event.id,
            "application_id": event.application_id,
            "event_type": event.event_type,
            "details": details_dict,
            "actor": event.actor,
            "previous_hash": event.previous_hash,
            "event_hash": event.event_hash,
            "created_at": event.created_at
        })

    # Format scrutiny runs
    runs_responses = []
    latest_run = None
    for run in app.scrutiny_runs:
        latest_run = run
        runs_responses.append({
            "id": run.id,
            "run_number": run.run_number,
            "status": run.status,
            "ruleset_version": run.ruleset_version,
            "total_checks": run.total_checks,
            "passed_checks": run.passed_checks,
            "failed_checks": run.failed_checks,
            "warnings_count": run.warnings_count,
            "execution_duration_ms": run.execution_duration_ms,
            "summary_notes": run.summary_notes,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "check_results": [
                {
                    "id": c.id,
                    "check_code": c.check_code,
                    "category": c.category,
                    "status": c.status,
                    "expected_value": c.expected_value,
                    "observed_value": c.observed_value,
                    "explanation": c.explanation,
                    "severity": c.severity,
                    "requires_human_review": c.requires_human_review
                } for c in run.check_results
            ]
        })

    # Build Section B: Submitted Documents Checklist
    mandatory_codes = compliance_engine.get_mandatory_documents(app.category)
    all_cat_codes = list(mandatory_codes)
    for cat in compliance_engine.config.get("categories", []):
        if cat.get("code") == app.category:
            for opt in cat.get("conditional_documents", []):
                opt_code = opt.get("code") if isinstance(opt, dict) else opt
                if opt_code and opt_code not in all_cat_codes:
                    all_cat_codes.append(opt_code)
            for opt in cat.get("optional_documents", []):
                opt_code = opt.get("code") if isinstance(opt, dict) else opt
                if opt_code and opt_code not in all_cat_codes:
                    all_cat_codes.append(opt_code)

    # Also include any uploaded document that might not be in standard list
    for doc_cat in active_docs.keys():
        if doc_cat not in all_cat_codes:
            all_cat_codes.append(doc_cat)

    checklist_items = []
    for cat_code in all_cat_codes:
        is_mand = cat_code in mandatory_codes
        is_subm = cat_code in active_docs
        doc = active_docs.get(cat_code)

        doc_title = CATEGORY_DOC_TITLES.get(cat_code, cat_code.replace("_", " ").title())
        ext_summary = None
        validity = None
        verif_status = "MISSING" if is_mand else "NOT_SUBMITTED"
        verif_source = None
        verif_evidence = None

        if is_subm and doc:
            # Gather extracted info
            fields = {ef.field_key: ef.field_value for ef in doc.extracted_fields}
            if fields:
                ext_summary = ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in list(fields.items())[:3]])
            elif doc.extracted_text:
                ext_summary = (doc.extracted_text[:120] + "...") if len(doc.extracted_text) > 120 else doc.extracted_text
            else:
                ext_summary = "Text extraction complete"

            # Check validity
            if "expiry_date" in fields:
                exp_date = fields["expiry_date"]
                if "2025" in exp_date or "2024" in exp_date:
                    validity = f"Expired on {exp_date}"
                    verif_status = "EXPIRED"
                else:
                    validity = f"Valid through {exp_date}"
            elif "valid_till" in fields:
                validity = f"Valid till {fields['valid_till']}"
            else:
                validity = "Statutory record / Non-expiring"

            # Check authority verification
            auth_v = db.query(AuthorityVerification).filter(
                AuthorityVerification.document_id == doc.id
            ).first()

            if doc.status == "EXTRACTION_FAILED" or (doc.ocr_needed and (not doc.extracted_text or "Incomplete extraction" in doc.extracted_text)):
                verif_status = "UNREADABLE"
                verif_source = "Local Inspection Engine"
                verif_evidence = doc.extracted_text or "Document text could not be extracted cleanly from scanned image."
            elif auth_v:
                verif_source = f"{auth_v.source_name} [DEMO/SIMULATED]" if auth_v.is_simulated else auth_v.source_name
                verif_evidence = auth_v.evidence_payload
                if auth_v.status == "SOURCE_UNAVAILABLE":
                    verif_status = "VERIFICATION_UNAVAILABLE"
                elif auth_v.status == "EXPIRED":
                    verif_status = "EXPIRED"
                elif auth_v.status == "VERIFIED":
                    verif_status = "VERIFIED"
                else:
                    verif_status = auth_v.status
            else:
                # Check if document has associated open finding
                has_finding = any(
                    f.supporting_document_id == doc.id and f.review_status != "RESOLVED"
                    for f in app.findings
                )
                if has_finding:
                    verif_status = "INCONSISTENT"
                    verif_source = "AICTE Automated Scrutiny Rules"
                    verif_evidence = "Automated compliance checks noted potential discrepancies requiring verification."
                elif verif_status not in ("EXPIRED", "UNREADABLE"):
                    verif_status = "VERIFIED"
                    verif_source = "AICTE Preliminary Scrutiny Engine"
                    verif_evidence = "Document structure and declared fields successfully reconciled."

        checklist_items.append(DocumentChecklistItem(
            category_code=cat_code,
            document_name=doc_title,
            is_mandatory=is_mand,
            is_submitted=is_subm,
            document_id=doc.id if doc else None,
            original_filename=doc.original_filename if doc else None,
            status=verif_status,
            extracted_summary=ext_summary,
            validity_info=validity,
            verification_result=verif_status,
            verification_source=verif_source,
            verification_evidence=verif_evidence,
            stream_url=f"/api/documents/{doc.id}/stream" if doc else None
        ))

    # Active Deficiency Notice
    active_deficiency_notice = None
    if app.status == "DEFICIENCY_FLAGGED" or any(f.review_status == "RECTIFICATION_REQUESTED" for f in app.findings):
        last_action = db.query(ReviewerAction).filter(
            ReviewerAction.application_id == app.id,
            ReviewerAction.action_type == "REQUEST_DEFICIENCY"
        ).order_by(ReviewerAction.created_at.desc()).first()

        last_audit = db.query(AuditEvent).filter(
            AuditEvent.application_id == app.id,
            AuditEvent.event_type == "DEFICIENCY_NOTICE_ISSUED"
        ).order_by(AuditEvent.created_at.desc()).first()

        req_cats = []
        if last_audit:
            try:
                ad = json.loads(last_audit.details_json)
                req_cats = ad.get("document_categories") or []
            except Exception:
                pass

        rect_finding_ids = [f.id for f in app.findings if f.review_status == "RECTIFICATION_REQUESTED"]

        if last_action:
            active_deficiency_notice = {
                "is_active": True,
                "instructions": last_action.justification_remarks,
                "issued_by": last_action.reviewer_name,
                "issued_at": last_action.created_at,
                "requested_categories": req_cats,
                "finding_ids": rect_finding_ids
            }
        elif last_audit:
            try:
                ad = json.loads(last_audit.details_json)
                inst = ad.get("instructions", "Rectification requested by scrutiny officer.")
            except Exception:
                inst = "Rectification requested by scrutiny officer."
            active_deficiency_notice = {
                "is_active": True,
                "instructions": inst,
                "issued_by": last_audit.actor,
                "issued_at": last_audit.created_at,
                "requested_categories": req_cats,
                "finding_ids": rect_finding_ids
            }

    # Build Section C: Grouped Scrutiny Report
    grouped_report = ScrutinyReportGrouped()
    if latest_run and latest_run.check_results:
        for c in latest_run.check_results:
            c_resp = CheckResultResponse(
                id=c.id,
                check_code=c.check_code,
                category=c.category,
                status=c.status,
                expected_value=c.expected_value,
                observed_value=c.observed_value,
                explanation=c.explanation,
                severity=c.severity,
                requires_human_review=c.requires_human_review
            )
            if c.status == "PASSED":
                grouped_report.passed_checks.append(c_resp)
            elif c.status in ("FAILED", "EXPIRED", "INCOMPLETE") and c.severity in ("CRITICAL", "HIGH"):
                grouped_report.issues_requiring_correction.append(c_resp)
            elif c.status in ("SOURCE_UNAVAILABLE", "UNREADABLE", "SKIPPED"):
                grouped_report.checks_could_not_be_completed.append(c_resp)
            else:
                grouped_report.items_requiring_officer_review.append(c_resp)

    return {
        "id": app.id,
        "application_number": app.application_number,
        "tracking_id": app.tracking_id,
        "institution_id": app.institution_id,
        "category": app.category,
        "academic_year": app.academic_year,
        "status": app.status,
        "declared_programme": app.declared_programme,
        "declared_course": app.declared_course,
        "declared_intake": app.declared_intake,
        "declared_land_acres": app.declared_land_acres,
        "institution": app.institution,
        "documents_count": len(doc_responses),
        "findings_count": len([f for f in app.findings if f.review_status != "RESOLVED"]),
        "final_decision": app.final_decision,
        "decided_by": app.decided_by,
        "documents": doc_responses,
        "findings": app.findings,
        "reviewer_actions": app.reviewer_actions,
        "audit_events": audit_responses,
        "scrutiny_runs": runs_responses,
        "alerts": app.alerts,
        "baseline_record": baseline,
        "document_checklist": checklist_items,
        "grouped_scrutiny_report": grouped_report,
        "active_deficiency_notice": active_deficiency_notice,
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


@router.post("/{id}/deficiency-notice")
def issue_deficiency_notice(
    id: int,
    payload: DeficiencyNoticePayload,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Officer Action: Issues formal deficiency notice to the applicant institution,
    selecting specific findings and entering instructions.
    """
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if app.status in ("APPROVED", "REJECTED") or app.final_decision in ("RECOMMEND_APPROVAL", "RECOMMEND_REJECTION"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application has already been finalized ({app.final_decision or app.status}). Return application to review before issuing new deficiency notices."
        )

    finding_ids = payload.finding_ids or []
    document_categories = payload.document_categories or []

    if not finding_ids and not document_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select at least one finding or document category for correction."
        )

    officer_name = payload.officer_name or current_user.full_name or "Officer"
    target_findings = []

    # 1. Fetch any findings directly requested by finding_ids
    if finding_ids:
        found = db.query(Finding).filter(
            Finding.application_id == app.id,
            Finding.id.in_(finding_ids)
        ).all()
        target_findings.extend(found)

    # 2. For requested document categories, link or create deficiency findings
    for cat in document_categories:
        cat_finding = None
        for f in app.findings:
            if f.supporting_document and f.supporting_document.document_category == cat:
                cat_finding = f
                break
            elif cat in f.finding_code:
                cat_finding = f
                break

        if cat_finding:
            if cat_finding not in target_findings:
                target_findings.append(cat_finding)
        else:
            doc_obj = db.query(Document).filter(
                Document.application_id == app.id,
                Document.document_category == cat,
                Document.status != "REPLACED_ARCHIVED"
            ).first()
            new_fnd = upsert_finding(
                db=db,
                app_id=app.id,
                run_id=None,
                code=f"FND-DEFICIENCY-{cat}-{app.id}",
                category="MISSING_DOCUMENT" if not doc_obj else "RECORD_MISMATCH",
                severity="HIGH",
                title=f"Deficiency Notice: {cat.replace('_', ' ').title()}",
                desc=payload.instructions,
                exp=f"Valid statutory document for {cat.replace('_', ' ').title()}",
                obs="Replacement or correction requested by scrutiny officer",
                rule_code=f"APH-DEFICIENCY-{cat}",
                rule_desc=f"Document compliance deficiency noted by officer for {cat}.",
                rec_action="Upload replacement statutory document in requested category.",
                doc_id=doc_obj.id if doc_obj else None,
                page_num=1 if doc_obj else None,
                evidence_class="VERIFIED_FACT"
            )
            if new_fnd not in target_findings:
                target_findings.append(new_fnd)

    for f in target_findings:
        f.review_status = "RECTIFICATION_REQUESTED"
        f.resolution_notes = payload.instructions

        action = ReviewerAction(
            application_id=app.id,
            finding_id=f.id,
            action_type="REQUEST_DEFICIENCY",
            justification_remarks=payload.instructions,
            reviewer_name=officer_name
        )
        db.add(action)

    app.status = "DEFICIENCY_FLAGGED"

    # Create or update official alert
    existing_alert = db.query(Alert).filter(
        Alert.application_id == app.id,
        Alert.alert_type == "DEFICIENCY_NOTICE",
        Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
    ).first()

    notice_msg = f"{officer_name} requested corrections: {payload.instructions}"
    if document_categories:
        notice_msg += f" (Categories: {', '.join(document_categories)})"

    if existing_alert:
        existing_alert.message = notice_msg
        existing_alert.severity = "Action required"
    else:
        alert = Alert(
            application_id=app.id,
            alert_type="DEFICIENCY_NOTICE",
            severity="Action required",
            title=f"Deficiency Notice Issued ({app.application_number})",
            message=notice_msg,
            status="ACTIVE"
        )
        db.add(alert)

    # Chained audit event
    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="DEFICIENCY_NOTICE_ISSUED",
        details={
            "finding_count": len(target_findings),
            "finding_codes": [f.finding_code for f in target_findings],
            "document_categories": document_categories,
            "instructions": payload.instructions,
            "officer": officer_name
        },
        actor=officer_name
    )

    db.commit()
    return {
        "message": f"Deficiency notice successfully issued with {len(target_findings)} required corrections.",
        "application_number": app.application_number,
        "status": app.status,
        "requested_categories": document_categories,
        "finding_ids": [f.id for f in target_findings]
    }


@router.post("/{id}/return-to-review")
def return_to_review(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    """
    Officer Action: Returns application to active scrutiny review after applicant rectifications,
    re-running automated checks.
    """
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    officer_name = current_user.full_name or "Scrutiny Officer"

    # Reset final decision state if application was previously decided
    app.final_decision = None
    app.decided_by = None
    app.decided_at = None
    app.decision_remarks = None

    # Re-run automated scrutiny
    run = execute_automated_scrutiny(db, app.id, trigger_source="OFFICER_RETURN_TO_REVIEW")

    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="APPLICATION_RETURNED_TO_REVIEW",
        details={
            "scrutiny_run_number": run.run_number,
            "officer": officer_name
        },
        actor=officer_name
    )

    db.commit()
    return {
        "message": f"Application returned to review. Scrutiny run #{run.run_number} completed.",
        "run_number": run.run_number,
        "run_status": run.status,
        "application_status": app.status
    }


@router.post("/{id}/verify")
def trigger_verification(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "APPROVER", "ADMIN"))
):
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    run = execute_automated_scrutiny(db, app.id, trigger_source="MANUAL_OFFICER_RE_RUN")
    return {
        "message": "Automated scrutiny pipeline completed.",
        "run_number": run.run_number,
        "status": run.status,
        "total_checks": run.total_checks,
        "passed_checks": run.passed_checks,
        "failed_checks": run.failed_checks,
        "duration_ms": run.execution_duration_ms
    }
