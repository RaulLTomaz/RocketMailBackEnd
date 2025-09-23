from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.database import database, engine, metadata
from app.routers import usuario, post, seguir, like
import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

@asynccontextmanager
async def lifespan(app: FastAPI):
    metadata.create_all(bind=engine)
    await database.connect()
    yield
    await database.disconnect()

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
