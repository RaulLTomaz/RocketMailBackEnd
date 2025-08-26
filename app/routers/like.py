# app/routers/like.py
from fastapi import APIRouter, Depends, Query
from typing import List, Dict
from databases import Database

from app.database import get_database
from app.crud.usuario import get_current_user
from app.crud import like as like_crud

router = APIRouter(prefix="/like", tags=["Like"])

# --- Coloque o batch ANTES das rotas dinâmicas ---
@router.get("/batch")
async def get_like_summary_batch(
    post_ids: List[int] = Query(..., description="IDs de post separados por vírgula"),
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
) -> Dict[int, dict]:
    """
    Ex.: /like/batch?post_ids=1&post_ids=2&post_ids=3
    Retorna { 1: {...}, 2: {...} }
    """
    return await like_crud.batch_resumo_like(db, usuario_id, post_ids)

# --- Rotas por post_id (dinâmicas) ---
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
