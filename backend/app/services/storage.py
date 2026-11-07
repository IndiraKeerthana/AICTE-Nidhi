import os
import hashlib
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from app.config import settings

def calculate_sha256(file_bytes: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()

def validate_and_store_document(application_id: int, file: UploadFile) -> tuple[str, str, int, str]:
    """
    Validates MIME type, size limit, calculates SHA-256, and stores in secure vault.
    Returns: (storage_path, sha256_hash, file_size_bytes, mime_type)
    """
    # 1. Read file bytes
    file_bytes = file.file.read()
    file_size = len(file_bytes)

    # 2. Check file size ceiling
    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB."
        )

    # 3. Check MIME type & extension
    filename = file.filename or "uploaded_file"
    ext = Path(filename).suffix.lower()
    content_type = file.content_type or ""

    valid_extensions = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    if ext not in valid_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: PDF, PNG, JPG, JPEG."
        )

    detected_mime = content_type if content_type in settings.ALLOWED_MIME_TYPES else valid_extensions[ext]

    # 4. Calculate SHA-256 hash
    sha256_hash = calculate_sha256(file_bytes)

    # 5. Create application vault directory
    app_vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(application_id)
    os.makedirs(app_vault_dir, exist_ok=True)

    # 6. Save file with safe hash-prefixed name to avoid path traversal
    safe_filename = f"{sha256_hash[:12]}_{Path(filename).name}"
    storage_path = str(app_vault_dir / safe_filename)

    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    # Reset file pointer if needed
    file.file.seek(0)

    return storage_path, sha256_hash, file_size, detected_mime
