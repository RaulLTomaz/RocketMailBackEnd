from sqlalchemy import Table, Column, Integer, ForeignKey, PrimaryKeyConstraint
from app.database import metadata

like = Table(
    "like",
    metadata,
    Column("usuario_id", Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
    Column("post_id", Integer, ForeignKey("post.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("usuario_id", "post_id", name="like_pkey"),
)
