from databases import Database
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models.seguir import seguir
from app.models.usuario import usuario

_USUARIO_PUBLICO_COLS = (
    usuario.c.id,
    usuario.c.nome,
    usuario.c.email,
    usuario.c.foto_url,
)


async def seguir_usuario(db: Database, seguidor_id: int, seguido_id: int):
    if seguidor_id == seguido_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível seguir a si mesmo.",
        )

    seguido = await db.fetch_one(
        select(usuario.c.id).where(usuario.c.id == seguido_id)
    )
    if not seguido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário a seguir não encontrado.",
        )

    # Idempotente: seguir de novo o mesmo usuário não deve estourar 500 por PK.
    stmt = insert(seguir).values(seguidor_id=seguidor_id, seguido_id=seguido_id)
    stmt = stmt.on_conflict_do_nothing()
    await db.execute(stmt)
    return {"seguidor_id": seguidor_id, "seguido_id": seguido_id}


async def listar_seguidos(db: Database, seguidor_id: int):
    query = (
        select(*_USUARIO_PUBLICO_COLS)
        .where(
            usuario.c.id.in_(
                select(seguir.c.seguido_id).where(seguir.c.seguidor_id == seguidor_id)
            )
        )
        .order_by(usuario.c.nome, usuario.c.id)
    )
    return await db.fetch_all(query)


async def deixar_de_seguir(db: Database, seguidor_id: int, seguido_id: int):
    query = seguir.delete().where(
        (seguir.c.seguidor_id == seguidor_id) & (seguir.c.seguido_id == seguido_id)
    )
    await db.execute(query)
    return {"deleted": True, "seguidor_id": seguidor_id, "seguido_id": seguido_id}


async def remover_todas_as_relacoes_do_usuario(db: Database, usuario_id: int):
    query = seguir.delete().where(
        (seguir.c.seguidor_id == usuario_id) | (seguir.c.seguido_id == usuario_id)
    )
    await db.execute(query)
    return {"removed": True, "usuario_id": usuario_id}
