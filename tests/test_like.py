import pytest
from httpx import AsyncClient
from app.auth import gerar_token_teste

async def _cria_usuario_api(client: AsyncClient, nome: str, email: str, senha: str = "senha_hashed") -> int:
    resp = await client.post(
        "/usuario/",
        json={"nome": nome, "email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]

async def _cria_post_api(client: AsyncClient, token: str, texto: str):
    return await client.post(
        "/post/",
        headers={"Authorization": f"Bearer {token}"},
        json={"post": texto},
    )

@pytest.mark.asyncio
async def test_like_flows(client: AsyncClient):
    # --- Arrange: cria dois usuários e um post do usuário A ---
    a_id = await _cria_usuario_api(client, "AliceLike", "alice.like@example.com")
    b_id = await _cria_usuario_api(client, "BobLike", "bob.like@example.com")

    token_a = gerar_token_teste(a_id)
    token_b = gerar_token_teste(b_id)

    resp_post = await _cria_post_api(client, token_a, "post curtível")
    assert resp_post.status_code == 200, resp_post.text
    post_id = resp_post.json()["id"]

    # --- Antes de qualquer like: count=0, liked_by_me=False (para A) ---
    r = await client.get(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["post_id"] == post_id
    assert body["count"] == 0
    assert body["liked_by_me"] is False

    # --- A dá like ---
    r = await client.post(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200, r.text
    assert r.json()["liked"] is True

    # --- Resumo para A: count=1, liked_by_me=True ---
    r = await client.get(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["liked_by_me"] is True

    # --- Idempotência: A dá like de novo, continua count=1 ---
    r = await client.post(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    r = await client.get(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.json()["count"] == 1

    # --- Para B: count=1, liked_by_me=False ---
    r = await client.get(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["liked_by_me"] is False

    # --- B tenta remover like (não deu like antes) -> idempotente ---
    r = await client.delete(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    assert r.json()["liked"] is False
    # count continua 1
    r = await client.get(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.json()["count"] == 1

    # --- A faz unlike -> count volta a 0 ---
    r = await client.delete(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    assert r.json()["liked"] is False
    r = await client.get(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    body = r.json()
    assert body["count"] == 0
    assert body["liked_by_me"] is False

    # --- Batch: cria outro post e dá like em ambos para testar /like/batch ---
    resp_post2 = await _cria_post_api(client, token_a, "outro post curtível")
    assert resp_post2.status_code == 200
    post2_id = resp_post2.json()["id"]

    # A curte os dois
    await client.post(f"/like/{post_id}", headers={"Authorization": f"Bearer {token_a}"})
    await client.post(f"/like/{post2_id}", headers={"Authorization": f"Bearer {token_a}"})

    r = await client.get(
        "/like/batch",
        headers={"Authorization": f"Bearer {token_a}"},
        params=[("post_ids", str(post_id)), ("post_ids", str(post2_id))],
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert batch[str(post_id)]["count"] == 1
    assert batch[str(post_id)]["liked_by_me"] is True
    assert batch[str(post2_id)]["count"] == 1
    assert batch[str(post2_id)]["liked_by_me"] is True
