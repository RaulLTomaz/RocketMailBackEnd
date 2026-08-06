from sqlalchemy import Column, ForeignKey, Integer, Table

from app.database import metadata

seguir = Table(
    "seguir",
    metadata,
    Column(
        "seguidor_id",
        Integer,
        ForeignKey("usuario.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "seguido_id",
        Integer,
        ForeignKey("usuario.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)
