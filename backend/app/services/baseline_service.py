"""
AICTE Deposit Manager — Default Baseline & User Initialization Service
Seeds initial synthetic users and system administrators.
"""

from sqlalchemy.orm import Session
from app.models import User, Institution


def ensure_baseline_records(db: Session, aicte_id: str = "1-9988776655", inst_name: str = "Sample Institute of Technology"):
    inst = db.query(Institution).filter(Institution.aicte_permanent_id == aicte_id).first()
    if not inst:
        inst = Institution(
            aicte_permanent_id=aicte_id,
            name=inst_name,
            institution_type="TECHNICAL_INSTITUTE",
            state="Maharashtra",
            district="Pune"
        )
        db.add(inst)
        db.commit()
    ensure_default_users(db)
    return inst


def ensure_default_users(db: Session):
    default_users = [
        {
            "username": "officer1",
            "full_name": "Officer",
            "role": "OFFICER",
            "designation": "Regulation Bureau Officer",
            "email": "officer@aicte-india.org",
            "institution_id": None
        },
        {
            "username": "approver1",
            "full_name": "Prof. R. K. Verma",
            "role": "APPROVER",
            "designation": "Bureau Head / Regional Director",
            "email": "rk.verma@aicte-india.org",
            "institution_id": None
        },
        {
            "username": "admin1",
            "full_name": "AICTE System Administrator",
            "role": "ADMIN",
            "designation": "Deposit Portal Administrator",
            "email": "admin@aicte-india.org",
            "institution_id": None
        },
        {
            "username": "inst_9988",
            "full_name": "Saraswati Institute Registrar",
            "role": "APPLICANT",
            "designation": "Authorized Institutional Representative",
            "email": "registrar@saraswati-tech.edu",
            "institution_id": "1-DEMO-FDR-001"
        }
    ]

    for u in default_users:
        existing = db.query(User).filter(User.username == u["username"]).first()
        if not existing:
            user = User(
                username=u["username"],
                full_name=u["full_name"],
                role=u["role"],
                designation=u["designation"],
                email=u["email"],
                institution_id=u["institution_id"],
                is_active=True
            )
            db.add(user)
        else:
            existing.full_name = u["full_name"]
            existing.designation = u["designation"]
            existing.role = u["role"]

    db.commit()
    return db.query(User).all()
