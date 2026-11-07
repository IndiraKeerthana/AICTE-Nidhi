"""
AICTE Deposit Manager — Primary API Router
Wires domain routers for dashboard, instruments, institutions, renewals,
releases, notifications, documents, reports, auth, and health.
"""

from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.instruments import router as instruments_router
from app.api.institutions import router as institutions_router
from app.api.renewals import router as renewals_router
from app.api.releases import router as releases_router
from app.api.notifications import router as notifications_router
from app.api.reports import router as reports_router
from app.api.documents import router as documents_router
from app.api.admin import router as admin_router
from app.api.evaluation import router as evaluation_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(evaluation_router)
api_router.include_router(dashboard_router)
api_router.include_router(instruments_router)
api_router.include_router(institutions_router)
api_router.include_router(renewals_router)
api_router.include_router(releases_router)
api_router.include_router(notifications_router)
api_router.include_router(reports_router)
api_router.include_router(documents_router)
