"""Upload / remoção de foto de perfil."""

from io import BytesIO

from httpx import AsyncClient

from tests.helpers import auth_header, cria_post, cria_usuario, cria_usuario_com_token

# PNG 1x1 válido
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


async def test_criar_usuario_foto_url_null(client: AsyncClient):
    user = await cria_usuario(client)
    assert user.get("foto_url") is None

    resp = await client.get(f"/usuario/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["foto_url"] is None


async def test_upload_foto_e_aparece_em_me_e_posts(client: AsyncClient):
    user, token = await cria_usuario_com_token(client)

    resp = await client.post(
        "/usuario/me/foto",
        headers=auth_header(token),
        files={"file": ("avatar.png", BytesIO(PNG_1X1), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == user["id"]
    assert body["foto_url"]
    assert "/media/avatars/" in body["foto_url"] or body["foto_url"].startswith("http")

    me = await client.get("/usuario/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["foto_url"] == body["foto_url"]

    post_resp = await cria_post(client, token, "post com avatar")
    assert post_resp.status_code == 200
    assert post_resp.json()["usuario"]["foto_url"] == body["foto_url"]

    feed = await client.get("/post/feed", headers=auth_header(token))
    assert feed.status_code == 200
    meu = next(p for p in feed.json() if p["usuario"]["id"] == user["id"])
    assert meu["usuario"]["foto_url"] == body["foto_url"]


async def test_upload_arquivo_invalido(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    resp = await client.post(
        "/usuario/me/foto",
        headers=auth_header(token),
        files={"file": ("nota.txt", BytesIO(b"nao sou imagem"), "text/plain")},
    )
    assert resp.status_code == 400


async def test_delete_foto(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    up = await client.post(
        "/usuario/me/foto",
        headers=auth_header(token),
        files={"file": ("avatar.png", BytesIO(PNG_1X1), "image/png")},
    )
    assert up.status_code == 200
    assert up.json()["foto_url"]

    deleted = await client.delete("/usuario/me/foto", headers=auth_header(token))
    assert deleted.status_code == 200
    assert deleted.json()["foto_url"] is None


async def test_patch_foto_url_externa(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    url = "https://example.com/avatar.jpg"
    resp = await client.patch(
        "/usuario/me",
        headers=auth_header(token),
        json={"foto_url": url},
    )
    assert resp.status_code == 200
    assert resp.json()["foto_url"] == url


async def test_producao_sem_cloudinary_retorna_503(client: AsyncClient, monkeypatch):
    import app.storage as storage

    monkeypatch.setenv("PYTHON_ENV", "production")
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
    monkeypatch.delenv("CLOUDINARY_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDINARY_API_SECRET", raising=False)

    _, token = await cria_usuario_com_token(client)
    resp = await client.post(
        "/usuario/me/foto",
        headers=auth_header(token),
        files={"file": ("avatar.png", BytesIO(PNG_1X1), "image/png")},
    )
    assert resp.status_code == 503
    assert "CLOUDINARY" in resp.json()["detail"].upper()
    assert storage.cloudinary_enabled() is False


async def test_cloudinary_erro_vira_502_nao_crash(client: AsyncClient, monkeypatch):
    """Falha do SDK deve virar HTTP 502/503 (com CORS), não derrubar a request."""
    import app.storage as storage

    monkeypatch.setenv("CLOUDINARY_URL", "cloudinary://key:secret@demo")

    def boom(*_a, **_k):
        raise RuntimeError("Invalid API Key")

    monkeypatch.setattr(storage, "_upload_cloudinary_sync", boom)

    _, token = await cria_usuario_com_token(client)
    resp = await client.post(
        "/usuario/me/foto",
        headers={**auth_header(token), "Origin": "http://localhost:8081"},
        files={"file": ("avatar.png", BytesIO(PNG_1X1), "image/png")},
    )
    assert resp.status_code in (502, 503)
    detail = resp.json()["detail"]
    assert "Invalid" in detail or "Cloudinary" in detail or "RuntimeError" in detail
    # Sem Origin o ASGI test não recebe ACAO; com Origin o middleware anexa o header.
    assert resp.headers.get("access-control-allow-origin") in (
        "*",
        "http://localhost:8081",
    )
