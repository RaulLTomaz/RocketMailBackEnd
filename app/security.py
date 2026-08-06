"""
Autenticação JWT e hashing de senhas.

Mantido separado do CRUD para não misturar regras de negócio com infra de auth.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from databases import Database
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_database
from app.models.usuario import usuario

logger = logging.getLogger("uvicorn.error")

_ENV = os.getenv("PYTHON_ENV", "dev").lower()
_DEFAULT_SECRET = "super-secret"
_SECRET_FROM_ENV = os.getenv("SECRET_KEY")

if _ENV in ("production", "prod"):
    if not _SECRET_FROM_ENV or _SECRET_FROM_ENV == _DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY deve ser definida com um valor forte em produção."
        )
    SECRET_KEY = _SECRET_FROM_ENV
else:
    SECRET_KEY = _SECRET_FROM_ENV or _DEFAULT_SECRET
    if not _SECRET_FROM_ENV:
        logger.warning(
            "SECRET_KEY ausente — usando valor padrão inseguro (apenas dev/test)."
        )

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/usuario/login")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_plana, senha_hash)


def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def criar_token_acesso(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
            ),
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

    # Token válido só conta se a conta ainda existir (logout implícito ao excluir).
    row = await db.fetch_one(usuario.select().where(usuario.c.id == usuario_id))
    if not row:
        raise credentials_exception
    return usuario_id
