"""
AICTE Deposit Manager — Reports and CSV Export Service
Generates structured financial summaries, filterable reports, and standard CSV downloads.
"""

import io
import csv
import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import DepositInstrument, Institution
from app.services.instrument_service import calculate_validity_status, format_inr, DEFAULT_WARNING_WINDOW_DAYS


def generate_instruments_csv_export(
    db: Session,
    institution_id: Optional[int] = None,
    issuing_bank: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    validity_status: Optional[str] = None,
    verification_status: Optional[str] = None
) -> str:
    """
    Exports filtered instrument register as a sanitized RFC 4180 CSV string.
    """
    query = db.query(DepositInstrument)

    if institution_id:
        query = query.filter(DepositInstrument.institution_id == institution_id)
    if issuing_bank and issuing_bank != "ALL":
        query = query.filter(DepositInstrument.issuing_bank == issuing_bank)
    if lifecycle_status and lifecycle_status != "ALL":
        query = query.filter(DepositInstrument.lifecycle_status == lifecycle_status)
    if verification_status and verification_status != "ALL":
        query = query.filter(DepositInstrument.verification_status == verification_status)

    instruments = query.order_by(DepositInstrument.maturity_date.asc().nullslast()).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header Row
    writer.writerow([
        "Instrument Number",
        "Institution Name",
        "AICTE Permanent ID",
        "Issuing Bank",
        "Branch Name",
        "Deposit Amount (INR)",
        "Issue Date",
        "Maturity Date",
        "Remaining Days",
        "Validity Status",
        "Verification Status",
        "Administrative Lifecycle Status",
        "Lien Marked To",
        "Submission Date"
    ])

    today = datetime.datetime.now(datetime.timezone.utc).date()

    for inst in instruments:
        v_status, remaining = calculate_validity_status(inst.maturity_date, DEFAULT_WARNING_WINDOW_DAYS, as_of_date=today)

        # Apply validity_status filter in memory if specified
        if validity_status and validity_status != "ALL" and v_status != validity_status:
            continue

        writer.writerow([
            inst.instrument_number,
            inst.institution.name if inst.institution else "N/A",
            inst.institution.aicte_permanent_id if inst.institution else "N/A",
            inst.issuing_bank,
            inst.branch_name or "",
            f"{float(inst.amount):.2f}",
            str(inst.issue_date) if inst.issue_date else "N/A",
            str(inst.maturity_date) if inst.maturity_date else "N/A",
            str(remaining) if remaining is not None else "N/A",
            v_status,
            inst.verification_status,
            inst.lifecycle_status,
            inst.lien_marked_to or "Regional Officer, AICTE",
            str(inst.submission_date)
        ])

    return output.getvalue()

