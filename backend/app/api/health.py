from fastapi import APIRouter
from app.config import settings
from app.services.document_parser import PYMUPDF_AVAILABLE, TESSERACT_AVAILABLE

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "capabilities": {
            "pymupdf_available": PYMUPDF_AVAILABLE,
            "tesseract_ocr_available": TESSERACT_AVAILABLE,
            "storage_vault_path": settings.STORAGE_VAULT_PATH,
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        }
    }
