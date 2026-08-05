"""Posts: criar, listar, feed, deletar e validações."""

import asyncio

from httpx import AsyncClient

from tests.helpers import (
    auth_header,
    cria_post,
    cria_usuario_com_token,
    seguir,
)


async def test_criar_post(client: AsyncClient):
    user, token = await cria_usuario_com_token(client, nome="Autor")
    resp = await cria_post(client, token, "Olá, este é um post de teste")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post"] == "Olá, este é um post de teste"
    assert data["usuario"]["id"] == user["id"]
    assert "id" in data
    assert "data_criacao" in data


async def test_criar_post_sem_auth(client: AsyncClient):
    resp = await client.post("/post/", json={"post": "sem token"})
    assert resp.status_code == 401


async def test_criar_post_vazio_ou_espacos(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    for conteudo in ("", "   ", "\n\t"):
        resp = await client.post(
            "/post/",
            json={"post": conteudo},
            headers=auth_header(token),
        )
        assert resp.status_code == 422, f"conteudo={conteudo!r} -> {resp.text}"


async def test_listar_posts(client: AsyncClient):
    user, token = await cria_usuario_com_token(client)
    texto = "post único do listador"
    assert (await cria_post(client, token, texto)).status_code == 200

    resp_list = await client.get("/post/", headers=auth_header(token))
    assert resp_list.status_code == 200, resp_list.text
    itens = resp_list.json()
    assert any(p["post"] == texto and p["usuario"]["id"] == user["id"] for p in itens)


async def test_listar_posts_paginacao_e_ordenacao(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    for i in range(3):
        assert (await cria_post(client, token, f"p{i}")).status_code == 200
        await asyncio.sleep(0.01)

    resp_desc = await client.get(
        "/post/",
        params={"limit": 2, "offset": 0, "sort": "-data"},
        headers=auth_header(token),
    )
    assert resp_desc.status_code == 200
    assert len(resp_desc.json()) == 2

    resp_asc = await client.get(
        "/post/",
        params={"limit": 50, "sort": "data"},
        headers=auth_header(token),
    )
    assert resp_asc.status_code == 200
    datas = [p["data_criacao"] for p in resp_asc.json()]
    assert datas == sorted(datas)


async def test_feed_prioriza_seguidos(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client, nome="Alice")
    b, token_b = await cria_usuario_com_token(client, nome="Bob")
    c, token_c = await cria_usuario_com_token(client, nome="Carol")

    assert (await seguir(client, token_a, b["id"])).status_code == 200

    txt_b = "post do Bob (seguido)"
    txt_c = "post da Carol (não seguido)"
    assert (await cria_post(client, token_b, txt_b)).status_code == 200
    assert (await cria_post(client, token_c, txt_c)).status_code == 200

    resp_feed = await client.get("/post/feed", headers=auth_header(token_a))
    assert resp_feed.status_code == 200, resp_feed.text
    feed = resp_feed.json()
    assert len(feed) >= 2

    ids = [item["usuario"]["id"] for item in feed]
    textos = [item["post"] for item in feed]
    assert ids[0] == b["id"]

    first_non_b = next((i for i, uid in enumerate(ids) if uid != b["id"]), None)
    if first_non_b is not None:
        assert all(uid != b["id"] for uid in ids[first_non_b:])

    assert txt_b in textos
    assert txt_c in textos


async def test_feed_ordem_temporal_dentro_dos_grupos(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client)
    b, token_b = await cria_usuario_com_token(client)
    c, token_c = await cria_usuario_com_token(client)

    assert (await seguir(client, token_a, b["id"])).status_code == 200

    assert (await cria_post(client, token_b, "B_old")).status_code == 200
    await asyncio.sleep(0.01)
    assert (await cria_post(client, token_c, "C_newer_than_B_old")).status_code == 200
    await asyncio.sleep(0.01)
    assert (await cria_post(client, token_b, "B_newest")).status_code == 200

    feed = (await client.get("/post/feed", headers=auth_header(token_a))).json()

    assert feed[0]["usuario"]["id"] == b["id"]
    assert feed[0]["post"] == "B_newest"
    assert feed[1]["usuario"]["id"] == b["id"]
    assert feed[1]["post"] == "B_old"
    assert feed[2]["usuario"]["id"] == c["id"]
    assert feed[2]["post"] == "C_newer_than_B_old"


async def test_deletar_post_autorizado_e_nao_autorizado(client: AsyncClient):
    dono, token_dono = await cria_usuario_com_token(client, nome="Dono")
    _, token_intruso = await cria_usuario_com_token(client, nome="Intruso")

    resp_create = await cria_post(client, token_dono, "post que só o dono pode deletar")
    assert resp_create.status_code == 200
    post_id = resp_create.json()["id"]

    resp_unauth = await client.delete(
        f"/post/{post_id}",
        headers=auth_header(token_intruso),
    )
    assert resp_unauth.status_code == 403

    resp_delete = await client.delete(
        f"/post/{post_id}",
        headers=auth_header(token_dono),
    )
    assert resp_delete.status_code == 200
    assert resp_delete.json()["deleted"] is True

    resp_list = await client.get("/post/", headers=auth_header(token_dono))
    assert all(p["id"] != post_id for p in resp_list.json())


async def test_deletar_post_inexistente(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    resp = await client.delete("/post/99999999", headers=auth_header(token))
    assert resp.status_code == 404
