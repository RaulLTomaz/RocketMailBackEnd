"""
Conexão com PostgreSQL.

Usa `databases`/asyncpg para queries async e um engine SQLAlchemy sync
apenas para `create_all` / ALTER no boot (migrations leves).
"""

import os
import ssl

from databases import Database
from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text

ENV = os.getenv("PYTHON_ENV", "dev").lower()

# No Render as variáveis vêm do painel; .env só faz sentido localmente.
if ENV == "test":
    load_dotenv(".env.test")
elif ENV in ("dev", "development"):
    load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and ENV == "test":
    DATABASE_URL = os.getenv("DATABASE_URL_TEST")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não definida.")

# Heroku/Render às vezes entregam o scheme legado postgres://.
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# psycopg2 (engine sync) não aceita o dialect +asyncpg na URL.
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "", 1)

metadata = MetaData()

use_ssl = ENV in ("production", "prod") or os.getenv("DATABASE_SSL", "0") == "1"
ssl_verify = os.getenv("DATABASE_SSL_VERIFY", "0") == "1"


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not ssl_verify:
        # Certificado do Postgres gerenciado no Render costuma falhar em verify-full.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


engine_kwargs: dict = {"pool_pre_ping": True}
if use_ssl:
    engine_kwargs["connect_args"] = {
        "sslmode": "verify-full" if ssl_verify else "require"
    }

engine = create_engine(SYNC_DATABASE_URL, **engine_kwargs)

if use_ssl:
    database = Database(DATABASE_URL, ssl=_build_ssl_context())
else:
    database = Database(DATABASE_URL)


_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_post_usuario_id ON post (usuario_id)",
    "CREATE INDEX IF NOT EXISTS ix_post_data_criacao ON post (data_criacao DESC)",
    'CREATE INDEX IF NOT EXISTS ix_like_post_id ON "like" (post_id)',
    "CREATE INDEX IF NOT EXISTS ix_seguir_seguido_id ON seguir (seguido_id)",
)


def ensure_schema() -> None:
    """
    create_all não altera tabelas existentes; o ALTER cobre colunas novas
    (ex.: foto_url) e índices secundários em bancos já em produção.
    """
    metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE usuario ADD COLUMN IF NOT EXISTS foto_url TEXT"))
        for stmt in _INDEX_STATEMENTS:
            conn.execute(text(stmt))


def get_database() -> Database:
    return database
