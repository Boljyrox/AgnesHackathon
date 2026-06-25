# Student Claw

AI project-management for student teams. A Telegram bot (Agnes AI) passively
tracks a group chat — extracting deadlines, delegating tasks, scoring
contributions, and answering questions over the project's history via RAG — and
a Next.js web dashboard surfaces it all in a Kanban board, deadline timeline,
contribution charts, and a chat-style "Ask Agnes" panel.

```
Telegram group ──► Bot (python-telegram-bot)
                        │
                        ▼
              FastAPI backend ──► Agnes AI (chat + embeddings)
              │   │   │   │
   PostgreSQL ┘   │   │   └─ MinIO (files)        Next.js web app ──► Google
   Qdrant (vectors)   └─ Redis (queue + pub/sub)   (BFF + dashboard)     Calendar
```

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| **Python** | **3.11 or 3.12** | ⚠️ Not 3.13+ — `python-telegram-bot` v20 is incompatible. |
| **Node.js** | 18.18+ or 20+ | For the Next.js frontend. |
| **Docker** + Docker Compose | any recent | Easiest way to run Postgres / Qdrant / Redis / MinIO. |
| **Tesseract OCR** | 5.x | Native binary required by `pytesseract` (image text extraction). |

Install Tesseract:

```bash
# macOS
brew install tesseract
# Debian/Ubuntu
sudo apt-get install -y tesseract-ocr
# Windows (choco)
choco install tesseract
```

---

## 2. Repository layout

```
student-claw/
├── backend/            FastAPI + Telegram bot + AI/RAG pipeline (Python)
│   ├── app/
│   │   ├── database/   SQLAlchemy models, connection, init
│   │   ├── bot/        Telegram handlers, webhook, services
│   │   ├── ai/         Parsing, embeddings, agent, calendar, pipeline
│   │   ├── api/        FastAPI routers, schemas, deps
│   │   └── core/       Auth, security, config
│   ├── main.py         FastAPI entrypoint
│   ├── requirements.txt
│   └── .env.example
├── frontend/           Next.js App Router (TypeScript)
│   ├── src/
│   ├── package.json
│   └── .env.example
└── docker-compose.yml  Local infra (Postgres/Qdrant/Redis/MinIO)
```

---

## 3. Obtain your API keys

You need three external credentials. Collect them before filling in `.env`.

### 3a. Agnes AI (required — chat + embeddings)
1. Sign in to the Agnes AI hub at **https://apihub.agnes-ai.com**.
2. Create an API key.
3. You'll use:
   - `AGNES_AI_API_KEY` = your key
   - `AGNES_AI_BASE_URL` = `https://apihub.agnes-ai.com/v1`
   - `AGNES_CHAT_MODEL` / `AGNES_EMBED_MODEL` — set to the model names your
     account exposes (defaults: `agnes-1`, `agnes-embeddings`).
   - `EMBED_DIM` — the embedding dimensionality of your embed model (default `1536`).

### 3b. Telegram bot (required)
1. In Telegram, message **@BotFather** → `/newbot` → follow prompts.
2. Copy the **HTTP API token** → `TELEGRAM_BOT_TOKEN`.
3. **Disable privacy mode** so the bot can read group messages (this is essential
   for the passive RAG listener): BotFather → `/setprivacy` → select your bot →
   **Disable**.
4. Set `TELEGRAM_BOT_USERNAME` to the bot's @username (without the `@`).

### 3c. Google Calendar OAuth2 (optional — deadline sync)
1. Go to **https://console.cloud.google.com** → create/select a project.
2. **APIs & Services → Library →** enable **Google Calendar API**.
3. **OAuth consent screen** → External → add yourself as a test user.
4. **Credentials → Create credentials → OAuth client ID → Web application.**
5. Add an **Authorized redirect URI**:
   `http://localhost:3000/api/integrations/google/callback`
6. Copy the **Client ID** → `GOOGLE_CLIENT_ID` and **Client secret** →
   `GOOGLE_CLIENT_SECRET` (set in **both** backend and frontend `.env`).

---

## 4. Generate the shared secrets

Several secrets must be **identical in the backend and frontend** `.env` files.
Generate them once and paste the same value into both:

```bash
# 32-byte hex secrets (use a fresh one for each line)
openssl rand -hex 32     # JWT_SECRET            (shared)
openssl rand -hex 32     # JWT_REFRESH_SECRET    (shared, different from above)
openssl rand -hex 32     # ENCRYPTION_KEY        (shared — must be 64 hex chars)
openssl rand -hex 32     # OAUTH_COOKIE_SECRET   (frontend)
openssl rand -hex 32     # PROJECT_KEY_HMAC_SECRET (backend)
openssl rand -hex 32     # TELEGRAM_WEBHOOK_SECRET (backend)
```

> **`ENCRYPTION_KEY` must decode to exactly 32 bytes** (AES-256). `openssl rand -hex 32`
> gives exactly 64 hex chars = 32 bytes. The backend and frontend use it to
> encrypt/decrypt the Google refresh token — if they differ, calendar sync breaks.

| Secret | Backend | Frontend | Must match? |
|---|:---:|:---:|:---:|
| `JWT_SECRET` | ✅ | ✅ | **Yes** |
| `JWT_REFRESH_SECRET` | ✅ | ✅ | **Yes** |
| `ENCRYPTION_KEY` | ✅ | ✅ | **Yes** |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | ✅ | ✅ | **Yes** |
| `REDIS_URL` | ✅ | ✅ | Yes (same instance) |
| `OAUTH_COOKIE_SECRET` | — | ✅ | n/a |
| `PROJECT_KEY_HMAC_SECRET`, `TELEGRAM_WEBHOOK_SECRET` | ✅ | — | n/a |

---

## 5. Start the infrastructure

The fastest path uses Docker:

```bash
cd student-claw
docker compose up -d
```

This launches:
- **PostgreSQL** on `localhost:5432` (db/user/pass = `student_claw`)
- **Qdrant** on `localhost:6333`
- **Redis** on `localhost:6379`
- **MinIO** on `localhost:9000` (console `:9001`, login `minioadmin` / `minioadmin`)

> Prefer your own managed services? Skip Compose and point the `DATABASE_URL`,
> `QDRANT_URL`, `REDIS_URL`, and `MINIO_*` env vars at them instead.

---

## 6. Backend setup

```bash
cd student-claw/backend

# 1) Virtual environment (Python 3.11/3.12)
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Environment
cp .env.example .env
#    → open .env and fill in every value from sections 3 & 4 above

# 4) Create the database tables (installs pgcrypto, creates all tables + enums)
python -m app.database.init_db
```

---

## 7. Frontend setup

```bash
cd student-claw/frontend

# 1) Install dependencies
npm install

# 2) Environment
cp .env.example .env
#    → fill in FASTAPI_BASE_URL, the SHARED secrets (JWT_SECRET,
#      JWT_REFRESH_SECRET, ENCRYPTION_KEY), REDIS_URL, OAUTH_COOKIE_SECRET,
#      and the Google client id/secret + redirect URI
```

---

## 8. Run everything (local development)

Open separate terminals (all from `student-claw/`, backend venv activated where
relevant):

```bash
# Terminal 1 — infra (if not already running)
docker compose up -d

# Terminal 2 — FastAPI web API            → http://localhost:8000  (docs: /docs)
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 3 — embedding worker (drains the Redis embed_queue)
cd backend && source .venv/bin/activate && python -m app.ai.pipeline

# Terminal 4 — Telegram bot (POLLING mode for local dev — no public URL needed)
cd backend && source .venv/bin/activate && python -m app.bot.bot

# Terminal 5 — Next.js dashboard          → http://localhost:3000
cd frontend && npm run dev
```

> In local dev the bot runs in **polling** mode (Terminal 4) and FastAPI logs
> that no `TELEGRAM_WEBHOOK_BASE_URL` is set — that's expected. In production you
> instead set `TELEGRAM_WEBHOOK_BASE_URL` to your public HTTPS host and drop
> Terminal 4; FastAPI registers the webhook and receives updates directly.

### First run — try it out
1. Open `http://localhost:3000` and register an account (set your Telegram
   username to match your real one).
2. Add your bot to a Telegram **group** → it replies with a **Project Key**.
3. In the dashboard, link the project with that key → it gives you a `/verify`
   token → send `/verify <token>` in the group to link your account.
4. Chat in the group, upload a PDF/PPTX/image, then ask the bot `/ask <question>`
   or use the dashboard's **Ask Agnes** panel.

---

## 9. Environment variable reference

### Backend (`backend/.env`)
| Variable | Required | Description |
|---|:---:|---|
| `DATABASE_URL` | ✅ | PostgreSQL async connection string. |
| `AGNES_AI_API_KEY` | ✅ | Agnes AI key. |
| `AGNES_AI_BASE_URL` | | Default `https://apihub.agnes-ai.com/v1`. |
| `AGNES_CHAT_MODEL` / `AGNES_EMBED_MODEL` | | Model names. |
| `EMBED_DIM` | | Embedding dimension (default `1536`). |
| `QDRANT_URL` / `QDRANT_API_KEY` | ✅/ | Vector DB. |
| `REDIS_URL` | ✅ | Queue + pub/sub. |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_SECURE` | ✅ | File storage. |
| `TELEGRAM_BOT_TOKEN` | ✅ | From BotFather. |
| `TELEGRAM_BOT_USERNAME` | | Bot @username. |
| `TELEGRAM_WEBHOOK_SECRET` | ✅ | Random secret. |
| `TELEGRAM_WEBHOOK_BASE_URL` | prod | Public HTTPS host (prod webhook only). |
| `PROJECT_KEY_HMAC_SECRET` | ✅ | Derives public project keys. |
| `JWT_SECRET` / `JWT_REFRESH_SECRET` | ✅ | Token signing (shared w/ frontend). |
| `ENCRYPTION_KEY` | ✅ | AES-256 key, 32 bytes (shared w/ frontend). |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | calendar | Google OAuth client. |
| `CORS_ORIGINS` | | Comma-separated allowed browser origins. |

### Frontend (`frontend/.env`)
| Variable | Required | Description |
|---|:---:|---|
| `FASTAPI_BASE_URL` | ✅ | e.g. `http://localhost:8000`. |
| `JWT_SECRET` / `JWT_REFRESH_SECRET` | ✅ | Shared with backend. |
| `ENCRYPTION_KEY` | ✅ | Shared with backend. |
| `REDIS_URL` | ✅ | Same Redis as backend (SSE pub/sub). |
| `OAUTH_COOKIE_SECRET` | ✅ | Signs the PKCE/state cookie (defaults to `JWT_SECRET`). |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | calendar | Same client as backend. |
| `GOOGLE_REDIRECT_URI` | calendar | `http://localhost:3000/api/integrations/google/callback`. |

---

## 10. Troubleshooting

- **`ModuleNotFoundError: telegram` / bot won't `.build()`** — you're on Python
  3.13+. Use 3.11 or 3.12.
- **Bot doesn't see group messages** — privacy mode is on. BotFather →
  `/setprivacy` → Disable, then remove & re-add the bot to the group.
- **OCR returns nothing / `TesseractNotFoundError`** — the Tesseract binary isn't
  installed or not on `PATH` (section 1).
- **Calendar sync silently does nothing** — `ENCRYPTION_KEY` differs between
  backend and frontend, or the user hasn't connected Google in Settings.
- **401 loops in the dashboard** — `JWT_SECRET` differs between backend and
  frontend; they must match exactly.
- **No real-time updates** — the frontend and backend must point at the *same*
  `REDIS_URL`.

---

## 11. Production notes
- Run the bot in **webhook** mode (set `TELEGRAM_WEBHOOK_BASE_URL`) behind HTTPS;
  serve FastAPI with `gunicorn -k uvicorn.workers.UvicornWorker`.
- Use **managed** Postgres/Redis/Qdrant or harden the Compose stack; enable
  MinIO TLS (`MINIO_SECURE=true`).
- `python -m app.database.init_db` is a dev bootstrap — adopt **Alembic**
  migrations for schema changes in production.
- Rotate all secrets; never commit `.env` (it's git-ignored).
