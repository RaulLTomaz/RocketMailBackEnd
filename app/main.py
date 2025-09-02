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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS.split(",")] if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
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
