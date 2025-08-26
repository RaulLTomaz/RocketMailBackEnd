from sqlalchemy import Table, Column, Integer, ForeignKey
from app.database import metadata

seguir = Table(
    "seguir",
    metadata,
    Column("seguidor_id", Integer, ForeignKey("usuario.id"), primary_key=True),
    Column("seguido_id", Integer, ForeignKey("usuario.id"), primary_key=True),
)
