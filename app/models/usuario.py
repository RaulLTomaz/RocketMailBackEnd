from sqlalchemy import Column, Integer, String, Table, Text

from app.database import metadata

usuario = Table(
    "usuario",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("nome", String(100), nullable=False),
    Column("email", String(100), nullable=False, unique=True),
    Column("senha", String(200), nullable=False),
    Column("foto_url", Text, nullable=True),
)
