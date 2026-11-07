from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api.router import api_router
from app.services.baseline_service import ensure_default_users
from app.services.fdr_demo_data import seed_fdr_demo_scenarios

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize SQLite database tables
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed default synthetic baseline users & 12 demonstration FDR scenarios
    db = SessionLocal()
    try:
        ensure_default_users(db=db)
        seed_fdr_demo_scenarios(db=db, force_refresh=False)
    finally:
        db.close()
    
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="AICTE NIDHI — AICTE Security Deposit and Fixed Deposit Receipt (FDR) Management Portal. Lifecycle tracking, independent verification, automated maturity monitoring, and renewal/release workflow governance.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS configuration
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Root convenience redirect / health
@app.get("/")
def root():
    return {
        "platform": settings.APP_NAME,
        "status": "online",
        "documentation": "/docs",
        "api_health": "/api/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
