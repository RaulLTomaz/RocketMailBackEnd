# RocketMail Backend

API REST do **RocketMail** — rede social no estilo Twitter/X, feita com **FastAPI** e **PostgreSQL**.

Frontend: [RocketMailFrontEnd](https://github.com/RaulLTomaz/RocketMailFrontEnd)  
API em produção: [rocketmail-api.onrender.com](https://rocketmail-api.onrender.com)

---

## Stack

| Tecnologia | Uso |
|---|---|
| FastAPI | API HTTP assíncrona |
| PostgreSQL | Banco relacional |
| SQLAlchemy + databases/asyncpg | Models e queries async |
| JWT (python-jose) | Autenticação |
| Cloudinary | Fotos de perfil (produção) |
| pytest + httpx | Testes |

---

## Estrutura

```
rocketmail-backend/
├── app/
│   ├── main.py          # App FastAPI, CORS, lifespan, /healthz
│   ├── database.py      # Conexão Postgres (SSL em produção)
│   ├── auth.py          # Helper de token para testes
│   ├── storage.py       # Upload de foto (Cloudinary / disco local)
│   ├── models/          # Tabelas SQLAlchemy
│   ├── schemas/         # DTOs Pydantic
│   ├── crud/            # Regras de negócio
│   └── routers/         # Endpoints HTTP
├── tests/               # Suíte pytest
├── requirements.txt
├── render.yaml          # Deploy Render
├── .env.example         # Variáveis de ambiente (modelo)
└── pytest.ini
```

---

## Funcionalidades

- Cadastro, login (OAuth2 password) e JWT com expiração
- Perfil (`/me`), foto de perfil, busca de usuários (Explore)
- Posts, feed priorizado por quem você segue
- Seguir / deixar de seguir
- Likes (idempotente) + resumo em lote
- Stats e timeline pública por usuário

---

## Setup local

```bash
git clone https://github.com/RaulLTomaz/RocketMailBackEnd
cd RocketMailBackEnd

python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edite .env: DATABASE_URL, SECRET_KEY, etc.
```

Subir a API:

```bash
uvicorn app.main:app --reload
```

Docs interativas: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Variáveis importantes

Veja `.env.example`. Em resumo:

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Postgres (`postgresql://...`) |
| `SECRET_KEY` | Segredo JWT |
| `PYTHON_ENV` | `dev` / `test` / `production` |
| `RUN_MIGRATIONS` | `1` cria/atualiza schema no boot |
| `PUBLIC_BASE_URL` | URL pública da API |
| `CLOUDINARY_URL` | **Obrigatório em produção** para fotos |

---

## Testes

```bash
# Configure .env.test com um banco Postgres de teste
pytest -q
```

---

## Deploy (Render)

O arquivo `render.yaml` define o serviço web + banco. Após o push:

1. Confirme `RUN_MIGRATIONS=1` e `PUBLIC_BASE_URL`
2. Configure `CLOUDINARY_URL` no Environment do Render
3. Health check: `GET /healthz`

---

## Autor

**Raul Lopes Tomaz**  
[LinkedIn](https://www.linkedin.com/in/raul-lopes-tomaz-aa56a5267/)
