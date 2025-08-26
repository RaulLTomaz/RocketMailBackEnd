import pytest
from httpx import AsyncClient
from app.auth import gerar_token_teste

# ----------------- helpers (tudo via API) -----------------

async def _cria_usuario_api(client: AsyncClient, nome: str, email: str, senha: str = "senha_hashed") -> int:
    resp = await client.post(
        "/usuario/",
        json={"nome": nome, "email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]

async def _seguir_api(client: AsyncClient, seguidor_id: int, seguido_id: int) -> None:
    # Rotas de seguir recebem ids via querystring e não exigem auth
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

# ----------------- tests -----------------

@pytest.mark.asyncio
async def test_listar_posts(client: AsyncClient):
    # Arrange
    uid = await _cria_usuario_api(client, "Listador", "listador@example.com")
    token = gerar_token_teste(uid)
    texto = "post único do listador"

    resp_create = await _cria_post_api(client, token, texto)
    assert resp_create.status_code == 200, resp_create.text

    # Act
    resp_list = await client.get(
        "/post/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_list.status_code == 200, resp_list.text
    itens = resp_list.json()

    # Assert
    assert any(p["post"] == texto and p["usuario"]["id"] == uid for p in itens)

@pytest.mark.asyncio
async def test_feed_prioriza_seguidos(client: AsyncClient):
    """
    Novo comportamento: feed traz posts de quem eu sigo primeiro,
    depois os demais, ambos em ordem decrescente de data dentro de cada grupo.
    """
    # Arrange: A (viewer), B (seguido), C (não seguido)
    a = await _cria_usuario_api(client, "Alice", "alice@example.com")
    b = await _cria_usuario_api(client, "Bob", "bob@example.com")
    c = await _cria_usuario_api(client, "Carol", "carol@example.com")

    token_a = gerar_token_teste(a)
    token_b = gerar_token_teste(b)
    token_c = gerar_token_teste(c)

    # A segue B
    await _seguir_api(client, a, b)

    txt_b = "post do Bob (seguido)"
    txt_c = "post da Carol (não seguido)"
    assert (await _cria_post_api(client, token_b, txt_b)).status_code == 200
    assert (await _cria_post_api(client, token_c, txt_c)).status_code == 200

    # Act
    resp_feed = await client.get(
        "/post/feed",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_feed.status_code == 200, resp_feed.text
    feed = resp_feed.json()

    # Assert: o feed deve conter pelo menos os 2 posts criados
    assert len(feed) >= 2
    ids = [item["usuario"]["id"] for item in feed]
    textos = [item["post"] for item in feed]

    # 1) O primeiro(s) bloco(s) devem ser de B (seguido)
    assert ids[0] == b, f"Esperado primeiro post do seguido {b}, veio de {ids[0]}"

    # Descobre onde termina o bloco de seguidos (ids != b)
    first_non_b = next((i for i, uid in enumerate(ids) if uid != b), None)

    # 2) Depois que aparecer alguém que não é B, não pode mais aparecer B.
    if first_non_b is not None:
        assert all(uid != b for uid in ids[first_non_b:]), "Posts do seguido apareceram depois de não-seguidos"

    # 3) Os textos específicos estão presentes
    assert any(p == txt_b for p in textos)
    assert any(p == txt_c for p in textos)

@pytest.mark.asyncio
async def test_deletar_post_autorizado_e_nao_autorizado(client: AsyncClient):
    # Arrange
    dono = await _cria_usuario_api(client, "Dono", "dono@example.com")
    intruso = await _cria_usuario_api(client, "Intruso", "intruso@example.com")

    token_dono = gerar_token_teste(dono)
    token_intruso = gerar_token_teste(intruso)

    texto = "post que só o dono pode deletar"
    resp_create = await _cria_post_api(client, token_dono, texto)
    assert resp_create.status_code == 200, resp_create.text
    post_id = resp_create.json()["id"]

    # Intruso tenta deletar -> deve falhar
    resp_unauth = await client.delete(
        f"/post/{post_id}",
        headers={"Authorization": f"Bearer {token_intruso}"},
    )
    assert resp_unauth.status_code in (401, 403)

    # Dono deleta -> deve funcionar
    resp_delete = await client.delete(
        f"/post/{post_id}",
        headers={"Authorization": f"Bearer {token_dono}"},
    )
    assert resp_delete.status_code == 200

    # Confirma remoção
    resp_list = await client.get(
        "/post/",
        headers={"Authorization": f"Bearer {token_dono}"},
    )
    assert resp_list.status_code == 200, resp_list.text
    itens = resp_list.json()
    assert all(p["id"] != post_id for p in itens)
