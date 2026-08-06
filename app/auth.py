"""
Helpers JWT usados apenas nos testes.

A autenticação da API está em `app.security`.
"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.security import ALGORITHM, SECRET_KEY


def gerar_token_teste(usuario_id: int, minutos: int = 60) -> str:
    """Token compatível com get_current_user (mesmo SECRET_KEY do ambiente)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutos)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
