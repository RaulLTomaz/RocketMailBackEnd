"""Usuário: criar, login, buscar, /me, validações e erros."""
from httpx import AsyncClient

from tests.helpers import (
    auth_header,
    cria_usuario,
    cria_usuario_com_token,
    email_unico,
    login,
)


async def test_criar_usuario_sucesso(client: AsyncClient):
    email = email_unico("criar")
    resp = await client.post(
        "/usuario/",
        json={"nome": "Novo User", "email": email, "senha": "senha123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["nome"] == "Novo User"
    assert body["email"] == email
    assert "id" in body
    assert "senha" not in body
    assert body.get("foto_url") is None


async def test_criar_usuario_email_duplicado(client: AsyncClient):
    email = email_unico("dup")
    await cria_usuario(client, email=email)
    resp = await client.post(
        "/usuario/",
        json={"nome": "Outro", "email": email, "senha": "senha123"},
    )
    assert resp.status_code == 409
    assert "e-mail" in resp.json()["detail"].lower() or "email" in resp.json()["detail"].lower()


async def test_criar_usuario_senha_curta(client: AsyncClient):
    resp = await client.post(
        "/usuario/",
        json={"nome": "Curto", "email": email_unico("curto"), "senha": "123"},
    )
    assert resp.status_code == 422


async def test_criar_usuario_nome_vazio(client: AsyncClient):
    resp = await client.post(
        "/usuario/",
        json={"nome": "", "email": email_unico("vazio"), "senha": "senha123"},
    )
    assert resp.status_code == 422


async def test_login_sucesso(client: AsyncClient):
    user = await cria_usuario(client, email=email_unico("login"), senha="minhasenha")
    token = await login(client, user["email"], "minhasenha")
    assert isinstance(token, str) and len(token) > 10

    resp = await client.get("/usuario/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == user["id"]


async def test_login_credenciais_invalidas(client: AsyncClient):
    user = await cria_usuario(client, email=email_unico("badlogin"))
    resp = await client.post(
        "/usuario/login",
        data={"username": user["email"], "password": "errada"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


async def test_buscar_usuario_por_id(client: AsyncClient):
    user = await cria_usuario(client)
    resp = await client.get(f"/usuario/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["email"] == user["email"]


async def test_buscar_usuario_inexistente(client: AsyncClient):
    resp = await client.get("/usuario/99999999")
    assert resp.status_code == 404


async def test_me_sem_token(client: AsyncClient):
    resp = await client.get("/usuario/me")
    assert resp.status_code == 401


async def test_me_token_invalido(client: AsyncClient):
    resp = await client.get("/usuario/me", headers=auth_header("token.invalido.aqui"))
    assert resp.status_code == 401


async def test_me_fluxo_completo(client: AsyncClient):
    email = email_unico("me")
    user = await cria_usuario(client, nome="Usuario Me", email=email, senha="senha123")
    token = await login(client, email, "senha123")
    headers = auth_header(token)

    resp_me = await client.get("/usuario/me", headers=headers)
    assert resp_me.status_code == 200
    assert resp_me.json()["id"] == user["id"]

    resp_patch = await client.patch(
        "/usuario/me",
        json={"nome": "Nome Novo", "email": email_unico("me_novo")},
        headers=headers,
    )
    assert resp_patch.status_code == 200
    assert resp_patch.json()["nome"] == "Nome Novo"

    resp_delete = await client.delete("/usuario/me", headers=headers)
    assert resp_delete.status_code == 200
    assert resp_delete.json()["deleted"] is True

    assert (await client.get(f"/usuario/{user['id']}")).status_code == 404
    # token de usuário deletado não autentica mais
    assert (await client.get("/usuario/me", headers=headers)).status_code == 401


async def test_patch_me_email_duplicado(client: AsyncClient):
    a = await cria_usuario(client, email=email_unico("a"))
    b, token_b = await cria_usuario_com_token(client, email=email_unico("b"))

    resp = await client.patch(
        "/usuario/me",
        json={"email": a["email"]},
        headers=auth_header(token_b),
    )
    assert resp.status_code == 409
