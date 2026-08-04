"""Upload de fotos de perfil: Cloudinary (se configurado) ou disco local + /media."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

MAX_BYTES = int(os.getenv("FOTO_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 MB
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads/avatars")).resolve()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
MEDIA_URL_PREFIX = "/media/avatars"


def _cloudinary_enabled() -> bool:
    return bool(
        os.getenv("CLOUDINARY_URL")
        or (
            os.getenv("CLOUDINARY_CLOUD_NAME")
            and os.getenv("CLOUDINARY_API_KEY")
            and os.getenv("CLOUDINARY_API_SECRET")
        )
    )


def _sniff_image(data: bytes) -> str | None:
    """Retorna content-type pela assinatura do arquivo, ou None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def _read_validated(file: UploadFile) -> tuple[bytes, str, str]:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo inválido: nome ausente.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio.",
        )
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo muito grande (máx {MAX_BYTES // (1024 * 1024)} MB).",
        )

    sniffed = _sniff_image(data)
    declared = (file.content_type or "").lower().strip()
    content_type = sniffed or (declared if declared in ALLOWED_CONTENT_TYPES else None)

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de arquivo não suportado. Use JPEG, PNG ou WebP.",
        )

    # se o cliente mentiu o MIME mas o sniff passou, confia no sniff
    if sniffed:
        content_type = sniffed

    ext = ALLOWED_CONTENT_TYPES[content_type]
    return data, content_type, ext


def _public_url_for_local(filename: str) -> str:
    path = f"{MEDIA_URL_PREFIX}/{filename}"
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}{path}"
    # fallback relativo — front em outro host precisa de PUBLIC_BASE_URL
    return path


def _upload_cloudinary(data: bytes, content_type: str, usuario_id: int) -> str:
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Cloudinary não instalado no servidor.",
        ) from e

    if os.getenv("CLOUDINARY_URL"):
        cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL"), secure=True)
    else:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )

    result = cloudinary.uploader.upload(
        data,
        folder="rocketmail/avatars",
        public_id=f"user_{usuario_id}",
        overwrite=True,
        resource_type="image",
        format=ALLOWED_CONTENT_TYPES[content_type].lstrip("."),
    )
    url = result.get("secure_url") or result.get("url")
    if not url:
        raise HTTPException(status_code=500, detail="Falha ao obter URL do Cloudinary.")
    return url


def _upload_local(data: bytes, ext: str, usuario_id: int) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # remove extensões antigas do mesmo usuário
    for old in UPLOAD_DIR.glob(f"user_{usuario_id}.*"):
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass
    filename = f"user_{usuario_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(data)
    return _public_url_for_local(filename)


async def salvar_foto_perfil(file: UploadFile, usuario_id: int) -> str:
    data, content_type, ext = await _read_validated(file)
    if _cloudinary_enabled():
        return _upload_cloudinary(data, content_type, usuario_id)
    return _upload_local(data, ext, usuario_id)


def remover_arquivo_local_se_houver(foto_url: str | None) -> None:
    if not foto_url:
        return
    # só apaga se for arquivo nosso sob /media/avatars/
    m = re.search(r"/media/avatars/([^/?#]+)$", foto_url)
    if not m:
        return
    path = UPLOAD_DIR / m.group(1)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def remover_foto_cloudinary_se_houver(usuario_id: int) -> None:
    if not _cloudinary_enabled():
        return
    try:
        import cloudinary
        import cloudinary.uploader

        if os.getenv("CLOUDINARY_URL"):
            cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL"), secure=True)
        else:
            cloudinary.config(
                cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
                api_key=os.getenv("CLOUDINARY_API_KEY"),
                api_secret=os.getenv("CLOUDINARY_API_SECRET"),
                secure=True,
            )
        cloudinary.uploader.destroy(
            f"rocketmail/avatars/user_{usuario_id}",
            resource_type="image",
        )
    except Exception:
        pass
