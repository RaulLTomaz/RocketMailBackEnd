from collections import defaultdict
from datetime import datetime, timezone

from databases import Database
from fastapi import HTTPException
from sqlalchemy import Integer, asc, bindparam, case, desc, func, literal, select

from app.models.like import like
from app.models.post import post
from app.models.seguir import seguir
from app.models.usuario import usuario
from app.schemas.post import PostCreate


def _row_to_response(row) -> dict:
    foto = getattr(row, "usuario_foto_url", None)
    return {
        "id": row.id,
        "post": row.post,
        "data_criacao": row.data_criacao,
        "usuario": {
            "id": row.usuario_id,
            "nome": row.usuario_nome,
            "foto_url": foto,
        },
    }


_POST_USER_COLS = (
    post.c.id,
    post.c.post,
    post.c.data_criacao,
    usuario.c.id.label("usuario_id"),
    usuario.c.nome.label("usuario_nome"),
    usuario.c.foto_url.label("usuario_foto_url"),
)


async def create_post(db: Database, post_data: PostCreate, usuario_id: int):
    agora = datetime.now(timezone.utc)

    insert_stmt = (
        post.insert()
        .values(
            post=post_data.post,
            usuario_id=usuario_id,
            data_criacao=agora,
        )
        .returning(post.c.id)
    )
    row_id = await db.fetch_one(insert_stmt)
    post_id = row_id["id"] if row_id else None
    if post_id is None:
        raise HTTPException(status_code=500, detail="Falha ao criar post.")

    select_query = (
        select(*_POST_USER_COLS)
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .where(post.c.id == post_id)
    )
    row = await db.fetch_one(select_query)
    return _row_to_response(row)


async def get_posts(
    db: Database, limit: int = 50, offset: int = 0, sort: str = "-data"
):
    """sort: `-data` (mais recente primeiro) ou `data` (crescente)."""
    order_col = (
        desc(post.c.data_criacao) if sort == "-data" else asc(post.c.data_criacao)
    )

    query = (
        select(*_POST_USER_COLS)
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .order_by(order_col)
        .limit(limit)
        .offset(offset)
    )
    rows = await db.fetch_all(query)
    return [_row_to_response(r) for r in rows]


async def get_posts_por_usuario(
    db: Database, usuario_id: int, limit: int = 50, offset: int = 0
):
    query = (
        select(*_POST_USER_COLS)
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .where(usuario.c.id == usuario_id)
        .order_by(desc(post.c.data_criacao))
        .limit(limit)
        .offset(offset)
    )
    rows = await db.fetch_all(query)
    return [_row_to_response(r) for r in rows]


async def get_posts_recentes_por_usuarios(
    db: Database, user_ids: list[int], per_user: int = 5
) -> dict[int, list]:
    """
    Uma query para vários usuários (evita N+1 do search).
    Usa row_number() para limitar posts por autor.
    """
    if not user_ids or per_user <= 0:
        return {}

    rn = (
        func.row_number()
        .over(
            partition_by=post.c.usuario_id,
            order_by=desc(post.c.data_criacao),
        )
        .label("rn")
    )
    ranked = (
        select(*_POST_USER_COLS, rn)
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .where(post.c.usuario_id.in_(user_ids))
    ).subquery()

    query = (
        select(ranked)
        .where(ranked.c.rn <= per_user)
        .order_by(ranked.c.usuario_id, ranked.c.rn)
    )
    rows = await db.fetch_all(query)

    by_user: dict[int, list] = defaultdict(list)
    for row in rows:
        by_user[int(row.usuario_id)].append(_row_to_response(row))
    return by_user


async def get_feed(db: Database, viewer_id: int, limit: int = 50, offset: int = 0):
    """
    Prioriza posts de quem o viewer segue (prioridade 0) e depois o restante (1);
    dentro de cada grupo ordena por data decrescente.

    O viewer_id vai no próprio bindparam (com tipo Integer) para o asyncpg
    não inferir o parâmetro como string.
    """
    viewer_bp = bindparam("viewer_id", type_=Integer, value=viewer_id)

    sub_following = select(seguir.c.seguido_id).where(seguir.c.seguidor_id == viewer_bp)

    prioridade = case(
        (post.c.usuario_id.in_(sub_following), literal(0).cast(Integer)),
        else_=literal(1).cast(Integer),
    ).label("prioridade")

    query = (
        select(prioridade, *_POST_USER_COLS)
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .order_by(prioridade.asc(), desc(post.c.data_criacao))
        .limit(limit)
        .offset(offset)
    )

    rows = await db.fetch_all(query)
    return [_row_to_response(r) for r in rows]


async def delete_post(db: Database, post_id: int, usuario_id: int):
    dono_query = select(post.c.usuario_id).where(post.c.id == post_id)
    dono_row = await db.fetch_one(dono_query)
    if not dono_row:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if dono_row.usuario_id != usuario_id:
        raise HTTPException(
            status_code=403, detail="Sem permissão para deletar este post"
        )

    async with db.transaction():
        # Defensivo: bancos antigos podem não ter ON DELETE CASCADE nos likes.
        await db.execute(like.delete().where(like.c.post_id == post_id))
        await db.execute(post.delete().where(post.c.id == post_id))

    return {"deleted": True, "id": post_id}
