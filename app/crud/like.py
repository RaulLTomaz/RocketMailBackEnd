from typing import Dict, List

from databases import Database
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models.like import like
from app.models.post import post


async def _garantir_post_existe(db: Database, post_id: int) -> None:
    row = await db.fetch_one(select(post.c.id).where(post.c.id == post_id))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post não encontrado",
        )


async def dar_like(db: Database, usuario_id: int, post_id: int) -> dict:
    """Idempotente via ON CONFLICT DO NOTHING na PK composta."""
    await _garantir_post_existe(db, post_id)
    stmt = insert(like).values(usuario_id=usuario_id, post_id=post_id)
    stmt = stmt.on_conflict_do_nothing(constraint="like_pkey")
    await db.execute(stmt)
    return {"liked": True, "post_id": post_id}


async def remover_like(db: Database, usuario_id: int, post_id: int) -> dict:
    """Idempotente: remover like inexistente não gera erro."""
    q = like.delete().where(
        (like.c.usuario_id == usuario_id) & (like.c.post_id == post_id)
    )
    await db.execute(q)
    return {"liked": False, "post_id": post_id}


async def contar_likes(db: Database, post_id: int) -> int:
    q = select(func.count()).select_from(like).where(like.c.post_id == post_id)
    return int(await db.fetch_val(q))


async def curtiu(db: Database, usuario_id: int, post_id: int) -> bool:
    q = (
        select(func.count())
        .select_from(like)
        .where((like.c.post_id == post_id) & (like.c.usuario_id == usuario_id))
    )
    return bool(await db.fetch_val(q))


async def resumo_like(db: Database, usuario_id: int, post_id: int) -> dict:
    count = await contar_likes(db, post_id)
    liked = await curtiu(db, usuario_id, post_id)
    return {"post_id": post_id, "count": count, "liked_by_me": liked}


async def batch_resumo_like(
    db: Database, usuario_id: int, post_ids: List[int]
) -> Dict[int, dict]:
    """
    Agrega contagem e liked_by_me em uma passagem.
    No JSON as chaves numéricas viram string (limitação do JSON).
    """
    if not post_ids:
        return {}

    counts_query = (
        select(like.c.post_id, func.count().label("cnt"))
        .where(like.c.post_id.in_(post_ids))
        .group_by(like.c.post_id)
    )
    counts_rows = await db.fetch_all(counts_query)
    counts = {int(r["post_id"]): int(r["cnt"]) for r in counts_rows}

    mine_query = select(like.c.post_id).where(
        (like.c.usuario_id == usuario_id) & (like.c.post_id.in_(post_ids))
    )
    mine_rows = await db.fetch_all(mine_query)
    mine = {int(r["post_id"]) for r in mine_rows}

    out: Dict[int, dict] = {}
    for pid in post_ids:
        out[int(pid)] = {
            "post_id": int(pid),
            "count": counts.get(int(pid), 0),
            "liked_by_me": int(pid) in mine,
        }
    return out
