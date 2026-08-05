"""Likes: like, unlike, resumo, batch e erros."""

from httpx import AsyncClient

from tests.helpers import auth_header, cria_post, cria_usuario_com_token


async def test_like_flows(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client, nome="AliceLike")
    _, token_b = await cria_usuario_com_token(client, nome="BobLike")

    resp_post = await cria_post(client, token_a, "post curtível")
    assert resp_post.status_code == 200
    post_id = resp_post.json()["id"]

    r = await client.get(f"/like/{post_id}", headers=auth_header(token_a))
    assert r.status_code == 200
    assert r.json() == {"post_id": post_id, "count": 0, "liked_by_me": False}

    r = await client.post(f"/like/{post_id}", headers=auth_header(token_a))
    assert r.status_code == 200
    assert r.json()["liked"] is True

    r = await client.get(f"/like/{post_id}", headers=auth_header(token_a))
    assert r.json()["count"] == 1
    assert r.json()["liked_by_me"] is True

    await client.post(f"/like/{post_id}", headers=auth_header(token_a))
    r = await client.get(f"/like/{post_id}", headers=auth_header(token_a))
    assert r.json()["count"] == 1

    r = await client.get(f"/like/{post_id}", headers=auth_header(token_b))
    assert r.json()["count"] == 1
    assert r.json()["liked_by_me"] is False

    r = await client.delete(f"/like/{post_id}", headers=auth_header(token_b))
    assert r.status_code == 200
    assert r.json()["liked"] is False
    assert (await client.get(f"/like/{post_id}", headers=auth_header(token_a))).json()[
        "count"
    ] == 1

    r = await client.delete(f"/like/{post_id}", headers=auth_header(token_a))
    assert r.status_code == 200
    body = (await client.get(f"/like/{post_id}", headers=auth_header(token_a))).json()
    assert body["count"] == 0
    assert body["liked_by_me"] is False


async def test_like_batch(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client)
    p1 = (await cria_post(client, token_a, "post 1")).json()["id"]
    p2 = (await cria_post(client, token_a, "post 2")).json()["id"]

    await client.post(f"/like/{p1}", headers=auth_header(token_a))
    await client.post(f"/like/{p2}", headers=auth_header(token_a))

    r = await client.get(
        "/like/batch",
        headers=auth_header(token_a),
        params=[("post_ids", str(p1)), ("post_ids", str(p2))],
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert batch[str(p1)]["count"] == 1
    assert batch[str(p1)]["liked_by_me"] is True
    assert batch[str(p2)]["count"] == 1
    assert batch[str(p2)]["liked_by_me"] is True


async def test_like_post_inexistente(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    r = await client.post("/like/99999999", headers=auth_header(token))
    assert r.status_code == 404


async def test_like_requer_auth(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client)
    post_id = (await cria_post(client, token_a, "x")).json()["id"]
    assert (await client.post(f"/like/{post_id}")).status_code == 401
    assert (await client.get(f"/like/{post_id}")).status_code == 401
    assert (await client.delete(f"/like/{post_id}")).status_code == 401
