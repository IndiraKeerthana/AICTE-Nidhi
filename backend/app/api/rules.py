from fastapi import APIRouter
from app.services.compliance_rules import compliance_engine

router = APIRouter(prefix="/rules", tags=["Regulatory Rules"])

@router.get("/categories")
def get_approval_categories():
    """
    Returns the officially configured approval categories and required statutory documents.
    """
    categories = compliance_engine.config.get("categories", [])
    return {
        "ruleset_version": compliance_engine.ruleset_version,
        "academic_year": compliance_engine.config.get("academic_year", "2026-2027"),
        "categories": categories
    }

@router.get("")
def list_regulatory_rules():
    """
    Returns the active AICTE Approval Process Handbook (APH) ruleset.
    """
    return {
        "ruleset_version": compliance_engine.ruleset_version,
        "academic_year": compliance_engine.config.get("academic_year", "2026-2027"),
        "handbook_reference": compliance_engine.config.get("handbook_reference", "AICTE Approval Process Handbook"),
        "status": compliance_engine.config.get("status", "ACTIVE"),
        "total_rules": len(compliance_engine.config.get("rules", [])),
        "rules": compliance_engine.config.get("rules", [])
    }
