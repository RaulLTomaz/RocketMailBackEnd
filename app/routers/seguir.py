from fastapi import APIRouter, Depends
from app.database import get_database
from databases import Database
from app.crud import seguir as seguir_crud

router = APIRouter(prefix="/seguir", tags=["Seguir"])


@router.post("/")
async def seguir_usuario(seguidor_id: int, seguido_id: int, db: Database = Depends(get_database)):
    return await seguir_crud.seguir_usuario(db, seguidor_id, seguido_id)


@router.get("/seguidos/{seguidor_id}")
async def listar_seguidos(seguidor_id: int, db: Database = Depends(get_database)):
    return await seguir_crud.listar_seguidos(db, seguidor_id)


@router.delete("/")
async def deixar_de_seguir(seguidor_id: int, seguido_id: int, db: Database = Depends(get_database)):
    return await seguir_crud.deixar_de_seguir(db, seguidor_id, seguido_id)
