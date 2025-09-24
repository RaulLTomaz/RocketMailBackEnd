from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from databases import Database
from starlette import status
from sqlalchemy.exc import IntegrityError

from app.database import get_database
from app.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.crud import usuario as crud_usuario
from app.crud import post as post_crud
from app.crud.usuario import autenticar_usuario, get_current_user

try:
    import asyncpg  # driver comum no Render para Postgres
except Exception:  # pragma: no cover
    asyncpg = None

router = APIRouter(prefix="/usuario", tags=["Usuário"])


@router.post(
    "/login",
    summary="Login",
    description="Autentica com email e senha (OAuth2 password) e retorna `access_token`.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Database = Depends(get_database),
):
    return await autenticar_usuario(db, form_data.username, form_data.password)


@router.post(
    "/",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    description="Cria um usuário com `nome`, `email` e `senha`.",
)
async def criar(usuario: UsuarioCreate, db: Database = Depends(get_database)):
    """
    Cria usuário e trata erros comuns para não retornar 500.
    """
    try:
        return await crud_usuario.criar_usuario(db, usuario)

    except IntegrityError:
        # chave única do email violada
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")

    except Exception as e:
        # alguns drivers expõem UniqueViolation específica
        if asyncpg and isinstance(e, getattr(asyncpg, "UniqueViolationError", tuple())):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")
        # erro genérico (ex.: validação/banco)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi possível criar o usuário.")


@router.get(
    "/me",
    response_model=UsuarioOut,
    summary="Meu perfil",
    description="Retorna informações do usuário autenticado.",
)
async def get_me(
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    row = await crud_usuario.buscar_usuario_por_id(db, usuario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return row


@router.patch(
    "/me",
    response_model=UsuarioOut,
    summary="Atualizar meu perfil",
    description="Atualiza `nome`, `email` e/ou `senha` do usuário autenticado.",
)
async def patch_me(
    payload: UsuarioUpdate,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await crud_usuario.atualizar_usuario(db, usuario_id, payload)


@router.delete(
    "/me",
    summary="Excluir minha conta",
    description="Remove a conta, seus posts e relações de seguir do usuário autenticado.",
)
async def delete_me(
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    await crud_usuario.deletar_usuario(db, usuario_id)
    return {"deleted": True}


@router.get(
    "/{usuario_id}",
    response_model=UsuarioOut,
    summary="Buscar usuário por ID",
    description="Retorna um usuário específico.",
)
async def buscar(usuario_id: int, db: Database = Depends(get_database)):
    usuario_row = await crud_usuario.buscar_usuario_por_id(db, usuario_id)
    if usuario_row is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario_row


@router.get(
    "/{usuario_id}/stats",
    summary="Estatísticas do perfil",
    description="Retorna contadores agregados: posts, seguidores e seguindo.",
)
async def stats(usuario_id: int, db: Database = Depends(get_database)):
    return await crud_usuario.stats_usuario(db, usuario_id)


@router.get(
    "/{usuario_id}/posts",
    summary="Posts do usuário (timeline pública)",
    description="Lista os posts de um usuário específico, com paginação.",
)
async def posts_do_usuario(
    usuario_id: int,
    db: Database = Depends(get_database),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await post_crud.get_posts_por_usuario(db, usuario_id, limit=limit, offset=offset)
