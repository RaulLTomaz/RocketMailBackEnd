# app/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from databases import Database
from sqlalchemy.orm import declarative_base

# Lê ambiente atual (padrão: "dev")
ENV = os.getenv("PYTHON_ENV", "dev")

# Carrega .env correto
if ENV == "test":
    load_dotenv(".env.test")
else:
    load_dotenv(".env")

# Escolhe URL do banco conforme ambiente
if ENV == "test":
    DATABASE_URL = os.getenv("DATABASE_URL_TEST") or os.getenv("DATABASE_URL")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida (verifique seu .env/.env.test).")

# Instâncias
database = Database(DATABASE_URL)
metadata = MetaData()
engine = create_engine(DATABASE_URL)
Base = declarative_base()

def get_database():
    return database
