"""
AICTE NIDHI — 12 Distinct Synthetic Demonstration Scenarios
Generates fully-persisted, realistic demonstration scenarios calculated relative to runtime date:
1. Valid Active FDR (All Verified)
2. FDR Approaching Maturity (Expiring in 12 days, Renewal Required)
3. Matured FDR (Matured 20 days ago, Overdue)
4. Missing Supporting Documents (FDR Receipt present, Bank Lien Letter missing)
5. Amount Mismatch (Recorded ₹20,00,000 vs Extracted ₹12,00,000)
6. Instrument Number & Entity Discrepancy
7. Replacement FDR Linked to Older Superseded Instrument
8. Release Request Awaiting Officer Review (Checklist underway)
9. Returned Release Request Requiring Correction
10. Completed Release Case with Recorded Decision History
11. External Bank Verification Unavailable (Regional Rural Bank)
12. Unreadable / Corrupted Document Test Case

Idempotent: Safe to run repeatedly without creating duplicates.
"""

import os
import io
import json
import datetime
from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session
import fitz  # PyMuPDF
import qrcode

from app.config import settings
from app.models import (
    Institution, DepositInstrument, InstrumentDocument, VerificationRecord,
    RenewalRecord, ReleaseRefundRequest, Notification, AuditEvent
)
from app.services.storage import calculate_sha256
from app.services.document_parser import extract_document_content
from app.services.instrument_service import (
    calculate_validity_status, format_inr, update_instrument_lifecycle,
    DEFAULT_WARNING_WINDOW_DAYS
)
from app.services.fdr_verification_service import run_instrument_verification
from app.services.release_service import PROTOTYPE_RELEASE_CHECKLIST_TEMPLATE


def render_bank_fdr_pdf(
    destination_path: Path,
    bank_title: str,
    branch_name: str,
    fdr_number: str,
    institution_name: str,
    amount_inr: float,
    issue_date: str,
    maturity_date: str,
    lien_text: str = "Regional Officer, All India Council for Technical Education (AICTE)",
    account_number: str = "39104810924",
    tenure_months: int = 36,
    qr_data: str | None = None,
    watermark_text: str | None = None,
    override_extracted_amount: float | None = None,
    override_extracted_number: str | None = None,
    corrupt_content: bool = False
) -> int:
    """
    Renders an authentic-looking synthetic Fixed Deposit Receipt (FDR)
    with PyMuPDF and an embedded digital QR seal.
    """
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if corrupt_content:
        # Create unreadable pseudo-PDF
        with open(destination_path, "wb") as f:
            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n[CORRUPTED_STREAM_PAYLOAD_FOR_SYNTHETIC_TESTING]")
        return 1

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Outer and inner border
    page.draw_rect(fitz.Rect(32, 32, 563, 810), color=(0.15, 0.25, 0.40), width=1.5)
    page.draw_rect(fitz.Rect(36, 36, 559, 806), color=(0.85, 0.88, 0.92), width=0.75)

    # Prototype banner
    page.draw_rect(fitz.Rect(38, 38, 557, 56), color=(0.94, 0.96, 0.98), fill=(0.94, 0.96, 0.98))
    page.insert_text(
        (46, 50),
        "AICTE NIDHI PORTAL EVALUATION DEMO  •  SYNTHETIC BANK FDR DATASET",
        fontsize=8,
        color=(0.35, 0.42, 0.52),
        fontname="helv"
    )

    # Bank Header
    page.insert_text((46, 82), bank_title.upper(), fontsize=13, color=(0.08, 0.15, 0.35), fontname="helv")
    page.insert_text((46, 98), f"Branch: {branch_name}", fontsize=9, color=(0.35, 0.40, 0.50), fontname="helv")
    page.draw_line(fitz.Point(46, 108), fitz.Point(420, 108), color=(0.20, 0.30, 0.50), width=1.2)

    # Title
    page.insert_text((46, 130), "FIXED DEPOSIT RECEIPT / TERM DEPOSIT ADVICE", fontsize=11, color=(0.10, 0.12, 0.20), fontname="helv")

    # Embed QR Code
    if qr_data or fdr_number:
        payload = qr_data or fdr_number
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        qr_rect = fitz.Rect(440, 68, 540, 168)
        page.draw_rect(fitz.Rect(436, 64, 544, 180), color=(0.85, 0.88, 0.92), width=0.5)
        page.insert_image(qr_rect, stream=buf.getvalue())
        page.insert_text((446, 176), "BANK DIGITAL SEAL", fontsize=7, color=(0.4, 0.45, 0.55), fontname="helv")

    # Fields
    y = 165
    display_amount = override_extracted_amount if override_extracted_amount is not None else amount_inr
    display_number = override_extracted_number if override_extracted_number is not None else fdr_number

    fields = [
        ("FDR Receipt No", display_number),
        ("Account No", account_number),
        ("Depositor / Institution", institution_name),
        ("Deposit Amount", f"₹ {display_amount:,.2f}"),
        ("Deposit Amount (Text)", f"INR {format_inr(display_amount)} Only"),
        ("Date of Issue", issue_date),
        ("Maturity Date", maturity_date),
        ("Tenure", f"{tenure_months} Months"),
        ("Lien Endorsement", f"Lien Marked to {lien_text}"),
        ("Operating Instructions", "Joint Operation / No Pre-mature Withdrawal without AICTE Written Sanction")
    ]

    for label, val in fields:
        page.insert_text((46, y), f"{label}:", fontsize=9.5, color=(0.28, 0.32, 0.42), fontname="helv")
        page.insert_text((210, y), str(val), fontsize=9.5, color=(0.06, 0.08, 0.15), fontname="helv")
        y += 20

    y += 10
    page.draw_line(fitz.Point(46, y), fitz.Point(549, y), color=(0.85, 0.88, 0.92), width=1)
    y += 25

    # Certification Paragraphs
    paragraphs = [
        f"This is to certify that the sum of ₹ {display_amount:,.2f} has been deposited under Special Fixed Term Deposit.",
        f"The deposit receipt has been formally lien-marked in favor of {lien_text}.",
        "Under regulatory guidelines, the bank undertakes that this deposit shall not be liquidated, pledged,",
        "or released to any third party without explicit written discharge sanction issued by the AICTE Competent Authority.",
        "Interest accrued shall be credited or reinvested as agreed under institutional approval norms."
    ]

    for p in paragraphs:
        page.insert_text((46, y), p, fontsize=9, color=(0.20, 0.22, 0.30), fontname="helv")
        y += 18

    # Watermark if present
    if watermark_text:
        page.draw_rect(fitz.Rect(80, 480, 515, 525), color=(0.90, 0.70, 0.70), fill=(0.98, 0.92, 0.92), width=1)
        page.insert_text((110, 512), f"*** {watermark_text} ***", fontsize=22, color=(0.80, 0.15, 0.15), fontname="helv")

    # Bank Officer Signatures Box
    y = 700
    page.draw_line(fitz.Point(46, y), fitz.Point(549, y), color=(0.85, 0.88, 0.92), width=0.75)
    y += 25
    page.insert_text((46, y), "Verified by: Senior Branch Manager", fontsize=9, color=(0.3, 0.35, 0.45), fontname="helv")
    page.insert_text((360, y), "Authorized Officer (AICTE Bureau)", fontsize=9, color=(0.3, 0.35, 0.45), fontname="helv")

    # Footer
    page.draw_line(fitz.Point(46, 765), fitz.Point(549, 765), color=(0.85, 0.88, 0.92), width=0.75)
    page.insert_text((46, 780), "AICTE Regulation Bureau • Security Deposit / FDR Repository Record", fontsize=8, color=(0.45, 0.50, 0.60), fontname="helv")
    page.insert_text((490, 780), "Page 1 of 1", fontsize=8, color=(0.45, 0.50, 0.60), fontname="helv")

    doc.save(str(destination_path))
    doc.close()
    return 1


def _create_or_get_institution(db: Session, aicte_id: str, name: str, state: str = "Maharashtra", district: str = "Pune", inst_type: str = "TECHNICAL_INSTITUTE") -> Institution:
    inst = db.query(Institution).filter(Institution.aicte_permanent_id == aicte_id).first()
    if not inst:
        inst = Institution(
            aicte_permanent_id=aicte_id,
            institution_code=f"INST-{aicte_id[-4:]}",
            name=name,
            institution_type=inst_type,
            address=f"Campus Road, {district}",
            state=state,
            district=district,
            contact_email=f"registrar@{aicte_id.lower().replace('-', '')}.edu",
            contact_phone="+91-20-25812345",
            record_status="ACTIVE"
        )
        db.add(inst)
        db.flush()
    return inst


def _clean_instrument_records(db: Session, instrument_id: int):
    """Cleans child records for an instrument before reseeding."""
    db.query(VerificationRecord).filter(VerificationRecord.instrument_id == instrument_id).delete(synchronize_session=False)
    db.query(InstrumentDocument).filter(InstrumentDocument.instrument_id == instrument_id).delete(synchronize_session=False)
    db.query(RenewalRecord).filter(RenewalRecord.original_instrument_id == instrument_id).delete(synchronize_session=False)
    db.query(RenewalRecord).filter(RenewalRecord.replacement_instrument_id == instrument_id).delete(synchronize_session=False)
    db.query(ReleaseRefundRequest).filter(ReleaseRefundRequest.instrument_id == instrument_id).delete(synchronize_session=False)
    db.query(Notification).filter(Notification.instrument_id == instrument_id).delete(synchronize_session=False)
    db.query(AuditEvent).filter(AuditEvent.instrument_id == instrument_id).delete(synchronize_session=False)
    db.flush()


def _save_and_attach_document(
    db: Session,
    instrument: DepositInstrument,
    category: str,
    original_filename: str,
    file_path: Path
) -> InstrumentDocument:
    """Stores document metadata, extracts text/bounding boxes, and links to instrument."""
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    file_size = len(file_bytes)
    sha256 = calculate_sha256(file_bytes)
    mime = "application/pdf" if original_filename.lower().endswith(".pdf") else "image/png"

    app_vault = Path(settings.STORAGE_VAULT_PATH) / "instruments" / str(instrument.id)
    app_vault.mkdir(parents=True, exist_ok=True)
    safe_name = f"{sha256[:12]}_{original_filename}"
    vault_file = app_vault / safe_name

    if file_path.resolve() != vault_file.resolve():
        with open(vault_file, "wb") as f:
            f.write(file_bytes)

    storage_path = str(vault_file)
    parsed = extract_document_content(storage_path, mime)

    doc = InstrumentDocument(
        instrument_id=instrument.id,
        document_category=category,
        original_filename=original_filename,
        storage_path=storage_path,
        file_size_bytes=file_size,
        mime_type=mime,
        sha256_hash=sha256,
        phash_value=parsed.get("phash"),
        upload_timestamp=datetime.datetime.now(datetime.timezone.utc),
        uploaded_by="SYSTEM_SEED",
        extraction_status=parsed.get("status", "PROCESSED"),
        extracted_fields_json=json.dumps(parsed.get("extracted_fields", [])),
        extracted_text=parsed.get("text"),
        ocr_performed=parsed.get("ocr_performed", False),
        version=1,
        status="ACTIVE"
    )
    db.add(doc)
    db.flush()
    return doc


def seed_fdr_demo_scenarios(db: Session, force_refresh: bool = False) -> dict:
    """
    Seeds the 12 realistic demonstration scenarios using runtime-relative dates.
    """
    today = datetime.datetime.now(datetime.timezone.utc).date()
    target_count = 12

    existing_count = db.query(DepositInstrument).count()
    if not force_refresh and existing_count >= target_count:
        return {"status": "ALREADY_SEEDED", "count": existing_count}

    results = {}
    vault_base = Path(settings.STORAGE_VAULT_PATH) / "seed_cache"
    vault_base.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Valid Active FDR (All Verified)
    # -------------------------------------------------------------------------
    inst1 = _create_or_get_institution(db, "1-DEMO-FDR-001", "Saraswati College of Engineering & Technology")
    num1 = "FDR-SBIN-2024-1001"
    app1 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num1).first()
    if not app1:
        app1 = DepositInstrument(
            instrument_number=num1,
            institution_id=inst1.id,
            instrument_type="FDR",
            issuing_bank="State Bank of India",
            branch_name="Kothrud Branch, Pune",
            branch_ifsc="SBIN0001234",
            amount=Decimal("1500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=365),
            maturity_date=today + datetime.timedelta(days=730),
            submission_date=today - datetime.timedelta(days=360),
            lifecycle_status="ACTIVE",
            validity_status="ACTIVE_VALID",
            verification_status="UNVERIFIED",
            purpose="Establishment Corpus Security Deposit"
        )
        db.add(app1)
        db.flush()
    else:
        _clean_instrument_records(db, app1.id)

    f1 = vault_base / "FDR_Receipt_SBI_1001.pdf"
    render_bank_fdr_pdf(
        f1, "State Bank of India", "Kothrud Branch, Pune", num1,
        inst1.name, 1500000.00, str(today - datetime.timedelta(days=365)), str(today + datetime.timedelta(days=730))
    )
    _save_and_attach_document(db, app1, "FDR_RECEIPT", "FDR_Receipt_SBI_1001.pdf", f1)

    f1_lien = vault_base / "Bank_Lien_Letter_SBI_1001.pdf"
    render_bank_fdr_pdf(
        f1_lien, "State Bank of India", "Kothrud Branch, Pune", num1,
        inst1.name, 1500000.00, str(today - datetime.timedelta(days=365)), str(today + datetime.timedelta(days=730)),
        lien_text="Regional Officer, Western Regional Office, AICTE Mumbai"
    )
    _save_and_attach_document(db, app1, "BANK_LIEN_LETTER", "Bank_Lien_Letter_SBI_1001.pdf", f1_lien)

    run_instrument_verification(db, app1)
    app1.lifecycle_status = "ACTIVE"
    results["scenario_1"] = app1

    # -------------------------------------------------------------------------
    # Scenario 2: FDR Approaching Maturity (Expiring in 12 days, Renewal Required)
    # -------------------------------------------------------------------------
    inst2 = _create_or_get_institution(db, "1-DEMO-FDR-002", "Pragati Institute of Technical Studies")
    num2 = "FDR-PNB-2022-2002"
    app2 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num2).first()
    mat2 = today + datetime.timedelta(days=12)
    if not app2:
        app2 = DepositInstrument(
            instrument_number=num2,
            institution_id=inst2.id,
            instrument_type="FDR",
            issuing_bank="Punjab National Bank",
            branch_name="Hinjewadi Infotech Park, Pune",
            branch_ifsc="PUNB0045600",
            amount=Decimal("2500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=1080),
            maturity_date=mat2,
            submission_date=today - datetime.timedelta(days=1075),
            lifecycle_status="RENEWAL_REQUIRED",
            validity_status="EXPIRING_SOON",
            verification_status="UNVERIFIED",
            purpose="Sanctioned Intake Expansion Security Deposit"
        )
        db.add(app2)
        db.flush()
    else:
        _clean_instrument_records(db, app2.id)

    f2 = vault_base / "FDR_Receipt_PNB_2002.pdf"
    render_bank_fdr_pdf(
        f2, "Punjab National Bank", "Hinjewadi Infotech Park, Pune", num2,
        inst2.name, 2500000.00, str(today - datetime.timedelta(days=1080)), str(mat2)
    )
    _save_and_attach_document(db, app2, "FDR_RECEIPT", "FDR_Receipt_PNB_2002.pdf", f2)

    f2_lien = vault_base / "Lien_Endorsement_PNB_2002.pdf"
    render_bank_fdr_pdf(
        f2_lien, "Punjab National Bank", "Hinjewadi Infotech Park, Pune", num2,
        inst2.name, 2500000.00, str(today - datetime.timedelta(days=1080)), str(mat2)
    )
    _save_and_attach_document(db, app2, "BANK_LIEN_LETTER", "Lien_Endorsement_PNB_2002.pdf", f2_lien)

    run_instrument_verification(db, app2)
    app2.lifecycle_status = "RENEWAL_REQUIRED"
    results["scenario_2"] = app2

    # -------------------------------------------------------------------------
    # Scenario 3: Matured FDR (Matured 20 days ago, Overdue)
    # -------------------------------------------------------------------------
    inst3 = _create_or_get_institution(db, "1-DEMO-FDR-003", "Vanguard Institute of Applied Technology")
    num3 = "FDR-HDFC-2021-3003"
    mat3 = today - datetime.timedelta(days=20)
    app3 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num3).first()
    if not app3:
        app3 = DepositInstrument(
            instrument_number=num3,
            institution_id=inst3.id,
            instrument_type="FDR",
            issuing_bank="HDFC Bank",
            branch_name="Katraj-Kondhwa Road, Pune",
            amount=Decimal("1000000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=1115),
            maturity_date=mat3,
            submission_date=today - datetime.timedelta(days=1110),
            lifecycle_status="MATURED",
            validity_status="MATURED",
            verification_status="UNVERIFIED",
            purpose="Addition of New Technical Division"
        )
        db.add(app3)
        db.flush()
    else:
        _clean_instrument_records(db, app3.id)

    f3 = vault_base / "Matured_FDR_Receipt_HDFC_3003.pdf"
    render_bank_fdr_pdf(
        f3, "HDFC Bank", "Katraj-Kondhwa Road, Pune", num3,
        inst3.name, 1000000.00, str(today - datetime.timedelta(days=1115)), str(mat3),
        watermark_text="MATURED OVERDUE"
    )
    _save_and_attach_document(db, app3, "FDR_RECEIPT", "Matured_FDR_Receipt_HDFC_3003.pdf", f3)
    f3_lien = vault_base / "Lien_Letter_HDFC_3003.pdf"
    render_bank_fdr_pdf(
        f3_lien, "HDFC Bank", "Katraj-Kondhwa Road, Pune", num3,
        inst3.name, 1000000.00, str(today - datetime.timedelta(days=1115)), str(mat3)
    )
    _save_and_attach_document(db, app3, "BANK_LIEN_LETTER", "Lien_Letter_HDFC_3003.pdf", f3_lien)

    run_instrument_verification(db, app3)
    app3.lifecycle_status = "MATURED"
    results["scenario_3"] = app3

    # -------------------------------------------------------------------------
    # Scenario 4: Missing Supporting Documents (FDR Receipt present, Lien missing)
    # -------------------------------------------------------------------------
    inst4 = _create_or_get_institution(db, "1-DEMO-FDR-004", "Sahyadri Institute of Pharmacy")
    num4 = "FDR-BOB-2025-4004"
    app4 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num4).first()
    if not app4:
        app4 = DepositInstrument(
            instrument_number=num4,
            institution_id=inst4.id,
            instrument_type="FDR",
            issuing_bank="Bank of Baroda",
            branch_name="Shivajinagar, Pune",
            amount=Decimal("1200000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=90),
            maturity_date=today + datetime.timedelta(days=640),
            submission_date=today - datetime.timedelta(days=15),
            lifecycle_status="SUBMITTED",
            validity_status="ACTIVE_VALID",
            verification_status="UNVERIFIED",
            purpose="New Pharmacy Programme Security Deposit"
        )
        db.add(app4)
        db.flush()
    else:
        _clean_instrument_records(db, app4.id)

    f4 = vault_base / "FDR_Receipt_BOB_4004.pdf"
    render_bank_fdr_pdf(
        f4, "Bank of Baroda", "Shivajinagar, Pune", num4,
        inst4.name, 1200000.00, str(today - datetime.timedelta(days=90)), str(today + datetime.timedelta(days=640))
    )
    _save_and_attach_document(db, app4, "FDR_RECEIPT", "FDR_Receipt_BOB_4004.pdf", f4)
    # Intentionally do not attach BANK_LIEN_LETTER!
    run_instrument_verification(db, app4)
    results["scenario_4"] = app4

    # -------------------------------------------------------------------------
    # Scenario 5: Amount Mismatch (Recorded ₹20,00,000 vs Extracted ₹12,00,000)
    # -------------------------------------------------------------------------
    inst5 = _create_or_get_institution(db, "1-DEMO-FDR-005", "Modern Institute of Management")
    num5 = "FDR-CANARA-2024-5005"
    app5 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num5).first()
    if not app5:
        app5 = DepositInstrument(
            instrument_number=num5,
            institution_id=inst5.id,
            instrument_type="FDR",
            issuing_bank="Canara Bank",
            branch_name="Deccan Gymkhana, Pune",
            amount=Decimal("2000000.00"),  # Recorded as ₹20,00,000
            currency="INR",
            issue_date=today - datetime.timedelta(days=120),
            maturity_date=today + datetime.timedelta(days=610),
            submission_date=today - datetime.timedelta(days=20),
            lifecycle_status="PENDING_VERIFICATION",
            validity_status="ACTIVE_VALID",
            verification_status="UNVERIFIED",
            purpose="MBA Program Expansion Deposit"
        )
        db.add(app5)
        db.flush()
    else:
        _clean_instrument_records(db, app5.id)

    f5 = vault_base / "Canara_Bank_Deposit_5005.pdf"
    render_bank_fdr_pdf(
        f5, "Canara Bank", "Deccan Gymkhana, Pune", num5,
        inst5.name, 2000000.00, str(today - datetime.timedelta(days=120)), str(today + datetime.timedelta(days=610)),
        override_extracted_amount=1200000.00  # Document contains ₹12,00,000!
    )
    _save_and_attach_document(db, app5, "FDR_RECEIPT", "Canara_Bank_Deposit_5005.pdf", f5)
    f5_lien = vault_base / "Canara_Lien_5005.pdf"
    render_bank_fdr_pdf(
        f5_lien, "Canara Bank", "Deccan Gymkhana, Pune", num5,
        inst5.name, 1200000.00, str(today - datetime.timedelta(days=120)), str(today + datetime.timedelta(days=610))
    )
    _save_and_attach_document(db, app5, "BANK_LIEN_LETTER", "Canara_Lien_5005.pdf", f5_lien)

    run_instrument_verification(db, app5)
    results["scenario_5"] = app5

    # -------------------------------------------------------------------------
    # Scenario 6: Discrepancy in Instrument Number & Entity
    # -------------------------------------------------------------------------
    inst6 = _create_or_get_institution(db, "1-DEMO-FDR-006", "Vidya Pratishthan Polytechnic")
    num6 = "FDR-UBI-2024-6006"
    app6 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num6).first()
    if not app6:
        app6 = DepositInstrument(
            instrument_number=num6,
            institution_id=inst6.id,
            instrument_type="FDR",
            issuing_bank="Union Bank of India",
            branch_name="Hadapsar Industrial Area, Pune",
            amount=Decimal("800000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=60),
            maturity_date=today + datetime.timedelta(days=670),
            submission_date=today - datetime.timedelta(days=10),
            lifecycle_status="PENDING_VERIFICATION",
            validity_status="ACTIVE_VALID",
            verification_status="UNVERIFIED",
            purpose="Polytechnic Diploma Corpus"
        )
        db.add(app6)
        db.flush()
    else:
        _clean_instrument_records(db, app6.id)

    f6 = vault_base / "Union_Bank_Receipt_6006.pdf"
    render_bank_fdr_pdf(
        f6, "Union Bank of India", "Hadapsar, Pune", num6,
        "Vidya Vikas Educational Trust (Different Entity)", 800000.00,
        str(today - datetime.timedelta(days=60)), str(today + datetime.timedelta(days=670)),
        override_extracted_number="FDR-UBI-2024-9999-WRONG"
    )
    _save_and_attach_document(db, app6, "FDR_RECEIPT", "Union_Bank_Receipt_6006.pdf", f6)
    f6_lien = vault_base / "Union_Bank_Lien_6006.pdf"
    render_bank_fdr_pdf(
        f6_lien, "Union Bank of India", "Hadapsar, Pune", num6,
        inst6.name, 800000.00, str(today - datetime.timedelta(days=60)), str(today + datetime.timedelta(days=670))
    )
    _save_and_attach_document(db, app6, "BANK_LIEN_LETTER", "Union_Bank_Lien_6006.pdf", f6_lien)

    run_instrument_verification(db, app6)
    results["scenario_6"] = app6

    # -------------------------------------------------------------------------
    # Scenario 7: Replacement FDR Linked to Older Superseded Instrument
    # -------------------------------------------------------------------------
    # Original Instrument (Old, Superseded)
    orig_num7 = "FDR-SBIN-2023-7001-ORIG"
    orig7 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == orig_num7).first()
    if not orig7:
        orig7 = DepositInstrument(
            instrument_number=orig_num7,
            institution_id=inst1.id,
            instrument_type="FDR",
            issuing_bank="State Bank of India",
            branch_name="Kothrud Branch, Pune",
            amount=Decimal("1500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=1100),
            maturity_date=today - datetime.timedelta(days=10),
            submission_date=today - datetime.timedelta(days=1095),
            lifecycle_status="SUPERSEDED",
            validity_status="MATURED",
            verification_status="VERIFIED",
            purpose="Initial Campus Security Deposit"
        )
        db.add(orig7)
        db.flush()

    # Replacement Instrument (Renewed, Active)
    rep_num7 = "FDR-SBIN-2026-7007-RENEWED"
    rep7 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == rep_num7).first()
    if not rep7:
        rep7 = DepositInstrument(
            instrument_number=rep_num7,
            institution_id=inst1.id,
            instrument_type="FDR",
            issuing_bank="State Bank of India",
            branch_name="Kothrud Branch, Pune",
            amount=Decimal("1500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=10),
            maturity_date=today + datetime.timedelta(days=1085),
            submission_date=today - datetime.timedelta(days=8),
            lifecycle_status="ACTIVE",
            validity_status="ACTIVE_VALID",
            verification_status="VERIFIED",
            original_instrument_id=orig7.id,
            renewal_count=1,
            purpose="Renewed Corpus Security Deposit (Cycle 2)"
        )
        db.add(rep7)
        db.flush()

    # Renewal record linking the two
    ren7 = db.query(RenewalRecord).filter(RenewalRecord.original_instrument_id == orig7.id).first()
    if not ren7:
        ren7 = RenewalRecord(
            original_instrument_id=orig7.id,
            replacement_instrument_id=rep7.id,
            previous_maturity_date=orig7.maturity_date,
            new_maturity_date=rep7.maturity_date,
            submission_date=today - datetime.timedelta(days=8),
            review_status="APPROVED",
            review_observations="Replacement FDR verified with renewed 3-year term and confirmed bank lien.",
            reviewed_by="Dr. V. Sharma (Regulation Bureau)",
            completed_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(ren7)
        db.flush()

    f7 = vault_base / "Renewed_FDR_Receipt_SBI_7007.pdf"
    render_bank_fdr_pdf(
        f7, "State Bank of India", "Kothrud Branch, Pune", rep_num7,
        inst1.name, 1500000.00, str(today - datetime.timedelta(days=10)), str(today + datetime.timedelta(days=1085))
    )
    _save_and_attach_document(db, rep7, "FDR_RECEIPT", "Renewed_FDR_Receipt_SBI_7007.pdf", f7)
    results["scenario_7"] = rep7

    # -------------------------------------------------------------------------
    # Scenario 8: Release / Refund Request Awaiting Officer Review
    # -------------------------------------------------------------------------
    inst8 = _create_or_get_institution(db, "1-DEMO-FDR-007", "Apex Technical Institute")
    num8 = "FDR-PNB-2016-8008"
    app8 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num8).first()
    if not app8:
        app8 = DepositInstrument(
            instrument_number=num8,
            institution_id=inst8.id,
            instrument_type="FDR",
            issuing_bank="Punjab National Bank",
            branch_name="Camp Branch, Pune",
            amount=Decimal("1500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=3650),  # 10 years continuous operation
            maturity_date=today + datetime.timedelta(days=365),
            submission_date=today - datetime.timedelta(days=3640),
            lifecycle_status="RELEASE_REQUESTED",
            validity_status="ACTIVE_VALID",
            verification_status="VERIFIED",
            purpose="Ten-Year Maturity Release Corpus"
        )
        db.add(app8)
        db.flush()
    else:
        _clean_instrument_records(db, app8.id)

    f8 = vault_base / "Apex_FDR_Receipt_8008.pdf"
    render_bank_fdr_pdf(
        f8, "Punjab National Bank", "Camp Branch, Pune", num8,
        inst8.name, 1500000.00, str(today - datetime.timedelta(days=3650)), str(today + datetime.timedelta(days=365))
    )
    _save_and_attach_document(db, app8, "FDR_RECEIPT", "Apex_FDR_Receipt_8008.pdf", f8)

    # Attach Release Request
    checklist8 = {
        "continuous_operation_years_satisfied": {"label": "Continuous operation satisfied (10 years completed)", "mandatory": True, "verified": True},
        "no_pending_student_grievances": {"label": "Zero student or faculty fee complaints on record", "mandatory": True, "verified": True},
        "audited_financial_accounts_clean": {"label": "Audited accounts submitted", "mandatory": True, "verified": True},
        "competent_authority_in_principle_approval": {"label": "Regional Committee recommendation", "mandatory": True, "verified": True},
        "original_fdr_discharge_undertaking": {"label": "Original FDR discharge letter received", "mandatory": True, "verified": False}
    }
    rel8 = ReleaseRefundRequest(
        request_number="REL-2026-0001",
        institution_id=inst8.id,
        instrument_id=app8.id,
        request_type="FULL_RELEASE",
        request_date=today - datetime.timedelta(days=5),
        reason="Institution has completed 10 years of unblemished operation. Requesting return of security deposit per APH Chapter I Clause 1.10.",
        conditions_checklist_json=json.dumps(checklist8),
        review_status="SUBMITTED",
        scrutiny_observations="Operational tenure satisfied. Original bank discharge requisition pending receipt from applicant."
    )
    db.add(rel8)
    db.flush()
    results["scenario_8"] = app8

    # -------------------------------------------------------------------------
    # Scenario 9: Returned Release Request Requiring Correction
    # -------------------------------------------------------------------------
    inst9 = _create_or_get_institution(db, "1-DEMO-FDR-008", "Trinity College of Engineering")
    num9 = "FDR-HDFC-2017-9009"
    app9 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num9).first()
    if not app9:
        app9 = DepositInstrument(
            instrument_number=num9,
            institution_id=inst9.id,
            instrument_type="FDR",
            issuing_bank="HDFC Bank",
            branch_name="Bhandarkar Road, Pune",
            amount=Decimal("2000000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=3285),
            maturity_date=today + datetime.timedelta(days=365),
            submission_date=today - datetime.timedelta(days=3280),
            lifecycle_status="RELEASE_REQUESTED",
            validity_status="ACTIVE_VALID",
            verification_status="VERIFIED",
            purpose="Establishment Security Deposit"
        )
        db.add(app9)
        db.flush()
    else:
        _clean_instrument_records(db, app9.id)

    f9 = vault_base / "Trinity_HDFC_Receipt_9009.pdf"
    render_bank_fdr_pdf(
        f9, "HDFC Bank", "Bhandarkar Road, Pune", num9,
        inst9.name, 2000000.00, str(today - datetime.timedelta(days=3285)), str(today + datetime.timedelta(days=365))
    )
    _save_and_attach_document(db, app9, "FDR_RECEIPT", "Trinity_HDFC_Receipt_9009.pdf", f9)

    rel9 = ReleaseRefundRequest(
        request_number="REL-2026-0002",
        institution_id=inst9.id,
        instrument_id=app9.id,
        request_type="FULL_RELEASE",
        request_date=today - datetime.timedelta(days=14),
        reason="Application for return of joint FDR corpus upon completion of prescribed operational period.",
        conditions_checklist_json=json.dumps({
            "continuous_operation_years_satisfied": {"label": "Continuous operation", "mandatory": True, "verified": True},
            "no_pending_student_grievances": {"label": "Student grievances check", "mandatory": True, "verified": True},
            "audited_financial_accounts_clean": {"label": "Audited balance sheet", "mandatory": True, "verified": False}
        }),
        review_status="RETURNED_FOR_CORRECTION",
        decision_remarks="Returned for Correction: FY 2025-2026 audited financial statement and CA certificate omitted from upload. Please resubmit."
    )
    db.add(rel9)
    db.flush()
    results["scenario_9"] = app9

    # -------------------------------------------------------------------------
    # Scenario 10: Completed Release / Refund Case
    # -------------------------------------------------------------------------
    inst10 = _create_or_get_institution(db, "1-DEMO-FDR-009", "Pinnacle College of Engineering")
    num10 = "FDR-BOB-2015-1010"
    app10 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num10).first()
    if not app10:
        app10 = DepositInstrument(
            instrument_number=num10,
            institution_id=inst10.id,
            instrument_type="FDR",
            issuing_bank="Bank of Baroda",
            branch_name="Koregaon Park, Pune",
            amount=Decimal("1500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=4000),
            maturity_date=today - datetime.timedelta(days=350),
            submission_date=today - datetime.timedelta(days=3990),
            lifecycle_status="RELEASED",
            validity_status="MATURED",
            verification_status="VERIFIED",
            purpose="Completed Ten-Year Corpus Release"
        )
        db.add(app10)
        db.flush()
    else:
        _clean_instrument_records(db, app10.id)

    f10 = vault_base / "Pinnacle_BOB_Receipt_1010.pdf"
    render_bank_fdr_pdf(
        f10, "Bank of Baroda", "Koregaon Park, Pune", num10,
        inst10.name, 1500000.00, str(today - datetime.timedelta(days=4000)), str(today - datetime.timedelta(days=350)),
        watermark_text="RELEASED & DISCHARGED"
    )
    _save_and_attach_document(db, app10, "FDR_RECEIPT", "Pinnacle_BOB_Receipt_1010.pdf", f10)

    rel10 = ReleaseRefundRequest(
        request_number="REL-2026-0003",
        institution_id=inst10.id,
        instrument_id=app10.id,
        request_type="FULL_RELEASE",
        request_date=today - datetime.timedelta(days=45),
        reason="Discharge of security deposit post successful 10-year lock-in period.",
        conditions_checklist_json=json.dumps({
            "continuous_operation_years_satisfied": {"label": "Continuous operation", "mandatory": True, "verified": True},
            "no_pending_student_grievances": {"label": "No grievances", "mandatory": True, "verified": True},
            "audited_financial_accounts_clean": {"label": "Audited accounts", "mandatory": True, "verified": True},
            "competent_authority_in_principle_approval": {"label": "In-principle sanction", "mandatory": True, "verified": True},
            "original_fdr_discharge_undertaking": {"label": "Discharge undertaking", "mandatory": True, "verified": True}
        }),
        review_status="COMPLETED",
        decision_record="APPROVED",
        decision_date=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30),
        decided_by="Prof. R. K. Verma (Regional Director / Bureau Head)",
        decision_remarks="Approved: 10-year lock-in period completed satisfactorily with zero student grievances. Lien release sanction issued to Bank of Baroda."
    )
    db.add(rel10)
    db.flush()
    results["scenario_10"] = app10

    # -------------------------------------------------------------------------
    # Scenario 11: External Bank Verification Unavailable (Regional Rural Bank)
    # -------------------------------------------------------------------------
    inst11 = _create_or_get_institution(db, "1-DEMO-FDR-010", "Gramin Polytechnic Institute")
    num11 = "FDR-RURAL-2025-1111"
    app11 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num11).first()
    if not app11:
        app11 = DepositInstrument(
            instrument_number=num11,
            institution_id=inst11.id,
            instrument_type="FDR",
            issuing_bank="Maharashtra Gramin Bank",
            branch_name="Baramati Rural Branch, Pune",
            amount=Decimal("500000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=45),
            maturity_date=today + datetime.timedelta(days=685),
            submission_date=today - datetime.timedelta(days=5),
            lifecycle_status="SUBMITTED",
            validity_status="ACTIVE_VALID",
            verification_status="PENDING",
            purpose="Rural Technical Polytechnic Corpus"
        )
        db.add(app11)
        db.flush()
    else:
        _clean_instrument_records(db, app11.id)

    f11 = vault_base / "Gramin_Bank_Receipt_1111.pdf"
    render_bank_fdr_pdf(
        f11, "Maharashtra Gramin Bank", "Baramati Rural Branch, Pune", num11,
        inst11.name, 500000.00, str(today - datetime.timedelta(days=45)), str(today + datetime.timedelta(days=685))
    )
    _save_and_attach_document(db, app11, "FDR_RECEIPT", "Gramin_Bank_Receipt_1111.pdf", f11)

    f11_lien = vault_base / "Gramin_Lien_1111.pdf"
    render_bank_fdr_pdf(
        f11_lien, "Maharashtra Gramin Bank", "Baramati Rural Branch, Pune", num11,
        inst11.name, 500000.00, str(today - datetime.timedelta(days=45)), str(today + datetime.timedelta(days=685))
    )
    _save_and_attach_document(db, app11, "BANK_LIEN_LETTER", "Gramin_Lien_1111.pdf", f11_lien)

    run_instrument_verification(db, app11)
    results["scenario_11"] = app11

    # -------------------------------------------------------------------------
    # Scenario 12: Unreadable / Corrupted Document Test Case
    # -------------------------------------------------------------------------
    inst12 = _create_or_get_institution(db, "1-DEMO-FDR-011", "Horizon Institute of Technology")
    num12 = "FDR-CORRUPT-2026-1212"
    app12 = db.query(DepositInstrument).filter(DepositInstrument.instrument_number == num12).first()
    if not app12:
        app12 = DepositInstrument(
            instrument_number=num12,
            institution_id=inst12.id,
            instrument_type="FDR",
            issuing_bank="State Bank of India",
            branch_name="Aundh Branch, Pune",
            amount=Decimal("1000000.00"),
            currency="INR",
            issue_date=today - datetime.timedelta(days=30),
            maturity_date=today + datetime.timedelta(days=700),
            submission_date=today - datetime.timedelta(days=2),
            lifecycle_status="SUBMITTED",
            validity_status="ACTIVE_VALID",
            verification_status="UNVERIFIED",
            purpose="Synthetic Corrupted Document Test Case"
        )
        db.add(app12)
        db.flush()
    else:
        _clean_instrument_records(db, app12.id)

    f12 = vault_base / "Corrupted_Payload_Test_1212.pdf"
    render_bank_fdr_pdf(
        f12, "State Bank of India", "Aundh Branch, Pune", num12,
        inst12.name, 1000000.00, str(today - datetime.timedelta(days=30)), str(today + datetime.timedelta(days=700)),
        corrupt_content=True
    )
    _save_and_attach_document(db, app12, "FDR_RECEIPT", "Corrupted_Payload_Test_1212.pdf", f12)
    run_instrument_verification(db, app12)
    results["scenario_12"] = app12

    # Generate initial notifications
    from app.services.notification_service import generate_system_notifications
    generate_system_notifications(db)

    db.commit()
    return {"status": "SUCCESS", "seeded_instruments_count": len(results)}

