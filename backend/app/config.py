import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

class Settings(BaseSettings):
    APP_NAME: str = "AICTE NIDHI — Security Deposit and FDR Management Portal"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'verifyai.db'}"
    
    # Document Storage Vault (Non-public filesystem path)
    STORAGE_VAULT_PATH: str = str(ROOT_DIR / "vault" / "documents")
    MAX_UPLOAD_SIZE_BYTES: int = 26214400  # 25 MB
    ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
    ]
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    # OCR Settings
    ENABLE_OCR: bool = True
    TESSERACT_CMD: str = ""

    # Security & Integration API
    SECRET_KEY: str = "aicte-nidhi-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    INTEGRATION_API_KEY: str = "nidhi-integration-demo-key-2026"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure storage vault directory exists
os.makedirs(settings.STORAGE_VAULT_PATH, exist_ok=True)
