from app.models.usuario import usuario
from app.models.seguir import seguir
from app.models.post import post
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.crud.seguir import remover_todas_as_relacoes_do_usuario
from databases import Database
from fastapi import HTTPException, Depends, status
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, asc, desc, func
import os

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/usuario/login")


def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)


def gerar_hash_senha(senha):
    return pwd_context.hash(senha)


def criar_token_acesso(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Não autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id: int = int(payload.get("sub"))
        if usuario_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return usuario_id


async def criar_usuario(db: Database, usuario_data: UsuarioCreate):
    senha_hash = gerar_hash_senha(usuario_data.senha)
    query = usuario.insert().values(
        nome=usuario_data.nome,
        email=usuario_data.email,
        senha=senha_hash,
    )
    user_id = await db.execute(query)
    return {**usuario_data.model_dump(), "id": user_id}


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
    # Remove os posts primeiro
    await db.execute(post.delete().where(post.c.usuario_id == usuario_id))

    # Remove TODAS as relações de seguir desse usuário
    await remover_todas_as_relacoes_do_usuario(db, usuario_id)

    # Agora remove o usuário
    query = usuario.delete().where(usuario.c.id == usuario_id)
    await db.execute(query)

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
    return {"id": row["id"], "nome": row["nome"], "email": row["email"]}


# ---------- seguir / deixar de seguir ----------
async def seguir_usuario(
    db: Database, seguido_id: int, seguidor_id: int = Depends(get_current_user)
):
    query = seguir.insert().values(seguidor_id=seguidor_id, seguido_id=seguido_id)
    await db.execute(query)
    return {"seguidor_id": seguidor_id, "seguido_id": seguido_id}


async def listar_seguidos(
    db: Database, seguidor_id: int = Depends(get_current_user)
):
    query = usuario.select().where(
        usuario.c.id.in_(
            seguir.select()
            .with_only_columns(seguir.c.seguido_id)
            .where(seguir.c.seguidor_id == seguidor_id)
        )
    )
    return await db.fetch_all(query)


async def deixar_de_seguir(
    db: Database, seguido_id: int, seguidor_id: int = Depends(get_current_user)
):
    query = seguir.delete().where(
        (seguir.c.seguidor_id == seguidor_id) & (seguir.c.seguido_id == seguido_id)
    )
    await db.execute(query)
    return {"deleted": True, "seguidor_id": seguidor_id, "seguido_id": seguido_id}


# ---------- atualizar perfil (/me PATCH) ----------
async def atualizar_usuario(db: Database, usuario_id: int, data: UsuarioUpdate) -> dict:
    valores = {}
    if data.nome is not None:
        valores["nome"] = data.nome
    if data.email is not None:
        valores["email"] = data.email
    if data.senha is not None:
        valores["senha"] = gerar_hash_senha(data.senha)

    if valores:
        await db.execute(
            usuario.update().where(usuario.c.id == usuario_id).values(**valores)
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
        "usuario": {"id": urow["id"], "nome": urow["nome"], "email": urow["email"]},
        "stats": {
            "posts": int(posts_count),
            "seguidores": int(seguidores_count),
            "seguindo": int(seguindo_count),
        },
    }
