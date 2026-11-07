from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ScrutinyRun, CheckResult

router = APIRouter(tags=["Scrutiny Runs & Check History"])

@router.get("/applications/{id}/runs")
def list_application_runs(id: int, db: Session = Depends(get_db)):
    runs = db.query(ScrutinyRun).filter(ScrutinyRun.application_id == id).order_by(ScrutinyRun.run_number.asc()).all()
    return [
        {
            "id": r.id,
            "run_number": r.run_number,
            "status": r.status,
            "ruleset_version": r.ruleset_version,
            "total_checks": r.total_checks,
            "passed": r.passed_checks,
            "passed_checks": r.passed_checks,
            "failed": r.failed_checks,
            "failed_checks": r.failed_checks,
            "warnings": r.warnings_count,
            "duration_ms": r.execution_duration_ms,
            "summary_notes": r.summary_notes,
            "created_at": r.created_at,
            "completed_at": r.completed_at
        } for r in runs
    ]

@router.get("/runs/{run_id}")
def get_run_details(run_id: int, db: Session = Depends(get_db)):
    run = db.query(ScrutinyRun).filter(ScrutinyRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scrutiny run not found.")

    return {
        "id": run.id,
        "application_id": run.application_id,
        "run_number": run.run_number,
        "status": run.status,
        "ruleset_version": run.ruleset_version,
        "summary": run.summary_notes,
        "checks": [
            {
                "id": c.id,
                "check_code": c.check_code,
                "category": c.category,
                "status": c.status,
                "expected": c.expected_value,
                "observed": c.observed_value,
                "explanation": c.explanation,
                "severity": c.severity,
                "requires_human_review": c.requires_human_review
            } for c in run.check_results
        ]
    }
