from databases import Database
from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert

from app.models.seguir import seguir
from app.models.usuario import usuario


async def seguir_usuario(db: Database, seguidor_id: int, seguido_id: int):
    if seguidor_id == seguido_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível seguir a si mesmo.",
        )

    seguido = await db.fetch_one(usuario.select().where(usuario.c.id == seguido_id))
    if not seguido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário a seguir não encontrado.",
        )

    # Idempotente: duplicata não gera 500
    stmt = insert(seguir).values(seguidor_id=seguidor_id, seguido_id=seguido_id)
    stmt = stmt.on_conflict_do_nothing()
    await db.execute(stmt)
    return {"seguidor_id": seguidor_id, "seguido_id": seguido_id}


async def listar_seguidos(db: Database, seguidor_id: int):
    query = usuario.select().where(
        usuario.c.id.in_(
            seguir.select().with_only_columns(seguir.c.seguido_id).where(
                seguir.c.seguidor_id == seguidor_id
            )
        )
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
