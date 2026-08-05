"""Seguir / deixar de seguir."""

from httpx import AsyncClient

from tests.helpers import (
    auth_header,
    cria_usuario_com_token,
    deixar_de_seguir,
    seguir,
)


async def test_seguir_requer_auth(client: AsyncClient):
    _, _ = await cria_usuario_com_token(client)
    b, _ = await cria_usuario_com_token(client)
    resp = await client.post("/seguir/", params={"seguido_id": b["id"]})
    assert resp.status_code == 401


async def test_seguir_e_deixar_de_seguir(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client, nome="Seguidor")
    b, _ = await cria_usuario_com_token(client, nome="Seguido")

    resp = await seguir(client, token_a, b["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["seguidor_id"] == a["id"]
    assert body["seguido_id"] == b["id"]

    resp2 = await seguir(client, token_a, b["id"])
    assert resp2.status_code == 200

    stats = await client.get(f"/usuario/{a['id']}/stats")
    assert stats.status_code == 200
    assert stats.json()["stats"]["seguindo"] == 1

    resp_un = await deixar_de_seguir(client, token_a, b["id"])
    assert resp_un.status_code == 200
    assert resp_un.json()["deleted"] is True

    stats2 = await client.get(f"/usuario/{a['id']}/stats")
    assert stats2.json()["stats"]["seguindo"] == 0


async def test_nao_pode_seguir_a_si_mesmo(client: AsyncClient):
    a, token_a = await cria_usuario_com_token(client)
    resp = await seguir(client, token_a, a["id"])
    assert resp.status_code == 400


async def test_seguir_usuario_inexistente(client: AsyncClient):
    _, token = await cria_usuario_com_token(client)
    resp = await seguir(client, token, 99999999)
    assert resp.status_code == 404


async def test_seguir_nao_usa_seguidor_id_da_query(client: AsyncClient):
    """IDOR: seguidor_id na query deve ser ignorado; vale só o JWT."""
    a, token_a = await cria_usuario_com_token(client)
    b, _ = await cria_usuario_com_token(client)
    c, _ = await cria_usuario_com_token(client)

    resp = await client.post(
        "/seguir/",
        params={"seguidor_id": c["id"], "seguido_id": b["id"]},
        headers=auth_header(token_a),
    )
    assert resp.status_code == 200
    assert resp.json()["seguidor_id"] == a["id"]
    assert resp.json()["seguido_id"] == b["id"]
