import os
import jwt

def gerar_token_teste(usuario_id: int):
    """
    Gera um token JWT para testes.
    """
    SECRET_KEY = os.getenv("SECRET_KEY", "segredo_teste")
    return jwt.encode({"sub": str(usuario_id)}, SECRET_KEY, algorithm="HS256")
