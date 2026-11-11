import base64
import os
import re
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class Base64ImageUpload(BaseModel):
    filename: str = "image.png"
    data: str  # Puede ser "data:image/png;base64,iVBOR..." o base64 puro


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\.-]", "_", name)
    return name[:50]


@router.post("/image")
def upload_image(file: UploadFile = File(...)):
    """Sube un archivo de imagen (JPEG, PNG, WEBP, GIF, SVG)."""
    ext = Path(file.filename or "image.png").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido ({ext}). Use {', '.join(ALLOWED_EXTENSIONS)}",
        )

    safe_name = sanitize_filename(file.filename or "image")
    unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    target_path = UPLOAD_DIR / unique_name

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar la imagen: {str(e)}")

    return {
        "url": f"/uploads/{unique_name}",
        "filename": unique_name,
        "message": "Imagen subida correctamente",
    }


@router.post("/image-base64")
def upload_image_base64(payload: Base64ImageUpload):
    """Permite subir una imagen en Base64 directamente desde el frontend."""
    raw_data = payload.data
    ext = ".png"

    if "," in raw_data and "data:" in raw_data:
        header, raw_data = raw_data.split(",", 1)
        if "jpeg" in header or "jpg" in header:
            ext = ".jpg"
        elif "webp" in header:
            ext = ".webp"
        elif "gif" in header:
            ext = ".gif"
        elif "svg" in header:
            ext = ".svg"
    else:
        ext = Path(payload.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".png"

    try:
        binary_data = base64.b64decode(raw_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 inválido")

    if len(binary_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 10 MB")

    safe_name = sanitize_filename(payload.filename or "image.png")
    if not safe_name.endswith(ext):
        safe_name = f"{Path(safe_name).stem}{ext}"

    unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    target_path = UPLOAD_DIR / unique_name

    try:
        with open(target_path, "wb") as f:
            f.write(binary_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al escribir archivo: {str(e)}")

    return {
        "url": f"/uploads/{unique_name}",
        "filename": unique_name,
        "message": "Imagen subida correctamente",
    }
