import logging
from collections import defaultdict

from databases import Database
from fastapi import HTTPException, status
from sqlalchemy import asc, func, select
from sqlalchemy.exc import IntegrityError

from app.crud.seguir import remover_todas_as_relacoes_do_usuario
from app.models.like import like
from app.models.post import post
from app.models.seguir import seguir
from app.models.usuario import usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.security import criar_token_acesso, gerar_hash_senha, verificar_senha

try:
    import asyncpg
except Exception:  # pragma: no cover
    asyncpg = None

logger = logging.getLogger("uvicorn.error")


def _is_unique_violation(exc: Exception) -> bool:
    """
    Detecta violação de UNIQUE mesmo quando `databases` encapsula o erro do asyncpg
    em outra exception (nem sempre chega como IntegrityError/UniqueViolation puro).
    """
    if isinstance(exc, IntegrityError):
        return True
    if asyncpg and isinstance(exc, getattr(asyncpg, "UniqueViolationError", tuple())):
        return True
    cause = getattr(exc, "__cause__", None) or getattr(exc, "orig", None)
    if cause is not None and cause is not exc:
        return _is_unique_violation(cause)
    return False


def _usuario_publico(row) -> dict:
    """Remove a senha e tolera rows antigas sem a coluna foto_url."""
    try:
        foto = row["foto_url"]
    except (KeyError, IndexError, TypeError):
        foto = None
    return {
        "id": row["id"],
        "nome": row["nome"],
        "email": row["email"],
        "foto_url": foto,
    }


async def criar_usuario(db: Database, usuario_data: UsuarioCreate) -> dict:
    """Cria usuário e devolve dados públicos (sem senha)."""
    nome = str(usuario_data.nome).strip()
    email = str(usuario_data.email).strip().lower()

    try:
        senha_hash = gerar_hash_senha(usuario_data.senha)
    except Exception:
        logger.exception("Falha ao hashear senha no cadastro")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível criar o usuário.",
        )

    # RETURNING evita um SELECT extra e a ambiguidade do PK retornado por execute().
    insert_stmt = (
        usuario.insert()
        .values(nome=nome, email=email, senha=senha_hash, foto_url=None)
        .returning(usuario.c.id, usuario.c.nome, usuario.c.email, usuario.c.foto_url)
    )

    try:
        row = await db.fetch_one(insert_stmt)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao criar usuário.",
            )
        return _usuario_publico(row)

    except HTTPException:
        raise

    except Exception as e:
        if _is_unique_violation(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="E-mail já cadastrado.",
            )
        logger.exception("Falha ao criar usuário")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível criar o usuário.",
        )


async def buscar_usuario_por_id(db: Database, usuario_id: int) -> dict | None:
    query = select(
        usuario.c.id,
        usuario.c.nome,
        usuario.c.email,
        usuario.c.foto_url,
    ).where(usuario.c.id == usuario_id)
    row = await db.fetch_one(query)
    return _usuario_publico(row) if row else None


async def deletar_usuario(db: Database, usuario_id: int):
    async with db.transaction():
        # Remoção explícita: FKs de post/seguir podem não ter ON DELETE CASCADE
        # em bancos criados antes das migrations atuais.
        sub_posts = select(post.c.id).where(post.c.usuario_id == usuario_id)
        await db.execute(like.delete().where(like.c.post_id.in_(sub_posts)))
        await db.execute(like.delete().where(like.c.usuario_id == usuario_id))

        await db.execute(post.delete().where(post.c.usuario_id == usuario_id))
        await remover_todas_as_relacoes_do_usuario(db, usuario_id)
        await db.execute(usuario.delete().where(usuario.c.id == usuario_id))

    return {"deleted": True, "usuario_id": usuario_id}


async def autenticar_usuario(db: Database, email: str, senha: str):
    email_norm = str(email).strip().lower()
    query = usuario.select().where(usuario.c.email == email_norm)
    user = await db.fetch_one(query)
    if not user or not verificar_senha(senha, user["senha"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    token = criar_token_acesso({"sub": str(user["id"])})
    return {"access_token": token, "token_type": "bearer"}


async def atualizar_usuario(db: Database, usuario_id: int, data: UsuarioUpdate) -> dict:
    valores = {}
    if data.nome is not None:
        valores["nome"] = str(data.nome).strip()
    if data.email is not None:
        valores["email"] = str(data.email).strip().lower()
    if data.senha is not None:
        valores["senha"] = gerar_hash_senha(data.senha)
    # model_fields_set distingue "omitido" de "enviado como null" (remover foto via PATCH).
    if "foto_url" in data.model_fields_set:
        valores["foto_url"] = str(data.foto_url) if data.foto_url is not None else None

    if valores:
        try:
            await db.execute(
                usuario.update().where(usuario.c.id == usuario_id).values(**valores)
            )
        except Exception as e:
            if _is_unique_violation(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="E-mail já cadastrado.",
                )
            logger.exception("Falha ao atualizar usuário %s", usuario_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Não foi possível atualizar o usuário.",
            )

    row = await buscar_usuario_por_id(db, usuario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return row


async def atualizar_foto_url(
    db: Database, usuario_id: int, foto_url: str | None
) -> dict:
    await db.execute(
        usuario.update().where(usuario.c.id == usuario_id).values(foto_url=foto_url)
    )
    row = await buscar_usuario_por_id(db, usuario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return row


async def stats_usuario(db: Database, usuario_id: int) -> dict:
    urow = await buscar_usuario_por_id(db, usuario_id)
    if not urow:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    posts_q = (
        select(func.count()).select_from(post).where(post.c.usuario_id == usuario_id)
    )
    seguidores_q = (
        select(func.count())
        .select_from(seguir)
        .where(seguir.c.seguido_id == usuario_id)
    )
    seguindo_q = (
        select(func.count())
        .select_from(seguir)
        .where(seguir.c.seguidor_id == usuario_id)
    )

    posts_count = await db.fetch_val(posts_q) or 0
    seguidores_count = await db.fetch_val(seguidores_q) or 0
    seguindo_count = await db.fetch_val(seguindo_q) or 0

    return {
        "usuario": urow,
        "stats": {
            "posts": int(posts_count),
            "seguidores": int(seguidores_count),
            "seguindo": int(seguindo_count),
        },
    }


def _escape_like(term: str) -> str:
    """Evita que % e _ digitados pelo usuário virem curingas do ILIKE."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def buscar_usuarios_com_posts(
    db: Database,
    q: str,
    limit: int = 20,
    posts_per_user: int = 5,
) -> list[dict]:
    """Busca por nome (ILIKE) e anexa os posts mais recentes de cada usuário encontrado."""
    from app.crud.post import get_posts_recentes_por_usuarios

    termo = (q or "").strip()
    if not termo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parâmetro q é obrigatório.",
        )

    pattern = f"%{_escape_like(termo)}%"
    query = (
        select(
            usuario.c.id,
            usuario.c.nome,
            usuario.c.email,
            usuario.c.foto_url,
        )
        .where(usuario.c.nome.ilike(pattern, escape="\\"))
        .order_by(asc(usuario.c.nome), asc(usuario.c.id))
        .limit(limit)
    )
    rows = await db.fetch_all(query)
    if not rows:
        return []

    user_ids = [row["id"] for row in rows]
    posts_by_user: dict[int, list] = defaultdict(list)
    if posts_per_user > 0:
        posts_by_user = await get_posts_recentes_por_usuarios(
            db, user_ids, per_user=posts_per_user
        )

    return [
        {
            "usuario": _usuario_publico(row),
            "posts": posts_by_user.get(row["id"], []),
        }
        for row in rows
    ]
