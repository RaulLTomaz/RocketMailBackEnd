import os
from pathlib import Path

# Configura env de teste ANTES de importar a app (database.py lê no import)
os.environ.setdefault("PYTHON_ENV", "test")
_env_test = Path(__file__).resolve().parent.parent / ".env.test"
if _env_test.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_test, override=False)

if not os.getenv("DATABASE_URL") and os.getenv("DATABASE_URL_TEST"):
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]

import asyncio
import platform
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import database, engine, metadata
from app import models  # noqa: F401

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def preparar_banco():
    from sqlalchemy import text

    metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE usuario ADD COLUMN IF NOT EXISTS foto_url TEXT"))
    yield
    metadata.drop_all(bind=engine)


@pytest_asyncio.fixture(autouse=True)
async def _ensure_db():
    if not database.is_connected:
        await database.connect()
    try:
        yield
    finally:
        if database.is_connected:
            await database.disconnect()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
