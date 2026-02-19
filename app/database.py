# app/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from databases import Database
from sqlalchemy.orm import declarative_base


ENV = os.getenv("PYTHON_ENV", "dev")

# Em produção (Render) você não precisa de .env, mas manter para dev/test ok.
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

# Normaliza caso venha "postgres://"
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

metadata = MetaData()

# SQLAlchemy (psycopg2) - força SSL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

Base = declarative_base()

# Databases (asyncpg) - força SSL também
# databases repassa kwargs pro driver (asyncpg), então ssl=True funciona.
database = Database(
    DATABASE_URL,
    ssl=True,
)


def get_database():
    return database
