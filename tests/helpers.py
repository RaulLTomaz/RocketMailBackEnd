from uuid import uuid4

from httpx import AsyncClient

from app.auth import gerar_token_teste


def email_unico(prefixo: str = "user") -> str:
    return f"{prefixo}_{uuid4().hex[:12]}@example.com"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def cria_usuario(
    client: AsyncClient,
    nome: str | None = None,
    email: str | None = None,
    senha: str = "senha123",
) -> dict:
    """Cria usuário via API; inclui `_senha` só para os testes reutilizarem no login."""
    payload = {
        "nome": nome or f"User {uuid4().hex[:6]}",
        "email": email or email_unico(),
        "senha": senha,
    }
    resp = await client.post("/usuario/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    data["_senha"] = senha
    return data


async def login(client: AsyncClient, email: str, senha: str) -> str:
    resp = await client.post(
        "/usuario/login",
        data={"username": email, "password": senha},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def cria_usuario_com_token(
    client: AsyncClient,
    nome: str | None = None,
    email: str | None = None,
    senha: str = "senha123",
) -> tuple[dict, str]:
    user = await cria_usuario(client, nome=nome, email=email, senha=senha)
    token = gerar_token_teste(user["id"])
    return user, token


async def cria_post(client: AsyncClient, token: str, conteudo: str):
    return await client.post(
        "/post/",
        json={"post": conteudo},
        headers=auth_header(token),
    )


async def seguir(client: AsyncClient, seguidor_token: str, seguido_id: int):
    return await client.post(
        "/seguir/",
        params={"seguido_id": seguido_id},
        headers=auth_header(seguidor_token),
    )


async def deixar_de_seguir(client: AsyncClient, seguidor_token: str, seguido_id: int):
    return await client.delete(
        "/seguir/",
        params={"seguido_id": seguido_id},
        headers=auth_header(seguidor_token),
    )
