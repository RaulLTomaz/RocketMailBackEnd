# app/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from databases import Database
from sqlalchemy.orm import declarative_base


ENV = os.getenv("PYTHON_ENV", "dev")

# Em produção (Render), normalmente você NÃO precisa carregar .env.
# Mas manter assim não atrapalha, desde que as variáveis estejam no painel.
if ENV == "test":
    load_dotenv(".env.test")
elif ENV == "dev":
    load_dotenv(".env")


if ENV == "test":
    DATABASE_URL = os.getenv("DATABASE_URL_TEST") or os.getenv("DATABASE_URL")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida (verifique suas env vars / .env).")

# Normaliza caso venha "postgres://" (alguns provedores usam isso)
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Databases (async) ---
# Mantemos como está: o driver usado depende do seu DATABASE_URL e libs instaladas.
database = Database(DATABASE_URL)

# --- SQLAlchemy (sync) ---
# Render/Postgres geralmente exige SSL: forçamos sslmode=require no psycopg2
metadata = MetaData()
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

Base = declarative_base()


def get_database():
    return database
