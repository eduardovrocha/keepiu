# Keepiu

**Personal AI Vault — Capture, process and search your content automatically.**

![Keepiu Dashboard](docs/dashboard.png)

Keepiu is a self-hosted tool that turns everything you send — links, images, audio, video, Instagram posts — into structured, searchable knowledge. Forward content from Telegram or WhatsApp and get back summaries, tags, transcriptions, and semantic search, all stored privately on your own infrastructure.

---

## What is Keepiu?

Most people accumulate content they never revisit: articles saved for later, voice messages with important info, screenshots of posts worth keeping. Keepiu captures all of that, processes it with AI, and makes it retrievable.

It works as an automated second brain:

- **Send content** via Telegram bot, WhatsApp, or the web UI
- **AI processes it** — extracts text, transcribes audio, summarizes, tags
- **Search it** semantically — find what you saved even if you don't remember the exact words

---

## How it works

```
Telegram / WhatsApp
         ↓
   Receive content
         ↓
  OCR (images) / STT (audio & video)
         ↓
  AI analysis (summary, tags, sentiment, CTA)
         ↓
  Store in PostgreSQL + pgvector
         ↓
  Semantic search & dashboard
```

---

## Features

### Ingestion
- **Telegram bot** — send text, links, images, audio, video, or forwarded messages
- **WhatsApp** — receive content via WhatsApp Business API webhook

### Processing
- **OCR** — extract text from images using Tesseract
- **Audio & video transcription** — Speech-to-Text via OpenAI (`gpt-4o-mini-transcribe`)
- **Instagram intelligence** — capture public posts, extract captions, run OCR on carousel slides, and analyze tone, niche, CTA, and sentiment
- **AI analysis** — summarize, categorize, tag, and score every piece of content using OpenAI
- **Reprocessing** — re-run AI analysis on any saved content from the detail view

### Storage & Search
- **PostgreSQL 16 + pgvector** — structured storage with semantic vector embeddings
- **Semantic search** — find content by meaning, not just keywords
- **Dashboard** — overview of stats, recent content, and top categories

### Infrastructure
- **Async pipeline** — Celery + Redis for background processing
- **Inline mode** — run without Redis for single-instance deployments
- **Docker Compose** — single command to start everything
- **Flower** — task monitoring UI included

---

## Bots as the primary interface

The Telegram and WhatsApp bots are the fastest way to capture content on mobile. No app to open — just forward a message and Keepiu handles the rest.

- Share a YouTube link → get a summary and tags
- Send a voice message → get a transcript and key points
- Forward an Instagram post URL → get OCR, caption analysis, and sentiment
- Send a screenshot → get extracted text and categorization

---

## Quick Start

**Prerequisites:** Docker Desktop and an OpenAI API key.

### One-command setup (recommended)

```bash
git clone https://github.com/eduardovrocha/keepiu.git
cd keepiu
./install.sh
```

The script handles everything: creates `.env`, generates secrets, prompts for your OpenAI key and vault password, starts all containers, runs migrations, and verifies the app is healthy.

### Manual setup

<details>
<summary>Expand for step-by-step instructions</summary>

```bash
git clone https://github.com/eduardovrocha/keepiu.git
cd keepiu
cp .env.example .env
```

Edit `.env` with your credentials (see [Configuration](#configuration) below), then:

```bash
docker compose --profile internal-db up -d --build
docker compose run --rm backend alembic upgrade head
docker compose restart backend
```

</details>

Once running, open `http://localhost:5173` and log in with the password you set in `APP_PASSWORD`.

**Services started:**
- PostgreSQL 16 with pgvector
- Redis
- FastAPI backend — `http://localhost:8000`
- Celery worker + Flower (`http://localhost:5555`)
- React frontend — `http://localhost:5173`
- Landing page — `http://localhost:5174`

The landing page at `http://localhost:5174` is a static SPA (Next.js → nginx) and runs independently from the backend.

---

## Webhooks em Localhost (ngrok)

O Telegram e o WhatsApp entregam mensagens via **webhook HTTP POST** — ou seja, eles precisam conseguir alcançar o seu servidor. Em localhost isso não funciona sem um túnel público.

> Se você vai usar apenas a interface web (`http://localhost:5173`) sem bots, pule esta seção.

### Por que ngrok?

Quando a aplicação roda localmente, o endereço `http://localhost:8000` não é acessível pela internet. O Telegram e a API do WhatsApp Business precisam de uma URL pública com HTTPS para entregar os eventos. O ngrok cria um túnel que expõe sua porta local com uma URL pública.

```
Telegram / WhatsApp
        ↓
https://xxxx.ngrok-free.app/webhooks/telegram   ← URL pública (ngrok)
        ↓
http://localhost:8000/webhooks/telegram          ← seu backend local
```

### Instalação

**macOS:**
```bash
brew install ngrok
```

**Linux:**
```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

**Windows / outros:** baixe em [ngrok.com/download](https://ngrok.com/download) e adicione ao PATH.

### Configuração

1. Crie uma conta gratuita em [ngrok.com](https://ngrok.com) e obtenha seu authtoken.

2. Autentique o ngrok:
```bash
ngrok config add-authtoken SEU_AUTHTOKEN_AQUI
```

3. Inicie o túnel apontando para o backend (porta 8000):
```bash
ngrok http 8000
```

4. Copie a URL gerada — ela aparece na saída do ngrok:
```
Forwarding   https://xxxx-xx-xx-xxx-xx.ngrok-free.app -> http://localhost:8000
```

> A URL muda a cada reinicialização do ngrok na conta gratuita. Para uma URL fixa, use um domínio estático no plano pago ou configure um domínio próprio.

### Configurar o Webhook do Telegram

Com o túnel rodando, registre o webhook no Telegram via API:

```bash
curl -X POST "https://api.telegram.org/bot<SEU_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://xxxx.ngrok-free.app/webhooks/telegram",
    "secret_token": "signalvault-webhook-secret"
  }'
```

Substitua:
- `<SEU_BOT_TOKEN>` pelo token do seu bot (do [@BotFather](https://t.me/BotFather))
- `xxxx.ngrok-free.app` pela URL gerada pelo ngrok
- `signalvault-webhook-secret` pelo valor de `TELEGRAM_WEBHOOK_SECRET` no seu `.env`

Verifique se o webhook foi registrado:
```bash
curl "https://api.telegram.org/bot<SEU_BOT_TOKEN>/getWebhookInfo"
```

### Configurar o Webhook do WhatsApp

No [Meta for Developers](https://developers.facebook.com):

1. Acesse seu app → **WhatsApp → Configuration → Webhook**
2. Em **Callback URL**, informe:
   ```
   https://xxxx.ngrok-free.app/webhooks/whatsapp
   ```
3. Em **Verify Token**, informe o valor de `WHATSAPP_VERIFY_TOKEN` do seu `.env`
4. Clique em **Verify and Save**
5. Assine os campos: `messages`

### Variáveis de ambiente relevantes

```env
# Telegram
TELEGRAM_BOT_TOKEN=seu-token-aqui
TELEGRAM_WEBHOOK_SECRET=signalvault-webhook-secret   # mesmo valor usado no setWebhook

# WhatsApp
WHATSAPP_VERIFY_TOKEN=seu-verify-token-aqui
WHATSAPP_ACCESS_TOKEN=seu-access-token-aqui
WHATSAPP_PHONE_NUMBER_ID=seu-phone-number-id
WHATSAPP_APP_SECRET=seu-app-secret-aqui              # usado para validar assinatura HMAC

# URL do frontend (CORS)
FRONTEND_URL=http://localhost:5173
```

> Todas essas variáveis também podem ser configuradas pela interface web em **Settings**, sem necessidade de reiniciar a aplicação.

---

## Configuration

Key variables in `.env`:

```env
# Required
OPENAI_API_KEY=sk-...
JWT_SECRET=change-this-to-a-random-string
SESSION_SECRET=change-this-to-a-random-string

# App mode
APP_MODE=single_user          # single_user | multi_user
APP_PASSWORD=your-password    # used when APP_MODE=single_user

# Telegram (optional — configure via Settings UI instead)
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=

# WhatsApp (optional — configure via Settings UI instead)
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_APP_SECRET=

# Processing mode
PROCESSING_MODE=worker        # worker | inline (no Redis required)

# Encryption key for secrets stored in DB
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SETTINGS_ENCRYPTION_KEY=
```

All integration keys (Telegram, WhatsApp, OpenAI) can also be set through the **Settings** page in the dashboard without restarting the application.

---

## Authentication

Keepiu supports two modes:

| Mode | Description |
|------|-------------|
| `single_user` | One shared password. Session stored in a secure httpOnly cookie. Ideal for personal use. |
| `multi_user` | Each Telegram/WhatsApp user gets their own account. Admin promoted via `INITIAL_ADMIN_USERNAME`. |

---

## Project Structure

```
keepiu/
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/           # FastAPI route handlers
│   │   │   ├── core/          # Config, database, security
│   │   │   ├── models/        # SQLAlchemy ORM models
│   │   │   ├── schemas/       # Pydantic request/response schemas
│   │   │   ├── services/      # Business logic (AI, ingestion, Instagram, settings)
│   │   │   ├── workers/       # Celery tasks (content, audio, Instagram, WhatsApp)
│   │   │   └── utils/         # OCR, audio extraction, transcription, link parsing
│   │   └── migrations/        # Alembic database migrations
│   └── frontend/
│       └── src/
│           ├── components/    # Shared UI components
│           ├── pages/         # Route-level pages (Dashboard, Library, ContentDetail, Settings)
│           ├── hooks/         # React Query data hooks
│           ├── services/      # API client
│           └── store/         # Zustand auth state
├── docker-compose.yml
├── docker-compose.prod.yml
└── .env.example
```

---

## Roadmap

### In progress / next
- **LinkedIn content capture** — public posts, text extraction, professional content analysis
- **Granular reprocessing** — choose which pipeline stages to re-run (OCR only, AI only, etc.)
- **Pipeline observability** — per-task metrics and error details in the dashboard

### Planned
- Browser extension for one-click capture from any webpage
- Mobile-optimized dashboard view
- Export to Notion / Obsidian / JSON
- Scheduled digests (daily/weekly summaries by email or Telegram)

---

## Contributing

### Getting started

1. Fork the repository
2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes following the existing code style
4. Open a Pull Request with a clear description of what changed and why

### Guidelines

- Keep the processing pipeline intact — new content types should follow the existing worker pattern (`bind=True` Celery task with stage tracking)
- Backend changes that touch the database need an Alembic migration
- Frontend components should use the existing `Card`, `LoadingSpinner`, and React Query hooks
- Add tests where the logic is non-trivial
- Describe your PR clearly — what it does, what it doesn't do, and how to test it

### Reporting issues

Use GitHub Issues. Include:
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (check `docker compose logs worker` for processing errors)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12, SQLAlchemy, Alembic |
| Database | PostgreSQL 16, pgvector |
| Queue | Celery, Redis |
| AI | OpenAI (GPT-4o, Whisper STT, embeddings) |
| OCR | Tesseract, ffmpeg |
| Browser automation | Playwright (Instagram capture) |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, React Query, Zustand |
| Infrastructure | Docker, Docker Compose |

---

## License

MIT — free to use, modify, and self-host.
