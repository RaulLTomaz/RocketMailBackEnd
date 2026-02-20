# app/database.py
import os
import ssl
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from databases import Database
from sqlalchemy.orm import declarative_base

ENV = os.getenv("PYTHON_ENV", "dev")

# Só carrega .env localmente (no Render não precisa)
if ENV == "test":
    load_dotenv(".env.test")
elif ENV == "dev":
    load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida.")

# compat: algumas plataformas usam postgres://
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

metadata = MetaData()
Base = declarative_base()

# engine (sync) - só usado se você ligar RUN_MIGRATIONS=1
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

# databases (asyncpg) - FORÇA SSL
ssl_context = ssl.create_default_context()
database = Database(DATABASE_URL, ssl=ssl_context)

def get_database():
    return database