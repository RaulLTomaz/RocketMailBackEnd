from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table

from app.database import metadata

post = Table(
    "post",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("post", String(280), nullable=False),
    Column(
        "usuario_id",
        Integer,
        ForeignKey("usuario.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "data_criacao",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    ),
)
