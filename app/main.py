"""
Bootstrap da API: lifespan (DB, schema, Cloudinary), CORS e montagem dos routers.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401 — registra tabelas no MetaData antes do create_all
from app import security  # noqa: F401 — fail-fast se SECRET_KEY inválida em produção
from app.database import database, ensure_schema
from app.routers import like, post, seguir, usuario
from app.storage import cloudinary_config_error, cloudinary_enabled, cloudinary_url

logger = logging.getLogger("uvicorn.error")

ENV = os.getenv("PYTHON_ENV", "dev").lower()
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
# Cobre app de produção e previews: https://*.vercel.app
ALLOWED_ORIGIN_REGEX = os.getenv(
    "ALLOWED_ORIGIN_REGEX",
    r"https://([\w-]+\.)*vercel\.app",
)
RUN_MIGRATIONS = os.getenv("RUN_MIGRATIONS", "0") == "1"
UPLOADS_ROOT = Path(os.getenv("UPLOAD_DIR", "uploads/avatars")).resolve().parent
DB_CONNECT_MAX_ATTEMPTS = 5

_DEFAULT_PROD_ORIGINS = (
    "https://rocket-mail-site.vercel.app",
    "http://localhost:8081",
    "http://localhost:3000",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:3000",
)


def _cors_settings() -> tuple[list[str], str | None, bool]:
    """
    Retorna (origins, origin_regex, allow_credentials).

    Em produção evita `*` (incompatível com credentials) e sempre libera
    `*.vercel.app` via regex, além dos origins explícitos em ALLOWED_ORIGINS.
    """
    raw = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
    wants_wildcard = (not raw) or ("*" in raw)
    regex = (ALLOWED_ORIGIN_REGEX or "").strip() or None

    if ENV in ("production", "prod"):
        explicit = [o for o in raw if o != "*"]
        # Mantém localhost para testar a API de prod a partir do front local.
        origins = list(dict.fromkeys([*explicit, *_DEFAULT_PROD_ORIGINS]))
        if wants_wildcard and not explicit:
            logger.info(
                "CORS produção: origins locais + regex Vercel (%s)",
                regex,
            )
        return origins, regex, True

    if wants_wildcard:
        return ["*"], None, False

    return raw, regex, True


async def _limpar_foto_urls_efemeras():
    """
    URLs /media/avatars deixam de existir após redeploy no Render (disco efêmero).
    Zera esses valores para o front não exibir avatares quebrados; Cloudinary permanece.
    """
    from sqlalchemy import text

    count = await database.fetch_val(
        text(
            "SELECT COUNT(*) FROM usuario "
            "WHERE foto_url IS NOT NULL AND foto_url LIKE '%/media/avatars/%'"
        )
    )
    if not count:
        return
    await database.execute(
        text(
            "UPDATE usuario SET foto_url = NULL "
            "WHERE foto_url IS NOT NULL AND foto_url LIKE '%/media/avatars/%'"
        )
    )
    logger.warning(
        "Limpou %s foto_url efêmera(s) apontando para /media/avatars/",
        int(count),
    )


def _log_cloudinary_status() -> None:
    if cloudinary_enabled():
        cfg_err = cloudinary_config_error()
        if cfg_err:
            logger.error("%s", cfg_err)
            return
        # Loga só o cloud name — nunca a URL completa (contém o secret).
        url = cloudinary_url()
        hint = url.split("@")[-1] if url and "@" in url else "vars CLOUDINARY_*"
        logger.info(
            "Cloudinary configurado (%s) — uploads de foto usam storage durável",
            hint,
        )
        return

    if ENV in ("production", "prod"):
        logger.error(
            "CLOUDINARY_URL ausente em produção. "
            "POST /usuario/me/foto retornará 503 até configurar Cloudinary no Render."
        )
    else:
        logger.warning("Cloudinary não configurado — usando disco local (dev/test)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No cold start do Render o Postgres pode demorar a aceitar conexões.
    last_err = None
    for attempt in range(1, DB_CONNECT_MAX_ATTEMPTS + 1):
        try:
            logger.info("Conectando no banco... (tentativa %s/%s)", attempt, DB_CONNECT_MAX_ATTEMPTS)
            await database.connect()
            logger.info("database.connect OK")
            last_err = None
            break
        except Exception as e:
            last_err = e
            logger.exception("Falha ao conectar no banco: %s", e)
            await asyncio.sleep(2 * attempt)

    if last_err:
        raise last_err

    if RUN_MIGRATIONS:
        logger.info("RUN_MIGRATIONS=1 -> garantindo schema...")
        try:
            ensure_schema()
            logger.info("schema OK")
        except Exception:
            logger.exception("Falha ao garantir schema")
            raise

    _log_cloudinary_status()

    try:
        await _limpar_foto_urls_efemeras()
    except Exception:
        logger.exception("Falha ao limpar foto_url efêmeras")

    yield

    await database.disconnect()
    logger.info("database.disconnect OK")


app = FastAPI(
    title="RocketMail API",
    description="API REST do RocketMail — posts, feed, seguir, likes e perfil.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins, cors_regex, cors_credentials = _cors_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_regex,
    # Com wildcard o browser exige credentials=False.
    allow_credentials=cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fallback de avatares em disco (dev/test). Em produção o caminho é Cloudinary.
UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
(UPLOADS_ROOT / "avatars").mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(UPLOADS_ROOT)), name="media")


@app.get("/healthz", tags=["Infra"])
async def healthz():
    return {"status": "ok"}


app.include_router(usuario.router)
app.include_router(post.router)
app.include_router(seguir.router)
app.include_router(like.router)
