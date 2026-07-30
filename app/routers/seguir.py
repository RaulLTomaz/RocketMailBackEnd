from fastapi import APIRouter, Depends, Query
from databases import Database

from app.database import get_database
from app.crud import seguir as seguir_crud
from app.crud.usuario import get_current_user

router = APIRouter(prefix="/seguir", tags=["Seguir"])


@router.post("/")
async def seguir_usuario(
    seguido_id: int = Query(..., description="ID do usuário a seguir"),
    db: Database = Depends(get_database),
    seguidor_id: int = Depends(get_current_user),
):
    """Segue um usuário. O seguidor é sempre o usuário autenticado."""
    return await seguir_crud.seguir_usuario(db, seguidor_id, seguido_id)


@router.delete("/")
async def deixar_de_seguir(
    seguido_id: int = Query(..., description="ID do usuário a deixar de seguir"),
    db: Database = Depends(get_database),
    seguidor_id: int = Depends(get_current_user),
):
    """Deixa de seguir um usuário. O seguidor é sempre o usuário autenticado."""
    return await seguir_crud.deixar_de_seguir(db, seguidor_id, seguido_id)
