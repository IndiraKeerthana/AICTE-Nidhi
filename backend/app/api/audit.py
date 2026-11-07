import json
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventResponse

router = APIRouter(prefix="/audit", tags=["Audit Trail"])

@router.get("/applications/{id}", response_model=list[AuditEventResponse])
def get_application_audit_trail(id: int, db: Session = Depends(get_db)):
    events = db.query(AuditEvent).filter(AuditEvent.application_id == id).order_by(AuditEvent.id.asc()).all()
    results = []
    for e in events:
        try:
            details_dict = json.loads(e.details_json)
        except Exception:
            details_dict = {"raw": e.details_json}
        results.append({
            "id": e.id,
            "application_id": e.application_id,
            "event_type": e.event_type,
            "details": details_dict,
            "actor": e.actor,
            "previous_hash": e.previous_hash,
            "event_hash": e.event_hash,
            "created_at": e.created_at
        })
    return results


@router.get("/verify-chain")
def verify_hash_chain_integrity(db: Session = Depends(get_db)):
    """
    Validates that the append-only audit trail is unbroken.
    Each event must satisfy previous_hash = previous.event_hash.
    """
    events = db.query(AuditEvent).order_by(AuditEvent.id.asc()).all()
    if not events:
        return {"status": "VALID", "total_events": 0, "message": "Audit log is empty."}

    prev_hash = "0" * 64
    for idx, e in enumerate(events):
        if e.previous_hash != prev_hash:
            return {
                "status": "TAMPER_DETECTED",
                "broken_at_event_id": e.id,
                "expected_previous_hash": prev_hash,
                "actual_previous_hash": e.previous_hash,
                "message": f"Hash chain broken at event #{e.id}."
            }
        prev_hash = e.event_hash

    return {
        "status": "VALID",
        "total_events": len(events),
        "genesis_hash": events[0].event_hash if events else None,
        "latest_hash": events[-1].event_hash if events else None,
        "message": "Cryptographic hash chain is intact and tamper-free."
    }
