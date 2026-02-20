import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import database, engine, metadata
from app.routers import usuario, post, seguir, like

logger = logging.getLogger("uvicorn.error")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
RUN_MIGRATIONS = os.getenv("RUN_MIGRATIONS", "0") == "1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if RUN_MIGRATIONS:
        logger.info("RUN_MIGRATIONS=1 -> criando tabelas...")
        metadata.create_all(bind=engine)
        logger.info("✅ metadata.create_all OK")

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

@app.get("/healthz", tags=["Infra"])
async def healthz():
    return {"status": "ok"}

app.include_router(usuario.router)
app.include_router(post.router)
app.include_router(seguir.router)
app.include_router(like.router)