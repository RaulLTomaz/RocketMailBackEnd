"""Perfil público: stats e timeline."""
import asyncio

from httpx import AsyncClient

from tests.helpers import cria_post, cria_usuario_com_token, seguir


async def test_stats_usuario_contadores(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client, nome="AliceStats")
    b, _ = await cria_usuario_com_token(client, nome="BobStats")
    c, token_c = await cria_usuario_com_token(client, nome="CarolStats")

    assert (await cria_post(client, token_a, "post 1 da Alice")).status_code == 200
    await asyncio.sleep(0.01)
    assert (await cria_post(client, token_a, "post 2 da Alice")).status_code == 200

    assert (await seguir(client, token_a, b["id"])).status_code == 200
    assert (await seguir(client, token_c, a["id"])).status_code == 200

    resp = await client.get(f"/usuario/{a['id']}/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["usuario"]["id"] == a["id"]
    assert body["stats"]["posts"] == 2
    assert body["stats"]["seguidores"] == 1
    assert body["stats"]["seguindo"] == 1


async def test_stats_usuario_inexistente(client: AsyncClient):
    resp = await client.get("/usuario/99999999/stats")
    assert resp.status_code == 404


async def test_timeline_usuario_paginada(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client, nome="AliceTL")
    b, token_b = await cria_usuario_com_token(client, nome="BobTL")

    assert (await cria_post(client, token_a, "A_post_1")).status_code == 200
    await asyncio.sleep(0.01)
    assert (await cria_post(client, token_a, "A_post_2")).status_code == 200
    await asyncio.sleep(0.01)
    assert (await cria_post(client, token_a, "A_post_3")).status_code == 200
    assert (await cria_post(client, token_b, "B_post_1")).status_code == 200

    resp_all = await client.get(f"/usuario/{a['id']}/posts")
    assert resp_all.status_code == 200
    items = resp_all.json()
    assert len(items) == 3
    assert all(p["usuario"]["id"] == a["id"] for p in items)
    assert [p["post"] for p in items] == ["A_post_3", "A_post_2", "A_post_1"]

    page1 = (
        await client.get(f"/usuario/{a['id']}/posts", params={"limit": 2, "offset": 0})
    ).json()
    assert [p["post"] for p in page1] == ["A_post_3", "A_post_2"]

    page2 = (
        await client.get(f"/usuario/{a['id']}/posts", params={"limit": 2, "offset": 2})
    ).json()
    assert [p["post"] for p in page2] == ["A_post_1"]
