import pytest
import asyncio
from httpx import AsyncClient
from app.auth import gerar_token_teste

# --- helpers (via API) ---

async def _cria_usuario_api(client: AsyncClient, nome: str, email: str, senha: str = "senha_hashed") -> int:
    resp = await client.post(
        "/usuario/",
        json={"nome": nome, "email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]

async def _seguir_api(client: AsyncClient, seguidor_id: int, seguido_id: int) -> None:
    # segue via querystring (sem auth)
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

# --- teste ---

@pytest.mark.asyncio
async def test_feed_prioriza_seguidos(client: AsyncClient):
    """
    Cenário:
        - A (viewer) segue B, não segue C.
        - Ordem desejada no /post/feed:
            1) Todos os posts de B (em ordem desc por data)
            2) Depois posts de C (em ordem desc por data)
    Mesmo que C tenha post mais novo que um dos de B, B deve vir primeiro.
    """
    # Arrange
    a = await _cria_usuario_api(client, "Alice", "alice.feedordem@example.com")
    b = await _cria_usuario_api(client, "Bob", "bob.feedordem@example.com")
    c = await _cria_usuario_api(client, "Carol", "carol.feedordem@example.com")

    token_a = gerar_token_teste(a)
    token_b = gerar_token_teste(b)
    token_c = gerar_token_teste(c)

    # A segue B
    await _seguir_api(client, a, b)

    # Criamos posts com pequenos sleeps para garantir timestamps diferentes
    # 1) B posta (mais antigo entre os 3 que vamos criar)
    r1 = await _cria_post_api(client, token_b, "B_old")
    assert r1.status_code == 200

    await asyncio.sleep(0.01)

    # 2) C posta (mais novo que B_old)
    r2 = await _cria_post_api(client, token_c, "C_newer_than_B_old")
    assert r2.status_code == 200

    await asyncio.sleep(0.01)

    # 3) B posta de novo (o mais novo entre todos)
    r3 = await _cria_post_api(client, token_b, "B_newest")
    assert r3.status_code == 200

    # Act
    resp_feed = await client.get(
        "/post/feed",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_feed.status_code == 200, resp_feed.text
    feed = resp_feed.json()

    # Assert básico: feed contém posts de B e depois de C
    assert len(feed) >= 3
    # Os dois primeiros devem ser do seguido (B), em ordem decrescente de data
    assert feed[0]["usuario"]["id"] == b
    assert feed[0]["post"] == "B_newest"
    assert feed[1]["usuario"]["id"] == b
    assert feed[1]["post"] == "B_old"

    # O primeiro não-seguido (C) deve aparecer depois dos de B
    # (e pode estar em qualquer posição após a última entrada de B; aqui checamos logo o 3º)
    assert feed[2]["usuario"]["id"] == c
    assert feed[2]["post"] == "C_newer_than_B_old"

    # Sanidade: nenhum post de C aparece antes de todos os posts de B
    idx_primeiro_c = next(i for i, item in enumerate(feed) if item["usuario"]["id"] == c)
    idx_ultimo_b = max(i for i, item in enumerate(feed) if item["usuario"]["id"] == b)
    assert idx_primeiro_c > idx_ultimo_b
