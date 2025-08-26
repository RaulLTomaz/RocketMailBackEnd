import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, or_
from app.main import app
from app.database import database
from app.models.usuario import usuario
from app.models.post import post
from app.models.seguir import seguir
from app.models.like import like
from app.auth import gerar_token_teste


@pytest.mark.asyncio
async def test_criar_post():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Garante conexão para o teste
        if not database.is_connected:
            await database.connect()

        # Cria usuário
        query_usuario = usuario.insert().values(
            nome="Usuário Teste",
            email="teste@example.com",
            senha="senha_hashed",
        )
        usuario_id = await database.execute(query_usuario)

        # Gera token
        token = gerar_token_teste(usuario_id)

        # Cria post via API
        post_data = {"post": "Olá, este é um post de teste"}
        response = await client.post(
            "/post/",
            json=post_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        # Asserções
        assert response.status_code == 200
        data = response.json()
        assert data["post"] == post_data["post"]
        assert data["usuario"]["id"] == usuario_id
        assert "id" in data
        assert "data_criacao" in data

        # ----------------- Limpeza específica (sem afetar outros testes) -----------------
        # Apaga likes dos posts deste usuário
        sub_posts = select(post.c.id).where(post.c.usuario_id == usuario_id)
        await database.execute(
            like.delete().where(like.c.post_id.in_(sub_posts))
        )
        # Apaga posts deste usuário
        await database.execute(
            post.delete().where(post.c.usuario_id == usuario_id)
        )
        # Apaga relações de seguir envolvendo este usuário (como seguidor ou seguido)
        await database.execute(
            seguir.delete().where(
                or_(
                    seguir.c.seguidor_id == usuario_id,
                    seguir.c.seguido_id == usuario_id,
                )
            )
        )
        # Por fim, apaga o usuário criado neste teste
        await database.execute(
            usuario.delete().where(usuario.c.id == usuario_id)
        )
