"""
Upload de fotos de perfil.

Em produção o disco do Render é efêmero — exige Cloudinary.
Em dev/test permite gravar em /media/avatars como fallback.
"""

from __future__ import annotations

import asyncio
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
_CLOUDINARY_URL_RE = re.compile(r"^cloudinary://[^:\s]+:[^@\s]+@[^/\s]+")


def _env_name() -> str:
    return os.getenv("PYTHON_ENV", "dev").lower()


def _is_production() -> bool:
    return _env_name() in ("production", "prod")


def _normalize_secret(value: str | None) -> str | None:
    """Remove aspas acidentais coladas no painel do Render."""
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


def cloudinary_url() -> str | None:
    return _normalize_secret(os.getenv("CLOUDINARY_URL"))


def cloudinary_enabled() -> bool:
    url = cloudinary_url()
    if url:
        return True
    return bool(
        _normalize_secret(os.getenv("CLOUDINARY_CLOUD_NAME"))
        and _normalize_secret(os.getenv("CLOUDINARY_API_KEY"))
        and _normalize_secret(os.getenv("CLOUDINARY_API_SECRET"))
    )


def cloudinary_config_error() -> str | None:
    """Mensagem se CLOUDINARY_URL existe mas está malformada; None se ok ou ausente."""
    url = cloudinary_url()
    if url and not _CLOUDINARY_URL_RE.match(url):
        return (
            "CLOUDINARY_URL inválida. Use o formato "
            "cloudinary://API_KEY:API_SECRET@CLOUD_NAME (sem aspas extras)."
        )
    return None


def _configure_cloudinary() -> None:
    import cloudinary

    err = cloudinary_config_error()
    if err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=err)

    url = cloudinary_url()
    if url:
        cloudinary.config(cloudinary_url=url, secure=True)
        return

    cloudinary.config(
        cloud_name=_normalize_secret(os.getenv("CLOUDINARY_CLOUD_NAME")),
        api_key=_normalize_secret(os.getenv("CLOUDINARY_API_KEY")),
        api_secret=_normalize_secret(os.getenv("CLOUDINARY_API_SECRET")),
        secure=True,
    )


def _ensure_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def _sniff_image(data: bytes) -> str | None:
    """Detecta MIME pela assinatura do arquivo (mais confiável que o Content-Type do client)."""
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


def _map_cloudinary_error(exc: Exception) -> HTTPException:
    msg = str(exc) or type(exc).__name__
    lower = msg.lower()
    if any(
        x in lower
        for x in ("invalid", "unauthorized", "api key", "authentication", "401")
    ):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Credenciais Cloudinary inválidas: {type(exc).__name__}: {msg}",
        )
    if any(
        x in lower for x in ("timeout", "timed out", "connection", "network", "resolve")
    ):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Timeout/rede ao falar com Cloudinary: {type(exc).__name__}: {msg}",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Falha no upload Cloudinary: {type(exc).__name__}: {msg}",
    )


def _upload_cloudinary_sync(data: bytes, content_type: str, usuario_id: int) -> str:
    try:
        import cloudinary.uploader
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Pacote cloudinary não instalado no servidor. Verifique requirements.txt.",
        ) from e

    _configure_cloudinary()

    try:
        result = cloudinary.uploader.upload(
            data,
            folder="rocketmail/avatars",
            public_id=f"user_{usuario_id}",
            overwrite=True,
            resource_type="image",
            format=ALLOWED_CONTENT_TYPES[content_type].lstrip("."),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("cloudinary.uploader.upload falhou (user_%s)", usuario_id)
        raise _map_cloudinary_error(e) from e

    url = result.get("secure_url") or result.get("url")
    if not url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cloudinary não retornou secure_url.",
        )
    url = _ensure_https(str(url))
    if not url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cloudinary não retornou URL HTTPS (secure_url).",
        )
    if "res.cloudinary.com" not in url and "cloudinary.com" not in url:
        logger.warning("URL Cloudinary inesperada: %s", url)
    return url


async def _upload_cloudinary(data: bytes, content_type: str, usuario_id: int) -> str:
    # SDK síncrono: to_thread evita bloquear o event loop (timeout/worker morto sem CORS).
    try:
        return await asyncio.to_thread(
            _upload_cloudinary_sync, data, content_type, usuario_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Falha inesperada no upload Cloudinary (user_%s)", usuario_id)
        raise _map_cloudinary_error(e) from e


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
    """Produção exige Cloudinary; dev/test pode usar disco local."""
    data, content_type, ext = await _read_validated(file)

    cfg_err = cloudinary_config_error()
    if cfg_err and _is_production():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=cfg_err,
        )

    if cloudinary_enabled() and not cfg_err:
        return await _upload_cloudinary(data, content_type, usuario_id)

    if _is_production():
        logger.error(
            "Upload de foto recusado: Cloudinary não configurado em produção. "
            "Defina CLOUDINARY_URL (ou CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET) no Render."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Upload de foto indisponível: configure CLOUDINARY_URL no Render. "
                "Formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME"
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
    if not cloudinary_enabled() or cloudinary_config_error():
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
    """Identifica URLs locais que somem após redeploy no Render."""
    if not foto_url:
        return False
    return "/media/avatars/" in foto_url
