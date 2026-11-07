import os
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditEvent, User
from app.api.auth import get_current_user, require_role, UserInfo
from app.services.integration_status import get_all_integration_statuses
from app.services.compliance_rules import compliance_engine

router = APIRouter(prefix="/admin", tags=["System Administration"])

@router.get("/integrations/status")
def get_integration_status(current_user: UserInfo = Depends(require_role("ADMIN", "OFFICER", "APPROVER"))):
    """
    Returns the real connection and simulation status of each upstream & authority adapter.
    """
    return {
        "status": "OPERATIONAL",
        "total_integrations": len(get_all_integration_statuses()),
        "integrations": get_all_integration_statuses()
    }

@router.get("/rules")
def get_admin_rules(current_user: UserInfo = Depends(require_role("ADMIN", "OFFICER", "APPROVER"))):
    """
    Returns the full configuration of APH regulatory rules and categories.
    """
    return compliance_engine.config

@router.put("/rules")
def update_admin_rules(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("ADMIN"))
):
    """
    Restricted to ADMIN: Updates the APH regulatory rules and categories,
    writes to rules YAML, reloads the engine, and logs to Activity History.
    """
    import yaml
    rules_path = compliance_engine.rules_file
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)

    compliance_engine.reload()

    AuditEvent.create_chained(
        db=db,
        application_id=None,
        event_type="RULESET_UPDATED",
        details={
            "ruleset_version": payload.get("ruleset_version", compliance_engine.ruleset_version),
            "updated_by": current_user.full_name,
            "total_rules": len(payload.get("rules", [])),
            "total_categories": len(payload.get("categories", []))
        },
        actor=current_user.full_name or "SYSTEM_ADMIN"
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "message": "Regulatory rules successfully updated and reloaded.",
        "ruleset_version": compliance_engine.ruleset_version
    }

@router.get("/audit")
def get_admin_audit_history(limit: int = 100, db: Session = Depends(get_db), current_user: UserInfo = Depends(require_role("ADMIN", "OFFICER", "APPROVER"))):
    """
    Returns the complete system-wide cryptographic audit event log.
    """
    events = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit).all()
    results = []
    for e in events:
        try:
            details_obj = json.loads(e.details_json)
        except Exception:
            details_obj = {"raw": e.details_json}
        results.append({
            "id": e.id,
            "application_id": e.application_id,
            "event_type": e.event_type,
            "details": details_obj,
            "actor": e.actor,
            "previous_hash": e.previous_hash,
            "event_hash": e.event_hash,
            "created_at": e.created_at
        })
    return results

@router.get("/health-evaluation")
def get_health_and_evaluation_reports(current_user: UserInfo = Depends(require_role("ADMIN", "OFFICER", "APPROVER"))):
    """
    Returns health status and synthetic benchmark evaluation metrics.
    """
    eval_file = Path(__file__).resolve().parent.parent.parent / "evaluation_results.json"
    eval_data = {}
    if eval_file.exists():
        try:
            with open(eval_file, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
        except Exception:
            pass

    return {
        "system_status": "HEALTHY",
        "storage_vault": "VAULT_DIRECTORY_WRITABLE",
        "database": "SQLITE_WAL_ACTIVE",
        "ocr_engine": "PYMUPDF_AVAILABLE",
        "ruleset_active": compliance_engine.ruleset_version,
        "evaluation_metrics": eval_data
    }
