import os
from pathlib import Path

# Configura env de teste ANTES de importar a app (database.py lê no import)
os.environ.setdefault("PYTHON_ENV", "test")
_env_test = Path(__file__).resolve().parent.parent / ".env.test"
if _env_test.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_test, override=False)

# Compat: se só existir DATABASE_URL_TEST
if not os.getenv("DATABASE_URL") and os.getenv("DATABASE_URL_TEST"):
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]

import asyncio
import platform
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import database, engine, metadata
from app import models  # noqa: F401 — registra tabelas no metadata

# Windows precisa desse policy para asyncio + asyncpg
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def preparar_banco():
    # cria o schema 1x por sessão
    metadata.create_all(bind=engine)
    yield
    metadata.drop_all(bind=engine)


# Garante conexão aberta/fechada por teste
@pytest_asyncio.fixture(autouse=True)
async def _ensure_db():
    if not database.is_connected:
        await database.connect()
    try:
        yield
    finally:
        if database.is_connected:
            await database.disconnect()


# Cliente HTTPX com ASGITransport (sem servidor real)
@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
