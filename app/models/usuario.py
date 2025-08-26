from sqlalchemy import Table, Column, Integer, String
from app.database import metadata

usuario = Table(
    "usuario",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("nome", String(100), nullable=False),
    Column("email", String(100), nullable=False, unique=True),
    Column("senha", String(200), nullable=False),
)
