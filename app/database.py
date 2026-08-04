# app/database.py
import os
import ssl
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from databases import Database
from sqlalchemy.orm import declarative_base

ENV = os.getenv("PYTHON_ENV", "dev").lower()

# Só carrega .env localmente (no Render não precisa)
if ENV == "test":
    load_dotenv(".env.test")
elif ENV in ("dev", "development"):
    load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and ENV == "test":
    # compat com nome antigo no .env.test
    DATABASE_URL = os.getenv("DATABASE_URL_TEST")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida.")

# compat: algumas plataformas usam postgres://
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# engine sync (psycopg2) não aceita +asyncpg
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "", 1)

metadata = MetaData()
Base = declarative_base()

# SSL em produção / quando DATABASE_SSL=1
# Render Postgres exige SSL, mas o certificado costuma falhar na verificação estrita.
use_ssl = ENV in ("production", "prod") or os.getenv("DATABASE_SSL", "0") == "1"
ssl_verify = os.getenv("DATABASE_SSL_VERIFY", "0") == "1"


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not ssl_verify:
        # Compatível com Render / certificados self-signed do managed Postgres
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


engine_kwargs = {"pool_pre_ping": True}
if use_ssl:
    # require = criptografa sem verificar CA (verify-full exigiria CA válida)
    engine_kwargs["connect_args"] = {
        "sslmode": "verify-full" if ssl_verify else "require"
    }

engine = create_engine(SYNC_DATABASE_URL, **engine_kwargs)

if use_ssl:
    database = Database(DATABASE_URL, ssl=_build_ssl_context())
else:
    database = Database(DATABASE_URL)


def get_database():
    return database
