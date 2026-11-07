"""
AICTE Deposit Manager — Notifications & Automated Reminders API
Provides alerts, maturity reminders, and idempotent batch reminder generation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, Institution
from app.schemas import NotificationResponse
from app.services.notification_service import generate_system_notifications
from app.api.auth import get_current_user, require_role, UserInfo

router = APIRouter(prefix="/notifications", tags=["Notifications & Reminders"])


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    is_read: Optional[bool] = Query(None),
    notification_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Lists notifications and reminders for the current user."""
    query = db.query(Notification)

    if current_user.role == "APPLICANT" and current_user.institution_id:
        query = query.join(Institution, Notification.institution_id == Institution.id)\
                     .filter(Institution.aicte_permanent_id == current_user.institution_id)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    if notification_type and notification_type != "ALL":
        query = query.filter(Notification.notification_type == notification_type)

    return query.order_by(Notification.id.desc()).offset(offset).limit(limit).all()


@router.post("/generate")
def trigger_reminder_generation(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role("OFFICER", "ADMIN"))
):
    """
    Executes idempotent reminder scan across all active instruments.
    Detects upcoming maturities, overdue deposits, and pending release actions.
    """
    generated = generate_system_notifications(db)
    db.commit()
    return {
        "status": "COMPLETED",
        "reminders_generated": len(generated),
        "message": f"Successfully evaluated active portfolio. Generated {len(generated)} new reminder notifications."
    }


@router.put("/{id}/read", response_model=NotificationResponse)
def mark_notification_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Marks a notification as read."""
    notif = db.query(Notification).filter(Notification.id == id).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.put("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """Marks all notifications as read for current user."""
    query = db.query(Notification).filter(Notification.is_read == False)
    if current_user.role == "APPLICANT" and current_user.institution_id:
        query = query.join(Institution, Notification.institution_id == Institution.id)\
                     .filter(Institution.aicte_permanent_id == current_user.institution_id)

    count = query.update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"status": "SUCCESS", "marked_read_count": count}

