"""
AICTE NIDHI — Realistic Demonstration Scenarios Engine
Implements three distinct, fully-persisted, realistic newly submitted application scenarios:
1. Scenario 1 (APP-2026-SARASWATI-001): Complete Submission, Ready for Approval (0 deficiencies, eligible).
2. Scenario 2 (APP-2026-PRAGATI-002): Missing Documents (Missing Fire NOC & Affiliation Order, blocked).
3. Scenario 3 (APP-2026-VANGUARD-003): Flagged for Review (Intake mismatch, expired Fire NOC, location mismatch, blocked).

All records are persisted with real generated PDF files in the storage vault,
scanned/processed through document_parser, and evaluated by execute_automated_scrutiny.
"""

import os
import io
import json
import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import fitz  # PyMuPDF
import qrcode

from app.config import settings
from app.models import (
    Institution, BaselineRecord, Application, Document,
    ExtractedField, Finding, CheckResult, ScrutinyRun,
    Alert, AuditEvent, AuthorityVerification
)
from app.services.storage import calculate_sha256
from app.services.document_parser import extract_document_content
from app.services.orchestrator import execute_automated_scrutiny
from app.api.decision import validate_approval_eligibility


def render_pdf_with_qr(
    destination_path: Path,
    header_agency: str,
    document_title: str,
    fields: list[tuple[str, str]],
    body_paragraphs: list[str],
    qr_payload: str | None = None,
    watermark_text: str | None = None
) -> int:
    """
    Renders an authentic-looking statutory government/university document
    in PDF format using PyMuPDF and embeds an authentic QR code image.
    Returns total page count.
    """
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 595 x 842 points

    # Outer and inner border
    page.draw_rect(fitz.Rect(32, 32, 563, 810), color=(0.70, 0.75, 0.82), width=1.5)
    page.draw_rect(fitz.Rect(36, 36, 559, 806), color=(0.88, 0.90, 0.94), width=0.75)

    # Top Synthetic Demo Header Banner
    page.draw_rect(fitz.Rect(38, 38, 557, 56), color=(0.94, 0.96, 0.98), fill=(0.94, 0.96, 0.98))
    page.insert_text(
        (46, 50),
        "AICTE NIDHI EVALUATION DEMO  •  SYNTHETIC REGULATORY DATASET",
        fontsize=8,
        color=(0.35, 0.42, 0.52),
        fontname="helv"
    )

    # Authority / Agency Header
    y = 80
    page.insert_text(
        (46, y),
        header_agency.upper(),
        fontsize=11,
        color=(0.15, 0.20, 0.30),
        fontname="helv"
    )
    y += 18
    page.insert_text(
        (46, y),
        document_title.upper(),
        fontsize=13,
        color=(0.08, 0.12, 0.22),
        fontname="helv"
    )
    page.draw_line(fitz.Point(46, y + 6), fitz.Point(400, y + 6), color=(0.15, 0.25, 0.45), width=1.5)

    # Embed QR Code if provided (placed top right)
    if qr_payload:
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(qr_payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_bytes = buf.getvalue()

        # Place QR in top-right box
        qr_rect = fitz.Rect(440, 68, 540, 168)
        page.draw_rect(fitz.Rect(436, 64, 544, 182), color=(0.85, 0.88, 0.92), width=0.5)
        page.insert_image(qr_rect, stream=qr_bytes)
        page.insert_text((442, 178), "DIGITAL QR SEAL", fontsize=7, color=(0.4, 0.45, 0.55), fontname="helv")

    y += 35

    # Insert Key-Value Fields
    for label, value in fields:
        page.insert_text((46, y), f"{label}:", fontsize=10, color=(0.25, 0.30, 0.40), fontname="helv")
        page.insert_text((200, y), str(value), fontsize=10, color=(0.05, 0.08, 0.15), fontname="helv")
        y += 18

    y += 10
    page.draw_line(fitz.Point(46, y), fitz.Point(549, y), color=(0.85, 0.88, 0.92), width=1)
    y += 20

    # Body Paragraphs
    for para in body_paragraphs:
        # Wrap text simply or insert line
        lines = para.split("\n")
        for line in lines:
            page.insert_text((46, y), line, fontsize=9.5, color=(0.15, 0.18, 0.25), fontname="helv")
            y += 15
        y += 8

    # Watermark if present
    if watermark_text:
        page.draw_rect(fitz.Rect(80, 460, 515, 505), color=(0.90, 0.70, 0.70), fill=(0.98, 0.92, 0.92), width=1)
        page.insert_text(
            (110, 492),
            f"*** {watermark_text} ***",
            fontsize=22,
            color=(0.80, 0.15, 0.15),
            fontname="helv"
        )

    # Footer
    page.draw_line(fitz.Point(46, 765), fitz.Point(549, 765), color=(0.85, 0.88, 0.92), width=0.75)
    page.insert_text(
        (46, 780),
        "Official Scrutiny Verification Copy  •  AICTE Approval Process Handbook (APH) 2024-2027",
        fontsize=8,
        color=(0.45, 0.50, 0.60),
        fontname="helv"
    )
    page.insert_text(
        (480, 780),
        "Page 1 of 1",
        fontsize=8,
        color=(0.45, 0.50, 0.60),
        fontname="helv"
    )

    doc.save(str(destination_path))
    doc.close()
    return 1


def _save_and_process_document(
    db: Session,
    app: Application,
    category: str,
    original_filename: str,
    doc_path: Path
) -> Document:
    """
    Saves and processes a document into the database, parsing fields and bounding boxes.
    """
    with open(doc_path, "rb") as f:
        file_bytes = f.read()

    file_size = len(file_bytes)
    sha256_hash = calculate_sha256(file_bytes)
    detected_mime = "application/pdf"

    # Move to permanent application vault path if different
    app_vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(app.id)
    app_vault_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{sha256_hash[:12]}_{original_filename}"
    permanent_path = app_vault_dir / safe_filename

    if doc_path.resolve() != permanent_path.resolve():
        with open(permanent_path, "wb") as f:
            f.write(file_bytes)

    storage_path = str(permanent_path)

    parsed = extract_document_content(storage_path, detected_mime)

    doc = Document(
        application_id=app.id,
        document_category=category,
        original_filename=original_filename,
        storage_path=storage_path,
        file_size_bytes=file_size,
        mime_type=detected_mime,
        sha256_hash=sha256_hash,
        phash_value=parsed.get("phash"),
        pdf_metadata_json=parsed.get("metadata_json"),
        incremental_updates_count=parsed.get("incremental_updates_count", 0),
        ocr_needed=parsed.get("ocr_needed", False),
        ocr_performed=parsed.get("ocr_performed", False),
        ocr_engine_available=parsed.get("ocr_engine_available", True),
        status=parsed.get("status", "PROCESSED"),
        page_count=parsed.get("page_count", 1),
        extracted_text=parsed.get("text"),
        uploaded_at=app.created_at
    )
    db.add(doc)
    db.flush()

    for field in parsed.get("extracted_fields", []):
        ef = ExtractedField(
            document_id=doc.id,
            field_key=field["field_key"],
            field_value=field["field_value"],
            normalized_value=field.get("normalized_value"),
            confidence_score=field.get("confidence_score", 1.0),
            page_number=field.get("page_number", 1),
            source_snippet=field.get("source_snippet"),
            bounding_box=json.dumps(field.get("bounding_box")) if field.get("bounding_box") else None,
            extraction_method=field.get("extraction_method", "PYMUPDF")
        )
        db.add(ef)

    AuditEvent.create_chained(
        db=db,
        application_id=app.id,
        event_type="DOC_UPLOADED",
        details={
            "document_id": doc.id,
            "filename": doc.original_filename,
            "category": doc.document_category,
            "file_size": doc.file_size_bytes,
            "sha256": doc.sha256_hash,
            "page_count": doc.page_count
        },
        actor="PORTAL_INTAKE"
    )

    db.flush()
    return doc


def _clean_application_records(db: Session, app_id: int):
    """
    Cleans up all child tables for an application in strict foreign-key dependency order.
    """
    run_ids = [r[0] for r in db.query(ScrutinyRun.id).filter(ScrutinyRun.application_id == app_id).all()]
    if run_ids:
        db.query(CheckResult).filter(CheckResult.scrutiny_run_id.in_(run_ids)).delete(synchronize_session=False)

    doc_ids = [d[0] for d in db.query(Document.id).filter(Document.application_id == app_id).all()]
    if doc_ids:
        db.query(ExtractedField).filter(ExtractedField.document_id.in_(doc_ids)).delete(synchronize_session=False)

    db.query(Alert).filter(Alert.application_id == app_id).delete(synchronize_session=False)
    db.query(Finding).filter(Finding.application_id == app_id).delete(synchronize_session=False)
    db.query(ScrutinyRun).filter(ScrutinyRun.application_id == app_id).delete(synchronize_session=False)
    db.query(AuthorityVerification).filter(AuthorityVerification.application_id == app_id).delete(synchronize_session=False)
    db.query(Document).filter(Document.application_id == app_id).delete(synchronize_session=False)
    db.query(AuditEvent).filter(AuditEvent.application_id == app_id).delete(synchronize_session=False)
    db.flush()


def seed_three_demo_scenarios(db: Session, force_refresh: bool = False) -> dict[str, Application]:
    """
    Creates and scrutinizes the three realistic demonstration scenarios:
    1. APP-2026-SARASWATI-001 (Complete & Eligible, Ready for Approval)
    2. APP-2026-PRAGATI-002 (Missing Mandatory Documents, Waiting for Docs)
    3. APP-2026-VANGUARD-003 (Intake, Expired Fire NOC, Location Mismatch, Flagged)

    Returns dictionary mapping scenario code to Application object.
    """
    target_apps = {
        "APP-2026-SARASWATI-001": None,
        "APP-2026-PRAGATI-002": None,
        "APP-2026-VANGUARD-003": None
    }

    # If already created and force_refresh is False, check if all 3 are present
    existing_records = db.query(Application).filter(
        Application.application_number.in_(list(target_apps.keys()))
    ).all()
    existing_map = {a.application_number: a for a in existing_records}

    if not force_refresh and len(existing_map) == 3:
        # Check that scenario 1 is ready and eligible, and scenarios 2/3 are flagged
        s1 = existing_map["APP-2026-SARASWATI-001"]
        s2 = existing_map["APP-2026-PRAGATI-002"]
        s3 = existing_map["APP-2026-VANGUARD-003"]
        if (
            s1.status == "READY_FOR_REVIEW" and
            s2.status == "DEFICIENCY_FLAGGED" and
            s3.status == "DEFICIENCY_FLAGGED" and
            len(s1.documents) == 3 and
            len(s2.documents) == 1 and
            len(s3.documents) == 3
        ):
            return existing_map

    now = datetime.datetime.now(datetime.timezone.utc)
    results = {}

    # =========================================================================
    # SCENARIO 1: Saraswati College of Engineering & Technology
    # Complete Submission, Ready for Approval (Eligible, 0 Deficiencies)
    # =========================================================================
    app1_num = "APP-2026-SARASWATI-001"
    inst1_aicte_id = "1-DEMO-READY-001"
    inst1 = db.query(Institution).filter(Institution.aicte_permanent_id == inst1_aicte_id).first()
    if not inst1:
        inst1 = Institution(
            aicte_permanent_id=inst1_aicte_id,
            name="Saraswati College of Engineering & Technology (DEMO)",
            institution_type="TECHNICAL_INSTITUTE",
            address="Survey 104/2A, Kothrud",
            district="Pune",
            state="Maharashtra"
        )
        db.add(inst1)
        db.flush()

    base1 = db.query(BaselineRecord).filter(
        BaselineRecord.institution_id == inst1.id,
        BaselineRecord.record_type == "APPROVED_INTAKE"
    ).first()
    if not base1:
        base1 = BaselineRecord(
            institution_id=inst1.id,
            record_type="APPROVED_INTAKE",
            academic_year="2025-2026",
            programme="ENGINEERING_AND_TECHNOLOGY",
            course="Computer Science & Engineering",
            approved_intake=120,
            source_system="AICTE_CENTRAL_DB (SYNTHETIC)",
            is_simulated=True
        )
        db.add(base1)
        db.flush()
    else:
        base1.approved_intake = 120

    app1 = db.query(Application).filter(Application.application_number == app1_num).first()
    t1 = now - datetime.timedelta(minutes=15)
    if not app1:
        app1 = Application(
            application_number=app1_num,
            institution_id=inst1.id,
            category="EOA_REGULAR",
            academic_year="2026-2027",
            status="SUBMITTED",
            declared_programme="ENGINEERING_AND_TECHNOLOGY",
            declared_course="Computer Science & Engineering",
            declared_intake=120,
            declared_land_acres=7.5,
            created_at=t1,
            updated_at=t1
        )
        db.add(app1)
        db.flush()
    else:
        # Clear existing child records for fresh run
        _clean_application_records(db, app1.id)
        app1.declared_intake = 120
        app1.final_decision = None
        app1.decided_by = None
        app1.decided_at = None
        app1.decision_remarks = None
        app1.status = "SUBMITTED"
        app1.created_at = t1
        app1.updated_at = t1
        db.flush()

    # Generate Scenario 1 Documents
    vault_app1 = Path(settings.STORAGE_VAULT_PATH) / str(app1.id)
    vault_app1.mkdir(parents=True, exist_ok=True)

    # 1. Fire Safety NOC (FS-2026-SARASWATI-01)
    fs1_path = vault_app1 / "Fire_Safety_NOC_FS1044.pdf"
    render_pdf_with_qr(
        destination_path=fs1_path,
        header_agency="Government of Maharashtra • Directorate of Fire & Emergency Services",
        document_title="Fire & Life Safety Certificate (NOC Renewal)",
        fields=[
            ("Certificate No", "FS-2026-SARASWATI-01"),
            ("Institution", "Saraswati College of Engineering & Technology"),
            ("Approved Location", "Survey 104/2A, Kothrud, Pune, Maharashtra"),
            ("Valid Up To", "30/06/2027"),
            ("Date of Inspection", "01/06/2025"),
            ("Issuing Directorate", "Municipal Directorate of Fire & Emergency Services")
        ],
        body_paragraphs=[
            "This is to certify that the institutional campus of Saraswati College of Engineering & Technology",
            "situated at Survey 104/2A, Kothrud, Pune, Maharashtra has been inspected by the Competent Authority.",
            "All statutory life safety provisions, fire hydrant networks, automatic detection systems, and emergency",
            "evacuation staircases have been installed and maintained in full operational condition.",
            "Occupancy clearance is hereby renewed for educational engineering institution use."
        ],
        qr_payload="FS-2026-SARASWATI-01"
    )
    _save_and_process_document(db, app1, "FIRE_SAFETY_NOC", "Fire_Safety_NOC_FS1044.pdf", fs1_path)

    # 2. Affiliation Letter (UNIV-AFFIL-SARASWATI-01)
    affil1_path = vault_app1 / "University_Affiliation_Letter_2026.pdf"
    render_pdf_with_qr(
        destination_path=affil1_path,
        header_agency="State Technical University Examination & Affiliation Board",
        document_title="University Affiliation Continuation Order (AY 2026-2027)",
        fields=[
            ("Ref No", "UNIV-AFFIL-SARASWATI-01"),
            ("Institution", "Saraswati College of Engineering & Technology"),
            ("Approved Location", "Survey 104/2A, Kothrud, Pune, Maharashtra"),
            ("Approved Intake", "120"),
            ("Sanctioned Intake", "120"),
            ("Sanctioned Programme", "B.Tech Computer Science & Engineering"),
            ("Valid Up To", "30/06/2027"),
            ("Date of Sanction", "15/05/2025")
        ],
        body_paragraphs=[
            "In accordance with the State Technical Universities Act and regulatory inspection recommendations,",
            "continuation of provisional affiliation is hereby granted to Saraswati College of Engineering & Technology.",
            "The institution is sanctioned to admit 120 (One Hundred Twenty) students in undergraduate Computer Science",
            "& Engineering for the Academic Year 2026-2027 subject to continued adherence to AICTE and University norms."
        ],
        qr_payload="UNIV-AFFIL-SARASWATI-01"
    )
    _save_and_process_document(db, app1, "AFFILIATION_LETTER", "University_Affiliation_Letter_2026.pdf", affil1_path)

    # 3. Faculty Cadre Roster
    roster1_path = vault_app1 / "Faculty_Cadre_Roster_AY2026.pdf"
    render_pdf_with_qr(
        destination_path=roster1_path,
        header_agency="Saraswati College of Engineering & Technology • Academic Cadre Cell",
        document_title="Faculty Cadre Roster & Qualifications Sheet (AY 2026-2027)",
        fields=[
            ("Institution", "Saraswati College of Engineering & Technology"),
            ("Department", "Computer Science & Engineering"),
            ("Sanctioned Intake", "120"),
            ("Total Faculty", "18"),
            ("Cadre Breakdown", "2 Professors, 4 Associate Professors, 12 Assistant Professors"),
            ("Teacher to Student Ratio", "1:20 (Compliant with AICTE APH Norms)"),
            ("Principal / Director", "Dr. M. K. Kulkarni, Ph.D (Comp. Engg.), 22 Years Exp.")
        ],
        body_paragraphs=[
            "It is certified that all teaching faculty listed in this roster possess valid AICTE-prescribed qualifications.",
            "All salaries and Dearness Allowances are disbursed through nationalized bank accounts per 7th Central Pay",
            "Commission scales. Biometric attendance compliance has been verified across all instructional working days."
        ],
        qr_payload="AICTE-FACULTY-ROSTER-SARASWATI-2026"
    )
    _save_and_process_document(db, app1, "FACULTY_ROSTER", "Faculty_Cadre_Roster_AY2026.pdf", roster1_path)

    # Run automated scrutiny for App 1
    execute_automated_scrutiny(db, app1.id, trigger_source="AUTOMATIC_ORCHESTRATOR")
    app1.created_at = t1
    app1.updated_at = t1
    db.commit()
    db.refresh(app1)
    results["APP-2026-SARASWATI-001"] = app1

    # =========================================================================
    # SCENARIO 2: Pragati Institute of Technical Studies
    # Missing Mandatory Documents (FIRE_SAFETY_NOC & AFFILIATION_LETTER missing)
    # =========================================================================
    app2_num = "APP-2026-PRAGATI-002"
    inst2_aicte_id = "1-DEMO-MISSING-002"
    inst2 = db.query(Institution).filter(Institution.aicte_permanent_id == inst2_aicte_id).first()
    if not inst2:
        inst2 = Institution(
            aicte_permanent_id=inst2_aicte_id,
            name="Pragati Institute of Technical Studies (DEMO)",
            institution_type="TECHNICAL_INSTITUTE",
            address="Plot 14, Hinjewadi Infotech Park Phase 1",
            district="Pune",
            state="Maharashtra"
        )
        db.add(inst2)
        db.flush()

    base2 = db.query(BaselineRecord).filter(
        BaselineRecord.institution_id == inst2.id,
        BaselineRecord.record_type == "APPROVED_INTAKE"
    ).first()
    if not base2:
        base2 = BaselineRecord(
            institution_id=inst2.id,
            record_type="APPROVED_INTAKE",
            academic_year="2025-2026",
            programme="ENGINEERING_AND_TECHNOLOGY",
            course="Mechanical Engineering",
            approved_intake=60,
            source_system="AICTE_CENTRAL_DB (SYNTHETIC)",
            is_simulated=True
        )
        db.add(base2)
        db.flush()

    app2 = db.query(Application).filter(Application.application_number == app2_num).first()
    t2 = now - datetime.timedelta(minutes=10)
    if not app2:
        app2 = Application(
            application_number=app2_num,
            institution_id=inst2.id,
            category="EOA_REGULAR",
            academic_year="2026-2027",
            status="SUBMITTED",
            declared_programme="ENGINEERING_AND_TECHNOLOGY",
            declared_course="Mechanical Engineering",
            declared_intake=60,
            declared_land_acres=5.0,
            created_at=t2,
            updated_at=t2
        )
        db.add(app2)
        db.flush()
    else:
        _clean_application_records(db, app2.id)
        app2.declared_intake = 60
        app2.final_decision = None
        app2.decided_by = None
        app2.decided_at = None
        app2.decision_remarks = None
        app2.status = "SUBMITTED"
        app2.created_at = t2
        app2.updated_at = t2
        db.flush()

    # Upload ONLY Faculty Cadre Roster (Missing Fire Safety NOC and Affiliation Letter)
    vault_app2 = Path(settings.STORAGE_VAULT_PATH) / str(app2.id)
    vault_app2.mkdir(parents=True, exist_ok=True)

    roster2_path = vault_app2 / "Faculty_Cadre_Roster_Mechanical.pdf"
    render_pdf_with_qr(
        destination_path=roster2_path,
        header_agency="Pragati Institute of Technical Studies • Academic Cell",
        document_title="Faculty Cadre Roster & Declarations (AY 2026-2027)",
        fields=[
            ("Institution", "Pragati Institute of Technical Studies"),
            ("Department", "Mechanical Engineering"),
            ("Sanctioned Intake", "60"),
            ("Total Faculty", "9"),
            ("Cadre Ratio", "1 Professor, 2 Associate Professors, 6 Assistant Professors"),
            ("Teacher to Student Ratio", "1:20 (Cadre Ratio Compliant)")
        ],
        body_paragraphs=[
            "Faculty roster submitted for Extension of Approval (EoA) scrutiny.",
            "Note: Supporting Fire Safety Certificate and University Affiliation Continuation Order are under",
            "administrative processing by local authorities and pending submission."
        ],
        qr_payload="AICTE-FACULTY-ROSTER-PRAGATI-2026"
    )
    _save_and_process_document(db, app2, "FACULTY_ROSTER", "Faculty_Cadre_Roster_Mechanical.pdf", roster2_path)

    execute_automated_scrutiny(db, app2.id, trigger_source="AUTOMATIC_ORCHESTRATOR")
    app2.created_at = t2
    app2.updated_at = t2
    db.commit()
    db.refresh(app2)
    results["APP-2026-PRAGATI-002"] = app2

    # =========================================================================
    # SCENARIO 3: Vanguard Institute of Applied Technology
    # Flagged for Review (Intake Mismatch, Expired Fire NOC, Location Mismatch)
    # =========================================================================
    app3_num = "APP-2026-VANGUARD-003"
    inst3_aicte_id = "1-DEMO-FLAGGED-003"
    inst3 = db.query(Institution).filter(Institution.aicte_permanent_id == inst3_aicte_id).first()
    if not inst3:
        inst3 = Institution(
            aicte_permanent_id=inst3_aicte_id,
            name="Vanguard Institute of Applied Technology (DEMO)",
            institution_type="TECHNICAL_INSTITUTE",
            address="Campus Sector 12, Katraj-Kondhwa Road",
            district="Pune",
            state="Maharashtra"
        )
        db.add(inst3)
        db.flush()

    base3 = db.query(BaselineRecord).filter(
        BaselineRecord.institution_id == inst3.id,
        BaselineRecord.record_type == "APPROVED_INTAKE"
    ).first()
    if not base3:
        base3 = BaselineRecord(
            institution_id=inst3.id,
            record_type="APPROVED_INTAKE",
            academic_year="2025-2026",
            programme="ENGINEERING_AND_TECHNOLOGY",
            course="Electronics and Communication Engineering",
            approved_intake=60,  # Baseline approved intake is 60!
            source_system="AICTE_CENTRAL_DB (SYNTHETIC)",
            is_simulated=True
        )
        db.add(base3)
        db.flush()
    else:
        base3.approved_intake = 60

    app3 = db.query(Application).filter(Application.application_number == app3_num).first()
    t3 = now - datetime.timedelta(minutes=5)
    if not app3:
        app3 = Application(
            application_number=app3_num,
            institution_id=inst3.id,
            category="EOA_REGULAR",
            academic_year="2026-2027",
            status="SUBMITTED",
            declared_programme="ENGINEERING_AND_TECHNOLOGY",
            declared_course="Electronics and Communication Engineering",
            declared_intake=180,  # Declared intake is 180 vs baseline 60!
            declared_land_acres=4.5,
            created_at=t3,
            updated_at=t3
        )
        db.add(app3)
        db.flush()
    else:
        _clean_application_records(db, app3.id)
        app3.declared_intake = 180
        app3.final_decision = None
        app3.decided_by = None
        app3.decided_at = None
        app3.decision_remarks = None
        app3.status = "SUBMITTED"
        app3.created_at = t3
        app3.updated_at = t3
        db.flush()

    vault_app3 = Path(settings.STORAGE_VAULT_PATH) / str(app3.id)
    vault_app3.mkdir(parents=True, exist_ok=True)

    # 1. Expired Fire Safety NOC (FS-2024-VANGUARD-EXP)
    fs3_path = vault_app3 / "Expired_Fire_Safety_NOC_2024.pdf"
    render_pdf_with_qr(
        destination_path=fs3_path,
        header_agency="Municipal Directorate of Fire & Emergency Services",
        document_title="Fire & Life Safety Certificate (NOC)",
        fields=[
            ("Certificate No", "FS-2024-VANGUARD-EXP"),
            ("Institution", "Vanguard Institute of Applied Technology"),
            ("Campus Location", "Campus Sector 12, Katraj-Kondhwa Road, Pune, Maharashtra"),
            ("Valid Up To", "15/01/2024"),  # Expired in 2024
            ("Date of Issue", "16/01/2021"),
            ("Current Status", "EXPIRED - PENDING RENEWAL INSPECTION")
        ],
        body_paragraphs=[
            "This certificate is issued to Vanguard Institute of Applied Technology for educational occupancy.",
            "Statutory three-year validity expired on 15/01/2024.",
            "Periodic renewal inspection has not been completed. A renewed certificate is mandatory under fire safety norms."
        ],
        qr_payload="FS-2024-VANGUARD-EXP",
        watermark_text="EXPIRED NOC"
    )
    _save_and_process_document(db, app3, "FIRE_SAFETY_NOC", "Expired_Fire_Safety_NOC_2024.pdf", fs3_path)

    # 2. Location Mismatch Affiliation Letter (UNIV-AFFIL-VANGUARD-LOC-ERR)
    affil3_path = vault_app3 / "University_Affiliation_Order_Hinjewadi.pdf"
    render_pdf_with_qr(
        destination_path=affil3_path,
        header_agency="State Technical University Examination & Affiliation Board",
        document_title="University Affiliation Sanction Order",
        fields=[
            ("Ref No", "UNIV-AFFIL-VANGUARD-LOC-ERR"),
            ("Order No", "UNIV-AFFIL-VANGUARD-LOC-ERR"),
            ("Institution", "Vanguard Institute of Applied Technology"),
            ("Approved Location", "Plot 88, MIDC Hinjewadi Phase 3, Pune, Maharashtra"),  # Hinjewadi vs Katraj-Kondhwa!
            ("Sanctioned Intake", "60"),
            ("Valid Up To", "19/05/2027"),
            ("Sanctioned Programme", "B.Tech Electronics & Communication Engineering")
        ],
        body_paragraphs=[
            "Affiliation order sanctioned exclusively for Hinjewadi campus premises at Plot 88, MIDC Hinjewadi Phase 3.",
            "This sanction is campus-specific and non-transferable to other branch facilities or locations.",
            "Approved intake capacity: 60 (Sixty) seats for undergraduate engineering."
        ],
        qr_payload="UNIV-AFFIL-VANGUARD-LOC-ERR"
    )
    _save_and_process_document(db, app3, "AFFILIATION_LETTER", "University_Affiliation_Order_Hinjewadi.pdf", affil3_path)

    # 3. Faculty Roster (ECE)
    roster3_path = vault_app3 / "Faculty_Roster_ECE.pdf"
    render_pdf_with_qr(
        destination_path=roster3_path,
        header_agency="Vanguard Institute of Applied Technology • Academic Cell",
        document_title="Faculty Cadre Roster & Summary (AY 2026-2027)",
        fields=[
            ("Institution", "Vanguard Institute of Applied Technology"),
            ("Department", "Electronics and Communication Engineering"),
            ("Declared Intake", "180"),
            ("Sanctioned Intake", "180"),
            ("Total Faculty", "12"),
            ("Principal / Director", "Dr. S. K. Mehta, Ph.D, 18 Years Experience")
        ],
        body_paragraphs=[
            "Faculty roster submitted in support of extension of approval and enhanced capacity intake of 180 seats.",
            "Cadre distribution: 1 Professor, 3 Associate Professors, 8 Assistant Professors."
        ],
        qr_payload="AICTE-FACULTY-ROSTER-VANGUARD-2026"
    )
    _save_and_process_document(db, app3, "FACULTY_ROSTER", "Faculty_Roster_ECE.pdf", roster3_path)

    execute_automated_scrutiny(db, app3.id, trigger_source="AUTOMATIC_ORCHESTRATOR")
    app3.created_at = t3
    app3.updated_at = t3
    db.commit()
    db.refresh(app3)
    results["APP-2026-VANGUARD-003"] = app3

    return results
