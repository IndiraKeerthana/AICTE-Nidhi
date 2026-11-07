import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Alert, AuditEvent, Application
from app.api.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("")
def list_alerts(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Alert).join(Application, Alert.application_id == Application.id)
    if status_filter:
        s_upper = status_filter.upper()
        if s_upper == "UNRESOLVED":
            query = query.filter(Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
        elif s_upper != "ALL":
            query = query.filter(Alert.status == s_upper)
            
    alerts = query.order_by(Alert.created_at.desc()).all()
    results = []
    for a in alerts:
        app = a.application
        results.append({
            "id": a.id,
            "application_id": a.application_id,
            "finding_id": a.finding_id,
            "scrutiny_run_id": a.scrutiny_run_id,
            "institution_name": app.institution.name if (app and app.institution) else "Unknown Institution",
            "application_reference": app.application_number if app else f"APP-{a.application_id}",
            "application_status": app.status if app else "UNKNOWN",
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "message": a.message,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "acknowledged_by": a.acknowledged_by,
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None
        })
    return results

@router.post("/{id}/acknowledge")
def acknowledge_alert(
    id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    alert.status = "ACKNOWLEDGED"
    username = current_user.get("username", "Scrutiny Officer") if isinstance(current_user, dict) else getattr(current_user, "username", "Scrutiny Officer")
    alert.acknowledged_by = username
    alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)

    AuditEvent.create_chained(
        db=db,
        application_id=alert.application_id,
        event_type="ALERT_ACKNOWLEDGED",
        details={
            "alert_id": alert.id,
            "title": alert.title,
            "acknowledged_by": alert.acknowledged_by
        },
        actor=username
    )

    db.commit()
    return {
        "message": "Alert marked as seen.",
        "id": alert.id,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at.isoformat()
    }
