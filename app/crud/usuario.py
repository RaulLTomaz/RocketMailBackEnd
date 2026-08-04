from datetime import datetime, timedelta, timezone
from app.models.usuario import usuario
from app.models.seguir import seguir
from app.models.post import post
from app.models.like import like
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.crud.seguir import remover_todas_as_relacoes_do_usuario
from app.database import get_database
from databases import Database
from fastapi import HTTPException, Depends, status
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, asc, desc, func
from sqlalchemy.exc import IntegrityError
import os

try:
    import asyncpg  # driver comum no Render para Postgres
except Exception:  # pragma: no cover
    asyncpg = None

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/usuario/login")


def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)


def gerar_hash_senha(senha):
    return pwd_context.hash(senha)


def criar_token_acesso(data: dict):
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        }
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Database = Depends(get_database),
) -> int:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Não autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        usuario_id = int(sub)
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    row = await db.fetch_one(usuario.select().where(usuario.c.id == usuario_id))
    if not row:
        raise credentials_exception
    return usuario_id


def _is_unique_violation(exc: Exception) -> bool:
    if isinstance(exc, IntegrityError):
        return True
    if asyncpg and isinstance(exc, getattr(asyncpg, "UniqueViolationError", tuple())):
        return True
    # databases/asyncpg às vezes encapsula a causa
    cause = getattr(exc, "__cause__", None) or getattr(exc, "orig", None)
    if cause is not None and cause is not exc:
        return _is_unique_violation(cause)
    return False


# ---------- criação de usuário ----------
async def criar_usuario(db: Database, usuario_data: UsuarioCreate) -> dict:
    """
    Cria usuário com senha hasheada.
    Retorna apenas {id, nome, email}.
    Lança HTTPException 409 para e-mail duplicado e 400 para falhas genéricas.
    """
    import logging

    logger = logging.getLogger("uvicorn.error")
    nome = str(usuario_data.nome).strip()
    email = str(usuario_data.email).strip().lower()

    try:
        senha_hash = gerar_hash_senha(usuario_data.senha)
    except Exception as e:
        logger.exception("Falha ao hashear senha no cadastro")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível criar o usuário (hash): {type(e).__name__}",
        )

    insert_stmt = (
        usuario.insert()
        .values(nome=nome, email=email, senha=senha_hash, foto_url=None)
        .returning(usuario.c.id, usuario.c.nome, usuario.c.email, usuario.c.foto_url)
    )

    try:
        row = await db.fetch_one(insert_stmt)
        if not row:
            raise HTTPException(
                status_code=500,
                detail="Falha ao ler usuário recém-criado.",
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
        logger.exception("Falha ao criar usuário: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível criar o usuário ({type(e).__name__}: {e})",
        )


# ---------- listagem com ordenação ----------
async def listar_usuarios(db: Database, limit: int = 50, offset: int = 0, sort: str = "nome"):
    """
    Lista usuários com paginação.
    sort:
        - "nome" (default)  => nome asc
        - "-nome"           => nome desc
        - "id"              => id asc
        - "-id"             => id desc
    """
    if sort == "-nome":
        order_col = desc(usuario.c.nome)
    elif sort == "id":
        order_col = asc(usuario.c.id)
    elif sort == "-id":
        order_col = desc(usuario.c.id)
    else:
        order_col = asc(usuario.c.nome)

    query = (
        select(usuario)
        .order_by(order_col)
        .limit(limit)
        .offset(offset)
    )
    return await db.fetch_all(query)


async def buscar_usuario_por_id(db: Database, usuario_id: int):
    query = usuario.select().where(usuario.c.id == usuario_id)
    return await db.fetch_one(query)


async def deletar_usuario(db: Database, usuario_id: int):
    async with db.transaction():
        # Likes do usuário e likes em posts dele (CASCADE pode já cobrir, mas fica explícito)
        sub_posts = select(post.c.id).where(post.c.usuario_id == usuario_id)
        await db.execute(like.delete().where(like.c.post_id.in_(sub_posts)))
        await db.execute(like.delete().where(like.c.usuario_id == usuario_id))

        await db.execute(post.delete().where(post.c.usuario_id == usuario_id))
        await remover_todas_as_relacoes_do_usuario(db, usuario_id)
        await db.execute(usuario.delete().where(usuario.c.id == usuario_id))

    return {"deleted": True, "usuario_id": usuario_id}


async def autenticar_usuario(db: Database, email: str, senha: str):
    query = usuario.select().where(usuario.c.email == email)
    user = await db.fetch_one(query)
    if not user or not verificar_senha(senha, user["senha"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    token = criar_token_acesso({"sub": str(user["id"]), "email": user["email"]})
    return {"access_token": token, "token_type": "bearer"}


# ---------- helpers de saída ----------
def _usuario_publico(row) -> dict:
    """Normaliza saída do usuário (sem senha)."""
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


# ---------- atualizar perfil (/me PATCH) ----------
async def atualizar_usuario(db: Database, usuario_id: int, data: UsuarioUpdate) -> dict:
    valores = {}
    if data.nome is not None:
        valores["nome"] = str(data.nome).strip()
    if data.email is not None:
        valores["email"] = str(data.email).strip().lower()
    if data.senha is not None:
        valores["senha"] = gerar_hash_senha(data.senha)
    if "foto_url" in data.model_fields_set:
        # permite null explícito ou URL externa
        valores["foto_url"] = data.foto_url

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
            raise

    row = await buscar_usuario_por_id(db, usuario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return _usuario_publico(row)


async def atualizar_foto_url(db: Database, usuario_id: int, foto_url: str | None) -> dict:
    await db.execute(
        usuario.update().where(usuario.c.id == usuario_id).values(foto_url=foto_url)
    )
    row = await buscar_usuario_por_id(db, usuario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return _usuario_publico(row)


# ---------- estatísticas do perfil ----------
async def stats_usuario(db: Database, usuario_id: int) -> dict:
    # Verifica existência do usuário
    urow = await db.fetch_one(select(usuario).where(usuario.c.id == usuario_id))
    if not urow:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Contadores agregados
    posts_q = select(func.count()).select_from(post).where(post.c.usuario_id == usuario_id)
    seguidores_q = select(func.count()).select_from(seguir).where(seguir.c.seguido_id == usuario_id)
    seguindo_q = select(func.count()).select_from(seguir).where(seguir.c.seguidor_id == usuario_id)

    posts_count = await db.fetch_val(posts_q) or 0
    seguidores_count = await db.fetch_val(seguidores_q) or 0
    seguindo_count = await db.fetch_val(seguindo_q) or 0

    return {
        "usuario": _usuario_publico(urow),
        "stats": {
            "posts": int(posts_count),
            "seguidores": int(seguidores_count),
            "seguindo": int(seguindo_count),
        },
    }
