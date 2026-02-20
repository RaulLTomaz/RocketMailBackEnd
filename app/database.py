# app/database.py
import os
import ssl
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from databases import Database
from sqlalchemy.orm import declarative_base


ENV = os.getenv("PYTHON_ENV", "dev")

if ENV == "test":
    load_dotenv(".env.test")
elif ENV == "dev":
    load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida.")

DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

metadata = MetaData()

# -------- SQLAlchemy (sync) --------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

Base = declarative_base()

# -------- Databases (asyncpg) --------
ssl_context = ssl.create_default_context()
database = Database(
    DATABASE_URL,
    ssl=ssl_context,
)


def get_database():
    return database
