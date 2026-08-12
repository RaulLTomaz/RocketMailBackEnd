# RocketMail Backend (FastAPI)

API REST do **RocketMail** — rede social no estilo Twitter/X — implementação original do backend com **FastAPI** e **PostgreSQL**.

---

## Status do Projeto

Este repositório está **arquivado** e **não recebe desenvolvimento ativo**.

- Esta foi a implementação **original** do backend, feita com FastAPI.
- Em seguida, os requisitos acadêmicos do projeto passaram a exigir **Django** como framework de backend.
- Por esse motivo, o desenvolvimento ativo foi migrado para uma implementação em Django.
- Este repositório permanece como **referência histórica** e demonstração do trabalho realizado com FastAPI, autenticação JWT, PostgreSQL async e deploy.

A migração **não** indica deficiência do FastAPI nem falha desta implementação — foi uma mudança de requisito do projeto.

| Recurso | Link |
|---|---|
| Frontend | [RocketMailFrontEnd](https://github.com/RaulLTomaz/RocketMailFrontEnd) |
| Backend atual (Django) | *[PREENCHER_URL_DO_REPOSITORIO_DJANGO]* |
| Deploy histórico (FastAPI) | [rocketmail-api.onrender.com](https://rocketmail-api.onrender.com) *(pode estar offline)* |
| App (frontend) | [rocket-mail-site.vercel.app](https://rocket-mail-site.vercel.app) |

---

## O que foi construído

- Cadastro, login (OAuth2 password) e JWT com expiração
- Perfil (`/me`), upload de foto (Cloudinary em produção / disco em dev)
- Busca de usuários (Explore) com posts recentes
- Posts, feed priorizado por quem você segue
- Seguir / deixar de seguir (idempotente; seguidor sempre do JWT)
- Likes idempotentes + resumo em lote
- Stats e timeline pública por usuário

---

## Stack

| Tecnologia | Uso |
|---|---|
| FastAPI | API HTTP assíncrona |
| PostgreSQL | Banco relacional |
| SQLAlchemy Core + databases/asyncpg | Models e queries async |
| JWT (python-jose) + bcrypt | Autenticação |
| Cloudinary | Fotos de perfil (produção) |
| pytest + httpx | Testes de integração |

---

## Arquitetura

```
rocketmail-backend/
├── app/
│   ├── main.py          # App, CORS, lifespan, /healthz
│   ├── database.py      # Conexão Postgres + ensure_schema
│   ├── security.py      # JWT, hashing e get_current_user
│   ├── auth.py          # Helper de JWT só para testes
│   ├── storage.py       # Upload (Cloudinary / disco local)
│   ├── models/          # Tabelas SQLAlchemy Core
│   ├── schemas/         # DTOs Pydantic
│   ├── crud/            # Regras de negócio + SQL
│   └── routers/         # Endpoints HTTP
├── tests/
├── requirements.txt
├── render.yaml
├── .env.example
├── .env.test.example
└── LICENSE
```

Camadas: **routers → crud → models/schemas**. Autenticação em `security.py`; I/O de mídia em `storage.py`.

---

## Decisões técnicas (resumo)

- Stack async (FastAPI + asyncpg); engine sync só para criar/ajustar schema no boot
- Feed priorizado em SQL (`CASE` + ordenação); search sem N+1 (`row_number`)
- Like/seguir idempotentes (`ON CONFLICT DO NOTHING`)
- Upload com validação por assinatura do arquivo; Cloudinary obrigatório em produção (disco do Render é efêmero)
- CORS em produção com origins explícitos + regex `*.vercel.app` (inclui localhost para testes manuais da época)
- `/healthz` é liveness simples (não consulta o banco) — adequado ao health check do Render free
- SSL do Postgres em produção sem verify-full por padrão (certificado gerenciado do Render)

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

## Variáveis de ambiente

Veja `.env.example`. Em resumo:

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Postgres (`postgresql://...`) |
| `SECRET_KEY` | Segredo JWT (**obrigatório** e forte em produção) |
| `ALLOWED_ORIGINS` | Origins CORS (vírgula) |
| `ALLOWED_ORIGIN_REGEX` | Regex CORS (default: `*.vercel.app` em prod) |
| `PYTHON_ENV` | `dev` / `test` / `production` |
| `RUN_MIGRATIONS` | `1` cria/atualiza schema no boot |
| `PUBLIC_BASE_URL` | URL pública da API |
| `CLOUDINARY_URL` | **Obrigatório em produção** para fotos |
| `DATABASE_SSL` / `DATABASE_SSL_VERIFY` | SSL do Postgres (Render: SSL on; verify off por default) |

Nunca versionar `.env` ou `.env.test`.

---

## Testes

```bash
cp .env.test.example .env.test
# Ajuste DATABASE_URL para um Postgres de teste local

pytest -q
```

A suíte cobre autenticação, ownership de posts, IDOR em seguir, feed, search, likes e upload de foto.

---

## Deploy histórico (Render)

O `render.yaml` descreve o serviço web + Postgres usados na época. Este deploy **não** é mais a API da aplicação em uso.

Se for recriar o ambiente apenas para estudo:

1. `RUN_MIGRATIONS=1` e `PUBLIC_BASE_URL`
2. `CLOUDINARY_URL` no Environment
3. Health check: `GET /healthz`

---

## Licença

MIT — veja [LICENSE](./LICENSE).

---

## Autor

**Raul Lopes Tomaz**  
[LinkedIn](https://www.linkedin.com/in/raul-lopes-tomaz-aa56a5267/)
