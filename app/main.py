import os
import logging
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
    # 1) Migrações/tabelas só se habilitar
    if RUN_MIGRATIONS:
        logger.info("RUN_MIGRATIONS=1 -> criando tabelas...")
        metadata.create_all(bind=engine)
        logger.info("✅ metadata.create_all OK")

    # 2) DB é obrigatório: se falhar, derruba o app (pra ver o erro real no Render)
    logger.info("Conectando no banco...")
    await database.connect()
    logger.info("✅ database.connect OK")

    yield

    logger.info("Desconectando do banco...")
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