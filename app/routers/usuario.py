from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from databases import Database
from starlette import status

from app.database import get_database
from app.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate, UsuarioSearchHit
from app.crud import usuario as crud_usuario
from app.crud import post as post_crud
from app.crud.usuario import autenticar_usuario, get_current_user
from app.storage import (
    salvar_foto_perfil,
    remover_arquivo_local_se_houver,
    remover_foto_cloudinary_se_houver,
)

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
    # Erros (409 e-mail duplicado, 400 genérico) já são tratados no CRUD via HTTPException
    return await crud_usuario.criar_usuario(db, usuario)


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
    description="Atualiza `nome`, `email`, `senha` e/ou `foto_url` do usuário autenticado.",
)
async def patch_me(
    payload: UsuarioUpdate,
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    return await crud_usuario.atualizar_usuario(db, usuario_id, payload)


@router.post(
    "/me/foto",
    response_model=UsuarioOut,
    summary="Upload da foto de perfil",
    description="Envia imagem (JPEG/PNG/WebP, até 5 MB) no campo multipart `file`.",
)
async def upload_foto_me(
    file: UploadFile = File(...),
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    atual = await crud_usuario.buscar_usuario_por_id(db, usuario_id)
    if not atual:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    try:
        foto_url = await salvar_foto_perfil(file, usuario_id)
    except HTTPException:
        raise
    except Exception as e:
        # Garante resposta FastAPI (com CORS) em vez de derrubar o worker
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao processar upload: {type(e).__name__}: {e}",
        ) from e

    try:
        antiga = atual["foto_url"]
    except (KeyError, IndexError, TypeError):
        antiga = None
    if antiga and antiga != foto_url:
        remover_arquivo_local_se_houver(antiga)

    return await crud_usuario.atualizar_foto_url(db, usuario_id, foto_url)


@router.delete(
    "/me/foto",
    response_model=UsuarioOut,
    summary="Remover foto de perfil",
)
async def delete_foto_me(
    db: Database = Depends(get_database),
    usuario_id: int = Depends(get_current_user),
):
    atual = await crud_usuario.buscar_usuario_por_id(db, usuario_id)
    if not atual:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    try:
        antiga = atual["foto_url"]
    except (KeyError, IndexError, TypeError):
        antiga = None
    remover_arquivo_local_se_houver(antiga)
    remover_foto_cloudinary_se_houver(usuario_id)
    return await crud_usuario.atualizar_foto_url(db, usuario_id, None)


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
    "/search",
    response_model=list[UsuarioSearchHit],
    summary="Buscar usuários",
    description=(
        "Busca usuários pelo nome (case-insensitive) e retorna os posts mais recentes "
        "de cada um. Requer autenticação (mesmo padrão do feed)."
    ),
)
async def search_usuarios(
    q: str = Query(..., min_length=1, description="Texto de busca (nome)"),
    limit: int = Query(20, ge=1, le=50, description="Máximo de usuários"),
    posts_per_user: int = Query(
        5, ge=0, le=20, description="Posts mais recentes por usuário"
    ),
    db: Database = Depends(get_database),
    _usuario_id: int = Depends(get_current_user),
):
    termo = q.strip()
    if not termo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parâmetro q é obrigatório.",
        )
    return await crud_usuario.buscar_usuarios_com_posts(
        db, q=termo, limit=limit, posts_per_user=posts_per_user
    )


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
