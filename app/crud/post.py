from sqlalchemy import select, desc, asc, case, bindparam, Integer, literal
from databases import Database
from datetime import datetime, timezone
from fastapi import HTTPException
from app.models.post import post
from app.models.usuario import usuario
from app.models.seguir import seguir
from app.schemas.post import PostCreate


def _row_to_response(row):
    return {
        "id": row.id,
        "post": row.post,
        "data_criacao": row.data_criacao,
        "usuario": {
            "id": row.usuario_id,
            "nome": row.usuario_nome,
        },
    }


async def create_post(db: Database, post_data: PostCreate, usuario_id: int):
    agora = datetime.now(timezone.utc)

    query = post.insert().values(
        post=post_data.post,
        usuario_id=usuario_id,
        data_criacao=agora,
    )
    post_id = await db.execute(query)

    select_query = (
        select(
            post.c.id,
            post.c.post,
            post.c.data_criacao,
            usuario.c.id.label("usuario_id"),
            usuario.c.nome.label("usuario_nome"),
        )
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .where(post.c.id == post_id)
    )

    row = await db.fetch_one(select_query)
    return _row_to_response(row)


async def get_posts(db: Database, limit: int = 50, offset: int = 0, sort: str = "-data"):
    """
    Lista posts com paginação.
    sort:
        - "-data" (default) => data_criacao desc
        - "data"            => data_criacao asc
    """
    order_col = desc(post.c.data_criacao) if sort == "-data" else asc(post.c.data_criacao)

    query = (
        select(
            post.c.id,
            post.c.post,
            post.c.data_criacao,
            usuario.c.id.label("usuario_id"),
            usuario.c.nome.label("usuario_nome"),
        )
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
    """
    Timeline pública do usuário (paginada).
    """
    query = (
        select(
            post.c.id,
            post.c.post,
            post.c.data_criacao,
            usuario.c.id.label("usuario_id"),
            usuario.c.nome.label("usuario_nome"),
        )
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .where(usuario.c.id == usuario_id)
        .order_by(desc(post.c.data_criacao))
        .limit(limit)
        .offset(offset)
    )
    rows = await db.fetch_all(query)
    return [_row_to_response(r) for r in rows]


async def get_feed(db: Database, viewer_id: int, limit: int = 50, offset: int = 0):
    """
    Feed:
        - Primeiro posts de quem o viewer segue (prioridade=0), depois os demais (prioridade=1)
        - Dentro de cada grupo, ordem decrescente por data.
        - Binda viewer_id no próprio bindparam (sem passar values no fetch_all).
    """
    # binda com tipo e valor para evitar inferência errada (asyncpg esperando str)
    viewer_bp = bindparam("viewer_id", type_=Integer, value=viewer_id)

    sub_following = select(seguir.c.seguido_id).where(seguir.c.seguidor_id == viewer_bp)

    prioridade = case(
        (post.c.usuario_id.in_(sub_following), literal(0).cast(Integer)),
        else_=literal(1).cast(Integer),
    ).label("prioridade")

    query = (
        select(
            prioridade,
            post.c.id,
            post.c.post,
            post.c.data_criacao,
            usuario.c.id.label("usuario_id"),
            usuario.c.nome.label("usuario_nome"),
        )
        .select_from(post.join(usuario, post.c.usuario_id == usuario.c.id))
        .order_by(prioridade.asc(), desc(post.c.data_criacao))
        .limit(limit)
        .offset(offset)
    )

    rows = await db.fetch_all(query)

    # Descarta 'prioridade' no response
    return [
        {
            "id": r.id,
            "post": r.post,
            "data_criacao": r.data_criacao,
            "usuario": {"id": r.usuario_id, "nome": r.usuario_nome},
        }
        for r in rows
    ]


async def delete_post(db: Database, post_id: int, usuario_id: int):
    dono_query = select(post.c.usuario_id).where(post.c.id == post_id)
    dono_row = await db.fetch_one(dono_query)
    if not dono_row:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    if dono_row.usuario_id != usuario_id:
        raise HTTPException(status_code=403, detail="Sem permissão para deletar este post")
    await db.execute(post.delete().where(post.c.id == post_id))
    return {"deleted": True, "id": post_id}
