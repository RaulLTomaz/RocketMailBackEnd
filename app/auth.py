import os
from datetime import datetime, timedelta, timezone
from jose import jwt

ALGORITHM = os.getenv("ALGORITHM", "HS256")

def gerar_token_teste(usuario_id: int, minutos: int = 60) -> str:
    secret = os.getenv("SECRET_KEY", "segredo_teste")
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(usuario_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutos)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)
