"""Upload de fotos de perfil: Cloudinary em produção; disco local só em dev/test."""
from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger("uvicorn.error")

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


def _env_name() -> str:
    return os.getenv("PYTHON_ENV", "dev").lower()


def _is_production() -> bool:
    return _env_name() in ("production", "prod")


def cloudinary_enabled() -> bool:
    return bool(
        os.getenv("CLOUDINARY_URL")
        or (
            os.getenv("CLOUDINARY_CLOUD_NAME")
            and os.getenv("CLOUDINARY_API_KEY")
            and os.getenv("CLOUDINARY_API_SECRET")
        )
    )


def _configure_cloudinary() -> None:
    import cloudinary

    if os.getenv("CLOUDINARY_URL"):
        cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL"), secure=True)
    else:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )


def _ensure_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


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

    if sniffed:
        content_type = sniffed

    ext = ALLOWED_CONTENT_TYPES[content_type]
    return data, content_type, ext


def _public_url_for_local(filename: str) -> str:
    path = f"{MEDIA_URL_PREFIX}/{filename}"
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}{path}"
    return path


def _upload_cloudinary(data: bytes, content_type: str, usuario_id: int) -> str:
    try:
        import cloudinary.uploader
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Cloudinary não instalado no servidor.",
        ) from e

    _configure_cloudinary()

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
    url = _ensure_https(str(url))
    if not url.startswith("https://"):
        raise HTTPException(
            status_code=500,
            detail="Cloudinary não retornou URL HTTPS (secure_url).",
        )
    return url


def _upload_local(data: bytes, ext: str, usuario_id: int) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
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
    """
    Em produção (Render) exige Cloudinary — disco local é efêmero.
    Em dev/test permite fallback local em /media/avatars.
    """
    data, content_type, ext = await _read_validated(file)

    if cloudinary_enabled():
        return _upload_cloudinary(data, content_type, usuario_id)

    if _is_production():
        logger.error(
            "Upload de foto recusado: Cloudinary não configurado em produção. "
            "Defina CLOUDINARY_URL (ou CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET) no Render."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Upload de foto indisponível: configure CLOUDINARY_URL no Render. "
                "O disco local é efêmero e as fotos somem após redeploy."
            ),
        )

    return _upload_local(data, ext, usuario_id)


def remover_arquivo_local_se_houver(foto_url: str | None) -> None:
    if not foto_url:
        return
    m = re.search(r"/media/avatars/([^/?#]+)$", foto_url)
    if not m:
        return
    path = UPLOAD_DIR / m.group(1)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def remover_foto_cloudinary_se_houver(usuario_id: int) -> None:
    if not cloudinary_enabled():
        return
    try:
        import cloudinary.uploader

        _configure_cloudinary()
        cloudinary.uploader.destroy(
            f"rocketmail/avatars/user_{usuario_id}",
            resource_type="image",
        )
    except Exception:
        logger.exception("Falha ao remover foto no Cloudinary (user_%s)", usuario_id)


def is_ephemeral_media_url(foto_url: str | None) -> bool:
    """True se a URL aponta para storage local /media/avatars (efêmero no Render)."""
    if not foto_url:
        return False
    return "/media/avatars/" in foto_url
