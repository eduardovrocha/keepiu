# Keepiu — Local Installation Guide

> **Goal:** Run Keepiu locally from scratch, with no prior knowledge of the project.
> If it takes more than 10 minutes to get running, the documentation is incomplete.

---

## Environment Prerequisites

**Required:**
- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- Docker Compose ≥ 2.20 (included in Docker Desktop)
- OpenAI account with a valid API key

**Optional (without Docker):**
- Python 3.12+
- Node.js 20+
- PostgreSQL 16 with `pgvector` extension
- Redis 7+

Quick check:
```bash
docker --version          # Docker version 24.x.x
docker compose version    # Docker Compose version v2.x.x
```

---

## Execution Modes

The project has two independent configuration axes that determine setup complexity:

| Variable | Option A (simple) | Option B (full) |
|---|---|---|
| `APP_MODE` | `single_user` — one password, no registration | `multi_user` — user accounts |
| `PROCESSING_MODE` | `inline` — no Redis, synchronous | `worker` — Celery + Redis (async) |

**For the lowest-friction local setup:** use `single_user` + `inline`.

---

## Complete Flow: From Zero to Running

### Step 1 — Clone and set up the environment

```bash
git clone <repository-url> keepiu
cd keepiu
cp .env.example .env
```

### Step 2 — Configure `.env`

Open `.env` and fill in the values below. Everything else can keep its defaults.

**Minimum working configuration:**

```env
# ── REQUIRED ──────────────────────────────────────────────────────────────

# OpenAI key (GPT-4o, Whisper, embeddings)
OPENAI_API_KEY=sk-...

# App mode — single_user = personal vault, one password
APP_MODE=single_user

# Vault access password (required in single_user mode)
APP_PASSWORD=your-password-here

# Session signing key — generate with the command below
# python3 -c "import secrets; print(secrets.token_hex(32))"
SESSION_SECRET=generate-a-value-here

# Encryption key for secrets stored in the database
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SETTINGS_ENCRYPTION_KEY=generate-a-value-here

# ── LOCAL SIMPLIFICATION ──────────────────────────────────────────────────

# No Redis — tasks processed inline (no workers, no Flower)
PROCESSING_MODE=inline

# Development environment
ENVIRONMENT=development

# API URL consumed by the frontend
VITE_API_URL=http://localhost:8000

# ── OPTIONAL (can be left empty for now) ─────────────────────────────────

TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=signalvault-webhook-secret
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_APP_SECRET=
VITE_TELEGRAM_BOT_LINK=
SENTRY_DSN=

# Database (used internally by the internal-db profile)
POSTGRES_USER=signalvault
POSTGRES_PASSWORD=signalvault
POSTGRES_DB=signalvault
FLOWER_BASIC_AUTH=admin:changeme
JWT_SECRET=signalvault-jwt-secret-change-in-production
FRONTEND_URL=http://localhost:5173
```

Generate both secrets at once:
```bash
python3 -c "import secrets; print('SESSION_SECRET=' + secrets.token_hex(32))"
python3 -c "from cryptography.fernet import Fernet; print('SETTINGS_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

### Step 3 — Start the services

The `--profile internal-db` flag activates PostgreSQL and Redis as containers. Without it, docker-compose expects them running on the host.

```bash
docker compose --profile internal-db up -d
```

This starts: `db`, `redis`, `backend`, `worker`, `flower`, `frontend`, `landing`.

> With `PROCESSING_MODE=inline`, `worker` and `flower` start but stay idle — they cause no issues and can be ignored.

Wait for containers to stabilize (~30 seconds):
```bash
docker compose ps
```

All services should show `Up` or `healthy`.

### Step 4 — Run database migrations

In development mode, migrations **do not run automatically**. Run them manually:

```bash
docker compose run --rm backend alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade -> 0001, initial schema
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, add indexes
...
INFO  [alembic.runtime.migration] Running upgrade 0014 -> 0015, add ocr blocks
```

### Step 5 — Restart the backend

After migrations, restart the backend so the startup hook creates the owner user:

```bash
docker compose restart backend
```

### Step 6 — Access the application

| Service | URL | Credentials |
|---|---|---|
| Frontend (UI) | http://localhost:5173 | password = value of `APP_PASSWORD` |
| Backend API | http://localhost:8000 | — |
| API Docs | http://localhost:8000/docs | — |
| Health check | http://localhost:8000/health | — |
| Flower (tasks) | http://localhost:5555 | `admin:changeme` |
| Landing page | http://localhost:5174 | — |

---

## Ports Used

| Port | Service | Notes |
|---|---|---|
| `5173` | React frontend (Vite) | Main interface |
| `5174` | Landing page (Next.js) | Public page |
| `8000` | FastAPI backend | REST API + webhooks |
| `5555` | Flower | Celery task monitor |
| `5432` | PostgreSQL | Internal, not exposed |
| `6379` | Redis | Internal, not exposed |

---

## Verifying Everything Works

**1. Backend health check:**
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "mode": "single_user",
  "db": "ok",
  "redis": "ok"
}
```

**2. Check backend logs:**
```bash
docker compose logs backend --tail=50
```
Look for:
```
INFO  Application startup complete
INFO  Bootstrap: owner account created/found
INFO  Admin bootstrap complete
```

**3. Confirm the database was migrated:**
```bash
docker compose exec db psql -U signalvault -d signalvault -c "\dt"
```
Should list: `users`, `contents`, `content_embeddings`, `system_settings`, `refresh_tokens`, etc.

**4. Access the UI and log in:**
- Open http://localhost:5173
- In `single_user` mode, enter the value of `APP_PASSWORD`
- The dashboard should load without errors

---

## Environment Variables — Complete Reference

### Required

| Variable | Purpose | Example |
|---|---|---|
| `OPENAI_API_KEY` | GPT-4o (summaries, tags), Whisper (STT), embeddings | `sk-proj-...` |
| `APP_PASSWORD` | Vault password (`single_user` only) | `my-password` |
| `SESSION_SECRET` | Signs session cookies (`single_user` only) | `token_hex(32)` |

### Strongly Recommended

| Variable | Purpose | Default |
|---|---|---|
| `SETTINGS_ENCRYPTION_KEY` | Encrypts secrets stored in the database (tokens, API keys) | empty (unencrypted) |
| `APP_MODE` | `single_user` or `multi_user` | `multi_user` |
| `PROCESSING_MODE` | `inline` (no Redis) or `worker` (Celery) | `worker` |
| `ENVIRONMENT` | `development` or `production` | `development` |

### Database

| Variable | Purpose | Default (internal-db) |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL user | `signalvault` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `signalvault` |
| `POSTGRES_DB` | Database name | `signalvault` |
| `DATABASE_URL` | Full connection URL | `postgresql://postgres:password@host.docker.internal:5432/signalvault` |

### Optional (bots and integrations)

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (can be configured via UI later) |
| `TELEGRAM_WEBHOOK_SECRET` | Validates incoming Telegram requests |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook verification token |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp Business API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID |
| `WHATSAPP_APP_SECRET` | Validates HMAC webhook signature |
| `VITE_TELEGRAM_BOT_LINK` | Public bot link (e.g. `https://t.me/MyBot`) |
| `SENTRY_DSN` | Error tracking (Sentry) |
| `INITIAL_ADMIN_USERNAME` | Username promoted to admin on startup (`multi_user`) |
| `FLOWER_BASIC_AUTH` | Flower auth (`user:password`) |
| `JWT_SECRET` | JWT secret (`multi_user`) |
| `FRONTEND_URL` | Frontend origin for CORS |

---

## Database Configuration

### Automatic initialization

With `--profile internal-db`, the PostgreSQL container is created with:
- User: `POSTGRES_USER` (default: `signalvault`)
- Password: `POSTGRES_PASSWORD` (default: `signalvault`)
- Database: `POSTGRES_DB` (default: `signalvault`)
- `pgvector` extension pre-installed in the `ankane/pgvector:v0.5.1` image

### Migrations

```bash
# Run all migrations (0001 → 0015)
docker compose run --rm backend alembic upgrade head

# Check current migration
docker compose run --rm backend alembic current

# View history
docker compose run --rm backend alembic history
```

### Direct database access

```bash
docker compose exec db psql -U signalvault -d signalvault
```

---

## Running Without Docker (Optional)

Useful for active backend debugging or development.

### Backend

```bash
cd apps/backend

# Install system dependencies (macOS)
brew install tesseract ffmpeg

# Create a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Set environment variables
export $(cat ../../.env | grep -v '^#' | xargs)
export DATABASE_URL="postgresql://signalvault:signalvault@localhost:5432/signalvault"
export REDIS_URL="redis://localhost:6379/0"

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd apps/frontend

npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

### Celery Worker (optional, only if `PROCESSING_MODE=worker`)

```bash
cd apps/backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info -Q processing,default
```

---

## What Can Be Disabled (Simplification)

| Component | How to disable | Impact |
|---|---|---|
| Redis + Worker + Flower | `PROCESSING_MODE=inline` in `.env` | Tasks processed synchronously. Slower, no parallelism, but fully functional. |
| Telegram Bot | Leave `TELEGRAM_BOT_TOKEN` empty | No Telegram message ingestion |
| WhatsApp Bot | Leave all `WHATSAPP_*` empty | No WhatsApp message ingestion |
| Landing page | Remove `landing` service from compose | Suppresses the marketing page only |
| Flower | Remove `flower` service from compose | No task monitor UI |
| Sentry | Leave `SENTRY_DSN` empty | No error tracking |

**Absolute minimum setup:** only `OPENAI_API_KEY`, `APP_MODE=single_user`, `APP_PASSWORD`, `SESSION_SECRET`, and `PROCESSING_MODE=inline`.

---

## Common Issues

### `alembic upgrade head` fails with "connection refused"

The database is not ready yet. Wait for the healthcheck to pass:
```bash
docker compose ps  # Confirm keepiu-db shows "healthy"
docker compose run --rm backend alembic upgrade head
```

### Frontend shows "Network Error" or 502

`VITE_API_URL` is misconfigured. Verify:
```bash
curl http://localhost:8000/health
```
If it fails, check the logs:
```bash
docker compose logs backend --tail=30
```

### Backend warns "SETTINGS_ENCRYPTION_KEY not set"

In development this is just a warning. To suppress it, generate and add the key to `.env`:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `host.docker.internal` does not resolve (Linux)

On Linux this is not resolved automatically. Use `--profile internal-db`, or add it to `/etc/hosts`:
```bash
echo "172.17.0.1 host.docker.internal" | sudo tee -a /etc/hosts
```

### Migrations ran but owner user was not created

The owner user is created at backend startup, not during migrations. After running `alembic upgrade head`, restart:
```bash
docker compose restart backend
docker compose logs backend | grep -i "bootstrap\|owner\|startup"
```

### Port 5173 or 8000 already in use

```bash
lsof -i :5173
lsof -i :8000
# Or change the port in docker-compose.yml: "8001:8000"
```

### Backend image build takes too long

The image includes Tesseract, ffmpeg, and Chromium (Playwright). The first build takes 3–5 minutes. Subsequent builds use the cache.

### Embeddings fail (pgvector)

Make sure you are using the `ankane/pgvector:v0.5.1` image and not a standard PostgreSQL image. The `--profile internal-db` flag guarantees this automatically.

---

## Setup Checklist

```
[ ] Docker and Docker Compose installed
[ ] Repository cloned
[ ] .env created from .env.example
[ ] OPENAI_API_KEY set
[ ] APP_MODE=single_user configured
[ ] APP_PASSWORD set
[ ] SESSION_SECRET generated (token_hex(32))
[ ] PROCESSING_MODE=inline (simple) or worker (with Redis)
[ ] docker compose --profile internal-db up -d executed
[ ] docker compose ps — all services Up/healthy
[ ] docker compose run --rm backend alembic upgrade head executed
[ ] docker compose restart backend executed
[ ] GET http://localhost:8000/health returns {"status":"healthy"}
[ ] http://localhost:5173 loads and accepts login with APP_PASSWORD
```

---

## Command Summary

```bash
# Full setup from scratch
git clone <repo> keepiu && cd keepiu
cp .env.example .env
# edit .env with OPENAI_API_KEY, APP_PASSWORD, SESSION_SECRET

docker compose --profile internal-db up -d
docker compose run --rm backend alembic upgrade head
docker compose restart backend

# Verify
curl http://localhost:8000/health
open http://localhost:5173
```
