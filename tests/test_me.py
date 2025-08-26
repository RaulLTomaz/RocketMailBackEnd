import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_me_endpoints(client: AsyncClient):
    # 1. Cria um usuário
    usuario_data = {
        "nome": "Usuario Teste",
        "email": "teste_me@example.com",
        "senha": "senha123"
    }
    resp = await client.post("/usuario/", json=usuario_data)
    assert resp.status_code == 200
    usuario = resp.json()
    usuario_id = usuario["id"]

    # 2. Login para obter token
    resp_login = await client.post(
        "/usuario/login",
        data={"username": usuario_data["email"], "password": usuario_data["senha"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert resp_login.status_code == 200
    token = resp_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. GET /me
    resp_me = await client.get("/usuario/me", headers=headers)
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["id"] == usuario_id
    assert me_data["email"] == usuario_data["email"]

    # 4. PATCH /me
    patch_payload = {"nome": "Usuario Alterado"}
    resp_patch = await client.patch("/usuario/me", json=patch_payload, headers=headers)
    assert resp_patch.status_code == 200
    assert resp_patch.json()["nome"] == "Usuario Alterado"

    # 5. DELETE /me
    resp_delete = await client.delete("/usuario/me", headers=headers)
    assert resp_delete.status_code == 200
    assert resp_delete.json()["deleted"] is True

    # 6. Verifica que o usuário foi realmente removido
    resp_check = await client.get(f"/usuario/{usuario_id}")
    assert resp_check.status_code == 404
