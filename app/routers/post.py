from fastapi import APIRouter, Depends, Query
from databases import Database
from app.database import get_database
from app.crud import post as post_crud
from app.crud.usuario import get_current_user
from app.schemas.post import PostCreate

router = APIRouter(prefix="/post", tags=["Post"])

@router.post(
    "/",
    summary="Criar post",
    description="Cria um post para o usuário autenticado.",
)
async def create_post(
    post_in: PostCreate,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await post_crud.create_post(db, post_in, usuario_id)

@router.get(
    "/",
    summary="Listar posts",
    description="Lista posts com paginação e ordenação por data (`-data` para decrescente, `data` para crescente).",
)
async def read_posts(
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("-data", pattern="^-?data$"),
):
    return await post_crud.get_posts(db, limit=limit, offset=offset, sort=sort)

@router.get(
    "/feed",
    summary="Feed priorizado",
    description="Retorna o feed priorizando posts de quem o usuário autenticado segue; depois os demais, ambos por ordem decrescente de data.",
)
async def read_feed(
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await post_crud.get_feed(db, viewer_id=usuario_id, limit=limit, offset=offset)

@router.delete(
    "/{post_id}",
    summary="Excluir post",
    description="Exclui um post se, e somente se, o usuário autenticado for o dono do post.",
)
async def delete_post(
    post_id: int,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await post_crud.delete_post(db, post_id, usuario_id)
