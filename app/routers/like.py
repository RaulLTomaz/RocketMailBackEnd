from typing import Dict, List

from databases import Database
from fastapi import APIRouter, Depends, Query

from app.crud import like as like_crud
from app.crud.usuario import get_current_user
from app.database import get_database

router = APIRouter(prefix="/like", tags=["Like"])


@router.get(
    "/batch",
    summary="Resumo de likes em lote",
    description=(
        "Aceita o parâmetro repetido `post_ids` "
        "(ex.: `?post_ids=1&post_ids=2`). Declarado antes de `/{post_id}`."
    ),
)
async def get_like_summary_batch(
    post_ids: List[int] = Query(..., description="IDs de post (repetir o param)"),
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
) -> Dict[int, dict]:
    return await like_crud.batch_resumo_like(db, usuario_id, post_ids)


@router.post("/{post_id}")
async def like_post(
    post_id: int,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await like_crud.dar_like(db, usuario_id, post_id)


@router.delete("/{post_id}")
async def unlike_post(
    post_id: int,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await like_crud.remover_like(db, usuario_id, post_id)


@router.get("/{post_id}")
async def get_like_summary(
    post_id: int,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await like_crud.resumo_like(db, usuario_id, post_id)
