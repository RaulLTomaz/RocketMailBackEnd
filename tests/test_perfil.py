import asyncio
import pytest
from httpx import AsyncClient
from app.auth import gerar_token_teste


# ----------------- helpers -----------------

async def _cria_usuario_api(client: AsyncClient, nome: str, email: str, senha: str = "senha123") -> int:
    resp = await client.post(
        "/usuario/",
        json={"nome": nome, "email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _seguir_api(client: AsyncClient, seguidor_id: int, seguido_id: int) -> None:
    # suas rotas de seguir usam querystring e não exigem auth
    resp = await client.post(
        "/seguir/",
        params={"seguidor_id": seguidor_id, "seguido_id": seguido_id},
    )
    assert resp.status_code == 200, resp.text


async def _cria_post_api(client: AsyncClient, token: str, conteudo: str):
    return await client.post(
        "/post/",
        json={"post": conteudo},
        headers={"Authorization": f"Bearer {token}"},
    )


# ----------------- testes -----------------


@pytest.mark.asyncio
async def test_stats_usuario_contadores(client: AsyncClient):
    """
    Cenário:
      - Usuário A cria 2 posts.
      - A segue B  -> seguindo(A) = 1
      - C segue A  -> seguidores(A) = 1
      - Posts(A)   = 2
    Verifica /usuario/{id}/stats
    """
    # Arrange
    a = await _cria_usuario_api(client, "AliceStats", "alice.stats@example.com")
    b = await _cria_usuario_api(client, "BobStats", "bob.stats@example.com")
    c = await _cria_usuario_api(client, "CarolStats", "carol.stats@example.com")

    token_a = gerar_token_teste(a)

    assert (await _cria_post_api(client, token_a, "post 1 da Alice")).status_code == 200
    await asyncio.sleep(0.01)  # garante ordem temporal distinta
    assert (await _cria_post_api(client, token_a, "post 2 da Alice")).status_code == 200

    # A segue B (A -> seguindo = 1)
    await _seguir_api(client, a, b)
    # C segue A (A -> seguidores = 1)
    await _seguir_api(client, c, a)

    # Act
    resp = await client.get(f"/usuario/{a}/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Assert
    assert body["usuario"]["id"] == a
    assert body["stats"]["posts"] == 2
    assert body["stats"]["seguidores"] == 1
    assert body["stats"]["seguindo"] == 1


@pytest.mark.asyncio
async def test_timeline_usuario_paginada(client: AsyncClient):
    """
    Gera 3 posts para o usuário A, 1 para B.
    Valida que /usuario/{A}/posts:
      - retorna apenas posts de A
      - ordenados desc por data_criacao
      - paginados via limit/offset
    """
    # Arrange
    a = await _cria_usuario_api(client, "AliceTL", "alice.tl@example.com")
    b = await _cria_usuario_api(client, "BobTL", "bob.tl@example.com")

    token_a = gerar_token_teste(a)
    token_b = gerar_token_teste(b)

    # 3 posts de A em ordem temporal
    r1 = await _cria_post_api(client, token_a, "A_post_1")
    assert r1.status_code == 200
    await asyncio.sleep(0.01)

    r2 = await _cria_post_api(client, token_a, "A_post_2")
    assert r2.status_code == 200
    await asyncio.sleep(0.01)

    r3 = await _cria_post_api(client, token_a, "A_post_3")
    assert r3.status_code == 200

    # 1 post de B (não deve aparecer na timeline de A)
    assert (await _cria_post_api(client, token_b, "B_post_1")).status_code == 200

    # Act: sem paginação explícita (default)
    resp_all = await client.get(f"/usuario/{a}/posts")
    assert resp_all.status_code == 200, resp_all.text
    items = resp_all.json()

    # Assert: só posts de A e ordem desc (A_post_3, A_post_2, A_post_1)
    assert len(items) == 3
    assert all(p["usuario"]["id"] == a for p in items)
    titles = [p["post"] for p in items]
    assert titles == ["A_post_3", "A_post_2", "A_post_1"]

    # Act: paginação limit=2 (primeiras 2)
    resp_page1 = await client.get(f"/usuario/{a}/posts", params={"limit": 2, "offset": 0})
    assert resp_page1.status_code == 200, resp_page1.text
    page1 = resp_page1.json()
    assert [p["post"] for p in page1] == ["A_post_3", "A_post_2"]

    # Act: segunda página offset=2
    resp_page2 = await client.get(f"/usuario/{a}/posts", params={"limit": 2, "offset": 2})
    assert resp_page2.status_code == 200, resp_page2.text
    page2 = resp_page2.json()
    assert [p["post"] for p in page2] == ["A_post_1"]
