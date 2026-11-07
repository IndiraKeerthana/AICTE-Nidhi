from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Finding, ReviewerAction, AuditEvent, Application, Alert
from app.schemas import FindingResponse, ReviewerActionCreate, ReviewerActionResponse

router = APIRouter(tags=["Findings & Reviewer Actions"])

@router.get("/applications/{id}/findings", response_model=list[FindingResponse])
def get_application_findings(id: int, db: Session = Depends(get_db)):
    return db.query(Finding).filter(Finding.application_id == id).all()


@router.post("/findings/{id}/action", response_model=FindingResponse)
def record_reviewer_action(
    id: int,
    payload: ReviewerActionCreate,
    db: Session = Depends(get_db)
):
    finding = db.query(Finding).filter(Finding.id == id).first()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    # 1. Update finding review status based on action
    action_type = payload.action_type.upper()
    valid_actions = {"ACKNOWLEDGE", "REQUEST_DEFICIENCY", "OVERRIDE", "RESOLVE", "RECOMMEND_EVC", "ESCALATE_EVC"}
    if action_type not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type '{action_type}'. Valid options: {list(valid_actions)}"
        )

    if action_type == "ACKNOWLEDGE":
        finding.review_status = "ACKNOWLEDGED"
    elif action_type == "REQUEST_DEFICIENCY":
        finding.review_status = "RECTIFICATION_REQUESTED"
    elif action_type == "OVERRIDE":
        finding.review_status = "OVERRIDDEN"
    elif action_type == "RESOLVE":
        finding.review_status = "RESOLVED"
    elif action_type in ("RECOMMEND_EVC", "ESCALATE_EVC"):
        finding.review_status = "EVC_RECOMMENDED"

    if action_type in ("RESOLVE", "OVERRIDE"):
        linked_alerts = db.query(Alert).filter(
            Alert.application_id == finding.application_id,
            Alert.finding_id == finding.id,
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
        ).all()
        for a in linked_alerts:
            a.status = "RESOLVED"
    elif action_type in ("RECOMMEND_EVC", "ESCALATE_EVC"):
        alert = Alert(
            application_id=finding.application_id,
            finding_id=finding.id,
            alert_type="EVC_ESCALATION",
            severity="Review required",
            title=f"Expert Visit Committee (EVC) Recommended",
            message=f"{payload.reviewer_name or 'Officer'} recommended on-site physical inspection by EVC: {payload.justification_remarks}",
            status="ACTIVE"
        )
        db.add(alert)

    finding.resolution_notes = payload.justification_remarks

    # 2. Record ReviewerAction row
    action = ReviewerAction(
        application_id=finding.application_id,
        finding_id=finding.id,
        action_type=action_type,
        justification_remarks=payload.justification_remarks,
        reviewer_name=payload.reviewer_name or "Scrutiny Officer"
    )
    db.add(action)
    db.flush()

    # 3. Record Hash-Chained Audit Event
    AuditEvent.create_chained(
        db=db,
        application_id=finding.application_id,
        event_type="REVIEWER_ACTION",
        details={
            "finding_code": finding.finding_code,
            "action_type": action_type,
            "justification": payload.justification_remarks,
            "new_status": finding.review_status,
            "reviewer": payload.reviewer_name or "Scrutiny Officer"
        },
        actor=payload.reviewer_name or "Scrutiny Officer"
    )

    db.commit()
    db.refresh(finding)
    return finding
