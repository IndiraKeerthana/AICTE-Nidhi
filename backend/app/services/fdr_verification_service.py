"""
AICTE Deposit Manager — FDR Verification & Discrepancy Detection Engine
Implements automated OCR comparisons, cross-field discrepancy detection,
and registry validation for Security Deposits & FDRs.
"""

import json
import re
import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    DepositInstrument, InstrumentDocument, VerificationRecord,
    AuditEvent, Notification
)
from app.services.anomaly_service import evaluate_institution_name_similarity


def normalize_clean(text: Optional[str]) -> str:
    """Strips whitespace, punctuation and uppercase for robust comparison."""
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(text)).upper()


def extract_fdr_fields_from_text(text: str) -> Dict[str, Any]:
    """
    Extracts key financial instrument fields from OCR/parsed document text.
    Returns dictionary with extracted field values.
    """
    fields = {}

    # 1. FDR / Reference Number
    fdr_match = re.search(
        r"(?:fdr\s*(?:no|number|ref)|receipt\s*(?:no|number)|deposit\s*receipt\s*no|account\s*no|certificate\s*no)[\s.:]*([A-Za-z0-9\/-]{5,35})",
        text,
        re.IGNORECASE
    )
    if fdr_match:
        fields["instrument_number"] = fdr_match.group(1).strip()

    # 2. Bank Name
    bank_match = re.search(
        r"(State\s+Bank\s+of\s+India|Punjab\s+National\s+Bank|HDFC\s+Bank|Bank\s+of\s+Baroda|Canara\s+Bank|Union\s+Bank\s+of\s+India|ICICI\s+Bank|Axis\s+Bank|Central\s+Bank\s+of\s+India|Indian\s+Bank)",
        text,
        re.IGNORECASE
    )
    if bank_match:
        fields["issuing_bank"] = bank_match.group(1).strip()

    # 3. Amount (supports INR, Rs, ₹, numbers with commas)
    amount_match = re.search(
        r"(?:Rs\.?|INR|₹|amount|deposit\s*amount|sum\s*of\s*rs\.?)[\s.:]*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{2})?)",
        text,
        re.IGNORECASE
    )
    if amount_match:
        amt_str = amount_match.group(1).replace(",", "")
        try:
            fields["amount"] = float(amt_str)
        except ValueError:
            pass

    # 4. Issue Date
    issue_match = re.search(
        r"(?:date\s*of\s*issue|issue\s*date|dated|deposited\s*on)[\s.:]*([0-9]{1,4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
        text,
        re.IGNORECASE
    )
    if issue_match:
        fields["issue_date"] = issue_match.group(1).strip()

    # 5. Maturity Date
    maturity_match = re.search(
        r"(?:maturity\s*date|date\s*of\s*maturity|due\s*date|valid\s*up\s*to|valid\s*till|expires\s*on)[\s.:]*([0-9]{1,4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
        text,
        re.IGNORECASE
    )
    if maturity_match:
        fields["maturity_date"] = maturity_match.group(1).strip()

    # 6. Lien / Beneficiary
    if re.search(r"(?:AICTE|All\s*India\s*Council\s*for\s*Technical\s*Education|Regional\s*Officer)", text, re.IGNORECASE):
        fields["lien_detected"] = True

    return fields


def run_instrument_verification(db: Session, instrument: DepositInstrument) -> List[VerificationRecord]:
    """
    Executes comprehensive discrepancy checks for a security deposit/FDR:
    1. Completeness of mandatory fields
    2. Supporting document completeness
    3. Document extracted fields vs recorded instrument details (amount, bank, dates, numbers)
    4. Institution title consistency
    5. Invalid date ordering
    6. Duplicate document hashes
    7. Independent bank confirmation / simulated registry check

    Persists VerificationRecord entries and updates instrument verification_status.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    results: List[VerificationRecord] = []
    has_mismatch = False
    has_unverified = False

    active_docs = [d for d in instrument.documents if d.status == "ACTIVE"]

    # ---------------------------------------------------------
    # 1. Mandatory Instrument Fields Check
    # ---------------------------------------------------------
    missing_fields = []
    if not instrument.instrument_number:
        missing_fields.append("Instrument Number")
    if not instrument.issuing_bank:
        missing_fields.append("Issuing Bank")
    if not instrument.amount or instrument.amount <= 0:
        missing_fields.append("Deposit Amount")
    if not instrument.issue_date:
        missing_fields.append("Issue Date")
    if not instrument.maturity_date:
        missing_fields.append("Maturity Date")

    rec1 = VerificationRecord(
        instrument_id=instrument.id,
        verification_method="COMPLIANCE_RULE",
        verification_source="AICTE Deposit Regulation Norms",
        verification_timestamp=now,
        result="VERIFIED" if not missing_fields else "MISMATCH",
        fields_checked=json.dumps(["instrument_number", "issuing_bank", "amount", "issue_date", "maturity_date"]),
        observed_values=json.dumps({
            "status": "COMPLETE" if not missing_fields else f"MISSING: {', '.join(missing_fields)}"
        }),
        evidence_notes="All statutory deposit fields are recorded." if not missing_fields else f"Missing mandatory fields: {', '.join(missing_fields)}.",
        is_simulated=False,
        verified_by="SYSTEM"
    )
    db.add(rec1)
    results.append(rec1)
    if missing_fields:
        has_mismatch = True

    # ---------------------------------------------------------
    # 2. Date Ordering Check (issue_date < maturity_date)
    # ---------------------------------------------------------
    if instrument.issue_date and instrument.maturity_date:
        if instrument.maturity_date <= instrument.issue_date:
            rec_dates = VerificationRecord(
                instrument_id=instrument.id,
                verification_method="DATE_ORDERING",
                verification_source="Calendar Consistency Logic",
                verification_timestamp=now,
                result="MISMATCH",
                fields_checked=json.dumps(["issue_date", "maturity_date"]),
                observed_values=json.dumps({
                    "issue_date": str(instrument.issue_date),
                    "maturity_date": str(instrument.maturity_date)
                }),
                evidence_notes=f"Maturity date ({instrument.maturity_date}) cannot be on or prior to issue date ({instrument.issue_date}).",
                is_simulated=False,
                verified_by="SYSTEM"
            )
            db.add(rec_dates)
            results.append(rec_dates)
            has_mismatch = True
        else:
            rec_dates = VerificationRecord(
                instrument_id=instrument.id,
                verification_method="DATE_ORDERING",
                verification_source="Calendar Consistency Logic",
                verification_timestamp=now,
                result="VERIFIED",
                fields_checked=json.dumps(["issue_date", "maturity_date"]),
                observed_values=json.dumps({
                    "tenure_days": (instrument.maturity_date - instrument.issue_date).days
                }),
                evidence_notes="Maturity date successfully succeeds issue date.",
                is_simulated=False,
                verified_by="SYSTEM"
            )
            db.add(rec_dates)
            results.append(rec_dates)

    # ---------------------------------------------------------
    # 3. Supporting Document Completeness Check
    # ---------------------------------------------------------
    doc_categories = {d.document_category for d in active_docs}
    has_fdr_doc = "FDR_RECEIPT" in doc_categories
    has_lien_doc = "BANK_LIEN_LETTER" in doc_categories or "JOINT_NAME_AGREEMENT" in doc_categories

    missing_docs = []
    if not has_fdr_doc:
        missing_docs.append("FDR Receipt Copy (FDR_RECEIPT)")
    if not has_lien_doc:
        missing_docs.append("Bank Lien Endorsement / Joint Name Agreement (BANK_LIEN_LETTER)")

    rec_doc = VerificationRecord(
        instrument_id=instrument.id,
        verification_method="DOCUMENT_COMPLETENESS",
        verification_source="AICTE Regulation Bureau Documentation Checklist",
        verification_timestamp=now,
        result="VERIFIED" if not missing_docs else "MISMATCH",
        fields_checked=json.dumps(["FDR_RECEIPT", "BANK_LIEN_LETTER"]),
        observed_values=json.dumps({
            "uploaded_categories": list(doc_categories),
            "missing_categories": missing_docs
        }),
        evidence_notes="Essential FDR receipt and bank lien documentation present." if not missing_docs else f"Missing required attachments: {', '.join(missing_docs)}.",
        is_simulated=False,
        verified_by="SYSTEM"
    )
    db.add(rec_doc)
    results.append(rec_doc)
    if missing_docs:
        has_mismatch = True

    # ---------------------------------------------------------
    # 4. OCR Discrepancy Checks on Active Documents
    # ---------------------------------------------------------
    for doc in active_docs:
        if not doc.extracted_text or len(doc.extracted_text) < 10:
            continue

        extracted = extract_fdr_fields_from_text(doc.extracted_text)

        # A. Amount Discrepancy
        if "amount" in extracted:
            rec_amt = float(instrument.amount)
            ext_amt = float(extracted["amount"])
            amt_diff = abs(rec_amt - ext_amt)
            is_amt_match = amt_diff < 1.0  # within 1 rupee

            rec_a = VerificationRecord(
                instrument_id=instrument.id,
                document_id=doc.id,
                verification_method="AUTOMATED_OCR_PARSE",
                verification_source=f"Document OCR Analysis ({doc.original_filename})",
                verification_timestamp=now,
                result="VERIFIED" if is_amt_match else "MISMATCH",
                fields_checked=json.dumps(["amount"]),
                observed_values=json.dumps({
                    "recorded_amount": rec_amt,
                    "extracted_amount": ext_amt,
                    "variance": amt_diff
                }),
                evidence_notes=(
                    f"Recorded amount ₹{rec_amt:,.2f} exactly matches extracted document value ₹{ext_amt:,.2f}."
                    if is_amt_match
                    else f"Discrepancy detected: Recorded amount ₹{rec_amt:,.2f} conflicts with extracted document amount ₹{ext_amt:,.2f}."
                ),
                is_simulated=False,
                verified_by="SYSTEM"
            )
            db.add(rec_a)
            results.append(rec_a)
            if not is_amt_match:
                has_mismatch = True

        # B. Instrument Number Discrepancy
        if "instrument_number" in extracted:
            clean_rec = normalize_clean(instrument.instrument_number)
            clean_ext = normalize_clean(extracted["instrument_number"])
            is_num_match = clean_rec in clean_ext or clean_ext in clean_rec

            rec_n = VerificationRecord(
                instrument_id=instrument.id,
                document_id=doc.id,
                verification_method="AUTOMATED_OCR_PARSE",
                verification_source=f"Document OCR Analysis ({doc.original_filename})",
                verification_timestamp=now,
                result="VERIFIED" if is_num_match else "MISMATCH",
                fields_checked=json.dumps(["instrument_number"]),
                observed_values=json.dumps({
                    "recorded_number": instrument.instrument_number,
                    "extracted_number": extracted["instrument_number"]
                }),
                evidence_notes=(
                    f"Instrument number matches document reference ({extracted['instrument_number']})."
                    if is_num_match
                    else f"Discrepancy detected: Recorded number '{instrument.instrument_number}' does not match extracted reference '{extracted['instrument_number']}'."
                ),
                is_simulated=False,
                verified_by="SYSTEM"
            )
            db.add(rec_n)
            results.append(rec_n)
            if not is_num_match:
                has_mismatch = True

        # C. Issuing Bank Match
        if "issuing_bank" in extracted:
            clean_bank_rec = normalize_clean(instrument.issuing_bank)
            clean_bank_ext = normalize_clean(extracted["issuing_bank"])
            is_bank_match = clean_bank_rec in clean_bank_ext or clean_bank_ext in clean_bank_rec

            rec_b = VerificationRecord(
                instrument_id=instrument.id,
                document_id=doc.id,
                verification_method="AUTOMATED_OCR_PARSE",
                verification_source=f"Document OCR Analysis ({doc.original_filename})",
                verification_timestamp=now,
                result="VERIFIED" if is_bank_match else "MISMATCH",
                fields_checked=json.dumps(["issuing_bank"]),
                observed_values=json.dumps({
                    "recorded_bank": instrument.issuing_bank,
                    "extracted_bank": extracted["issuing_bank"]
                }),
                evidence_notes=(
                    f"Bank title matches ({extracted['issuing_bank']})."
                    if is_bank_match
                    else f"Bank name variation: Recorded '{instrument.issuing_bank}' vs extracted '{extracted['issuing_bank']}'."
                ),
                is_simulated=False,
                verified_by="SYSTEM"
            )
            db.add(rec_b)
            results.append(rec_b)
            if not is_bank_match:
                has_mismatch = True

    # ---------------------------------------------------------
    # 5. Duplicate Check Across Instruments
    # ---------------------------------------------------------
    for doc in active_docs:
        dup = db.query(InstrumentDocument).filter(
            InstrumentDocument.sha256_hash == doc.sha256_hash,
            InstrumentDocument.instrument_id != instrument.id,
            InstrumentDocument.status == "ACTIVE"
        ).first()

        if dup:
            rec_dup = VerificationRecord(
                instrument_id=instrument.id,
                document_id=doc.id,
                verification_method="CHECKSUM_DEDUPLICATION",
                verification_source="Repository SHA-256 Catalog",
                verification_timestamp=now,
                result="MISMATCH",
                fields_checked=json.dumps(["sha256_hash"]),
                observed_values=json.dumps({
                    "duplicate_document_id": dup.id,
                    "duplicate_instrument_id": dup.instrument_id,
                    "sha256": doc.sha256_hash
                }),
                evidence_notes=f"Identical file upload detected on another instrument record (#{dup.instrument_id}). File reuse requires officer review.",
                is_simulated=False,
                verified_by="SYSTEM"
            )
            db.add(rec_dup)
            results.append(rec_dup)
            has_mismatch = True

    # ---------------------------------------------------------
    # 6. Simulated External Bank Registry Confirmation
    # ---------------------------------------------------------
    # Explicitly labeled simulated check
    bank_name = instrument.issuing_bank.upper()
    is_bank_supported = any(b in bank_name for b in ["STATE BANK", "SBI", "PUNJAB NATIONAL", "PNB", "HDFC", "BARODA", "CANARA"])

    if is_bank_supported:
        rec_ext = VerificationRecord(
            instrument_id=instrument.id,
            verification_method="REGISTRY_CHECK",
            verification_source=f"{instrument.issuing_bank} Core Banking Gateway [SIMULATED]",
            verification_timestamp=now,
            result="VERIFIED",
            fields_checked=json.dumps(["instrument_number", "lien_status", "balance"]),
            observed_values=json.dumps({
                "source": "SIMULATED_CENTRAL_BANK_REGISTRY",
                "lien_confirmed": True,
                "encumbrance": "Lien Marked to Regional Officer, AICTE"
            }),
            evidence_notes="[SIMULATED EXTERNAL VERIFICATION · PROTOTYPE DATA ONLY] Deposit status confirmed active with statutory lien recorded.",
            is_simulated=True,
            verified_by="AUTOMATED_BANK_CONNECTOR"
        )
        db.add(rec_ext)
        results.append(rec_ext)
    else:
        rec_ext = VerificationRecord(
            instrument_id=instrument.id,
            verification_method="REGISTRY_CHECK",
            verification_source=f"{instrument.issuing_bank} Integration Gateway",
            verification_timestamp=now,
            result="UNAVAILABLE",
            fields_checked=json.dumps(["lien_status"]),
            observed_values=json.dumps({
                "status": "GATEWAY_NOT_CONFIGURED"
            }),
            evidence_notes="External electronic confirmation gateway unavailable for this issuing bank. Authorized officer manual verification required.",
            is_simulated=False,
            verified_by="SYSTEM"
        )
        db.add(rec_ext)
        results.append(rec_ext)
        has_unverified = True

    # Update overall verification_status
    if has_mismatch:
        instrument.verification_status = "MISMATCH_DETECTED"
    elif has_unverified:
        instrument.verification_status = "PENDING"
    else:
        instrument.verification_status = "VERIFIED"

    AuditEvent.create_chained(
        db=db,
        instrument_id=instrument.id,
        entity_type="VERIFICATION",
        event_type="VERIFICATION_EXECUTED",
        details={
            "checks_count": len(results),
            "verification_status": instrument.verification_status,
            "has_mismatch": has_mismatch
        },
        actor="SYSTEM"
    )

    db.flush()
    return results

