from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["Authentication & Roles"])

class UserInfo(BaseModel):
    id: int | None = None
    username: str
    full_name: str
    role: str  # OFFICER, APPROVER, ADMIN, APPLICANT
    designation: str
    institution_id: str | None = None
    email: str | None = None

def get_current_user(
    x_user_role: str | None = Header(None, description="Role of the current user: OFFICER, APPROVER, ADMIN, APPLICANT"),
    x_user_id: str | None = Header(None, description="Username or user identifier"),
    x_institution_id: str | None = Header(None, description="AICTE Permanent ID for applicant users"),
    db: Session = Depends(get_db)
) -> UserInfo:
    """
    Resolves the current authenticated user context and role.
    Defaults safely to OFFICER (Dr. V. Sharma) if no explicit header is provided.
    """
    username = x_user_id or "officer1"
    role = (x_user_role or "OFFICER").upper()

    user_db = db.query(User).filter(User.username == username).first()
    if user_db:
        # If header specifically overrode role in session
        effective_role = role if x_user_role else user_db.role
        effective_inst = x_institution_id or user_db.institution_id
        return UserInfo(
            id=user_db.id,
            username=user_db.username,
            full_name=user_db.full_name,
            role=effective_role,
            designation=user_db.designation,
            institution_id=effective_inst,
            email=user_db.email
        )

    # Fallback user context
    inst_id = x_institution_id if role == "APPLICANT" else None
    designation_map = {
        "OFFICER": "AICTE Scrutiny Officer",
        "APPROVER": "Competent Authority / Regional Officer",
        "ADMIN": "Portal & Regulatory Administrator",
        "APPLICANT": "Authorized Institutional Representative"
    }
    return UserInfo(
        id=None,
        username=username,
        full_name="Dr. V. Sharma" if role == "OFFICER" else ("Prof. R. K. Verma" if role == "APPROVER" else "Authorized User"),
        role=role,
        designation=designation_map.get(role, "AICTE Officer"),
        institution_id=inst_id,
        email=f"{username}@aicte-india.org"
    )

def require_role(*allowed_roles: str):
    def role_checker(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role in {list(allowed_roles)}, current role is '{current_user.role}'."
            )
        return current_user
    return role_checker

@router.get("/users", response_model=list[UserInfo])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()
    return [
        UserInfo(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            designation=u.designation,
            institution_id=u.institution_id,
            email=u.email
        ) for u in users
    ]

@router.get("/current", response_model=UserInfo)
def get_current_user_profile(user: UserInfo = Depends(get_current_user)):
    return user
