from databases import Database
from fastapi import APIRouter, Depends, Query

from app.crud import seguir as seguir_crud
from app.crud.usuario import get_current_user
from app.database import get_database
from app.schemas.usuario import UsuarioOut

router = APIRouter(prefix="/seguir", tags=["Seguir"])


@router.get("/seguidos", response_model=list[UsuarioOut])
async def listar_seguidos(
    db: Database = Depends(get_database),
    seguidor_id: int = Depends(get_current_user),
):
    return await seguir_crud.listar_seguidos(db, seguidor_id)


@router.post("/")
async def seguir_usuario(
    seguido_id: int = Query(..., description="ID do usuário a seguir"),
    db: Database = Depends(get_database),
    seguidor_id: int = Depends(get_current_user),
):
    """Segue um usuário. O seguidor é sempre o autenticado (JWT)."""
    return await seguir_crud.seguir_usuario(db, seguidor_id, seguido_id)


@router.delete("/")
async def deixar_de_seguir(
    seguido_id: int = Query(..., description="ID do usuário a deixar de seguir"),
    db: Database = Depends(get_database),
    seguidor_id: int = Depends(get_current_user),
):
    """Deixa de seguir. O seguidor é sempre o autenticado (JWT)."""
    return await seguir_crud.deixar_de_seguir(db, seguidor_id, seguido_id)
