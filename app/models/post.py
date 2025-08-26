from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime
from datetime import datetime, timezone
from app.database import metadata

post = Table(
    "post",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("post", String, nullable=False),
    Column("usuario_id", Integer, ForeignKey("usuario.id")),
    Column("data_criacao", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
)
