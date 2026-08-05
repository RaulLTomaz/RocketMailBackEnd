import os
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import database, engine, metadata
from app import models  # noqa: F401 — registra tabelas no metadata
from app.routers import usuario, post, seguir, like
from app.storage import cloudinary_enabled, cloudinary_config_error, cloudinary_url

logger = logging.getLogger("uvicorn.error")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
RUN_MIGRATIONS = os.getenv("RUN_MIGRATIONS", "0") == "1"
UPLOADS_ROOT = Path(os.getenv("UPLOAD_DIR", "uploads/avatars")).resolve().parent


def _ensure_schema():
    """create_all + ALTER seguro para colunas novas em DBs já existentes."""
    metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE usuario ADD COLUMN IF NOT EXISTS foto_url TEXT")
        )


async def _limpar_foto_urls_efemeras():
    """
    Zera foto_url que apontam para /media/avatars (arquivos somem no redeploy do Render).
    Cloudinary HTTPS permanece intacto.
    """
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry DB connect (muito comum o primeiro connect falhar no Render)
    last_err = None
    for attempt in range(1, 6):
        try:
            logger.info(f"Conectando no banco... (tentativa {attempt}/5)")
            await database.connect()
            logger.info("✅ database.connect OK")
            last_err = None
            break
        except Exception as e:
            last_err = e
            logger.exception("⚠️ Falha ao conectar no banco: %s", e)
            await asyncio.sleep(2 * attempt)  # 2s,4s,6s,8s,10s

    if last_err:
        raise last_err  # derruba o app e deixa o Render mostrar o erro final

    if RUN_MIGRATIONS:
        logger.info("RUN_MIGRATIONS=1 -> garantindo schema...")
        try:
            _ensure_schema()
            logger.info("✅ schema OK")
        except Exception:
            logger.exception("Falha ao garantir schema")
            raise

    if cloudinary_enabled():
        cfg_err = cloudinary_config_error()
        if cfg_err:
            logger.error("⚠️ %s", cfg_err)
        else:
            # não loga o secret — só confirma presença/formato
            url = cloudinary_url()
            hint = url.split("@")[-1] if url and "@" in url else "vars CLOUDINARY_*"
            logger.info(
                "✅ Cloudinary configurado (%s) — uploads de foto usam storage durável",
                hint,
            )
    else:
        env = os.getenv("PYTHON_ENV", "dev").lower()
        if env in ("production", "prod"):
            logger.error(
                "⚠️ CLOUDINARY_URL ausente em produção. "
                "POST /usuario/me/foto retornará 503 até configurar Cloudinary no Render."
            )
        else:
            logger.warning("Cloudinary não configurado — usando disco local (dev/test)")

    try:
        await _limpar_foto_urls_efemeras()
    except Exception:
        logger.exception("Falha ao limpar foto_url efêmeras")

    yield

    await database.disconnect()
    logger.info("✅ database.disconnect OK")


app = FastAPI(lifespan=lifespan)

origins_list = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
use_wildcard = (not origins_list) or ("*" in origins_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if use_wildcard else origins_list,
    allow_credentials=False if use_wildcard else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# arquivos locais de avatar em /media/avatars/... (apenas dev/test)
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
