"""GET /usuario/search — Explore."""
from httpx import AsyncClient

from tests.helpers import auth_header, cria_post, cria_usuario_com_token


async def test_search_requer_auth(client: AsyncClient):
    resp = await client.get("/usuario/search", params={"q": "a"})
    assert resp.status_code == 401


async def test_search_q_vazio_400(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    resp = await client.get(
        "/usuario/search",
        params={"q": "   "},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_search_sem_match_retorna_lista_vazia(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    resp = await client.get(
        "/usuario/search",
        params={"q": "zzzz_inexistente_xyz"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_search_parcial_case_insensitive_com_posts(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client, nome="Ana Maria")
    b, token_b = await cria_usuario_com_token(client, nome="carla silva")
    await cria_usuario_com_token(client, nome="Bruno Costa")

    assert (await cria_post(client, token_a, "post antigo ana")).status_code == 200
    assert (await cria_post(client, token_a, "post novo ana")).status_code == 200
    assert (await cria_post(client, token_b, "post da carla")).status_code == 200

    # "ana" case-insensitive deve achar Ana Maria; não Bruno
    resp = await client.get(
        "/usuario/search",
        params={"q": "ANA", "limit": 20, "posts_per_user": 5},
        headers=auth_header(token_a),
    )
    assert resp.status_code == 200, resp.text
    hits = resp.json()
    assert len(hits) == 1
    assert hits[0]["usuario"]["id"] == a["id"]
    assert hits[0]["usuario"]["nome"] == "Ana Maria"
    assert "senha" not in hits[0]["usuario"]
    assert "email" in hits[0]["usuario"]
    assert len(hits[0]["posts"]) == 2
    # posts mais recentes primeiro
    assert hits[0]["posts"][0]["post"] == "post novo ana"
    assert hits[0]["posts"][0]["usuario"]["id"] == a["id"]
    assert "foto_url" in hits[0]["posts"][0]["usuario"]

    # parcial "sil" → carla silva
    resp2 = await client.get(
        "/usuario/search",
        params={"q": "Sil"},
        headers=auth_header(token_a),
    )
    assert resp2.status_code == 200
    nomes = [h["usuario"]["nome"] for h in resp2.json()]
    assert "carla silva" in nomes


async def test_search_limita_posts_por_usuario(client: AsyncClient):
    user, token = await cria_usuario_com_token(client, nome="Posts Limit User")
    for i in range(6):
        assert (await cria_post(client, token, f"p{i}")).status_code == 200

    resp = await client.get(
        "/usuario/search",
        params={"q": "Posts Limit", "posts_per_user": 2},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    hits = resp.json()
    assert len(hits) == 1
    assert len(hits[0]["posts"]) == 2


async def test_search_nao_conflita_com_id(client: AsyncClient):
    """GET /usuario/search não deve ser capturado por /{usuario_id}."""
    user, token = await cria_usuario_com_token(client, nome="Search Route")
    # se conflitar, FastAPI tentaria parsear "search" como int → 422
    resp = await client.get(
        "/usuario/search",
        params={"q": "Search"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert any(h["usuario"]["id"] == user["id"] for h in resp.json())

    # /usuario/{id} continua funcionando
    by_id = await client.get(f"/usuario/{user['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["id"] == user["id"]
