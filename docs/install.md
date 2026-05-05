# Keepiu — Guia de Instalação Local

> **Objetivo:** Rodar o Keepiu localmente do zero, sem conhecimento prévio do projeto.
> Se não for possível rodar em menos de 10 minutos, a documentação está incompleta.

---

## Pré-requisitos do Ambiente

**Obrigatório:**
- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- Docker Compose ≥ 2.20 (incluso no Docker Desktop)
- Conta OpenAI com API Key válida

**Opcional (sem Docker):**
- Python 3.12+
- Node.js 20+
- PostgreSQL 16 com extensão `pgvector`
- Redis 7+

Verificação rápida:
```bash
docker --version          # Docker version 24.x.x
docker compose version    # Docker Compose version v2.x.x
```

---

## Modos de Execução

O projeto tem dois eixos de configuração independentes que determinam a complexidade do setup:

| Variável | Opção A (simples) | Opção B (completo) |
|---|---|---|
| `APP_MODE` | `single_user` — uma senha, sem registro | `multi_user` — cadastro de usuários |
| `PROCESSING_MODE` | `inline` — sem Redis, tudo síncrono | `worker` — Celery + Redis (assíncrono) |

**Para rodar localmente com o mínimo de fricção:** use `single_user` + `inline`.

---

## Fluxo Completo: Do Zero ao Rodando

### Passo 1 — Clone e configure o ambiente

```bash
git clone <url-do-repositório> keepiu
cd keepiu
cp .env.example .env
```

### Passo 2 — Configure o `.env`

Abra o `.env` e preencha os valores abaixo. O restante pode ficar com os defaults.

**Configuração mínima funcional:**

```env
# ── OBRIGATÓRIO ────────────────────────────────────────────────────────────

# Chave OpenAI (GPT-4o, Whisper, embeddings)
OPENAI_API_KEY=sk-...

# Modo da aplicação — single_user = vault pessoal, uma senha
APP_MODE=single_user

# Senha de acesso ao vault (obrigatória no single_user)
APP_PASSWORD=minha-senha-aqui

# Chave de sessão — gere com o comando abaixo
# python3 -c "import secrets; print(secrets.token_hex(32))"
SESSION_SECRET=gere-um-valor-aqui

# Chave de criptografia para segredos no banco
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SETTINGS_ENCRYPTION_KEY=gere-um-valor-aqui

# ── SIMPLIFICAÇÃO LOCAL ────────────────────────────────────────────────────

# Sem Redis — tasks processadas em linha (sem workers, sem Flower)
PROCESSING_MODE=inline

# Ambiente de desenvolvimento
ENVIRONMENT=development

# URL da API que o frontend vai consumir
VITE_API_URL=http://localhost:8000

# ── OPCIONAL (pode deixar vazio agora) ────────────────────────────────────

TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=signalvault-webhook-secret
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_APP_SECRET=
VITE_TELEGRAM_BOT_LINK=
SENTRY_DSN=

# Banco (usado internamente pelo profile internal-db)
POSTGRES_USER=signalvault
POSTGRES_PASSWORD=signalvault
POSTGRES_DB=signalvault
FLOWER_BASIC_AUTH=admin:changeme
JWT_SECRET=signalvault-jwt-secret-change-in-production
FRONTEND_URL=http://localhost:5173
```

Gere os segredos de uma vez:
```bash
python3 -c "import secrets; print('SESSION_SECRET=' + secrets.token_hex(32))"
python3 -c "from cryptography.fernet import Fernet; print('SETTINGS_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

### Passo 3 — Suba os serviços

O flag `--profile internal-db` ativa PostgreSQL e Redis em containers. Sem ele, o docker-compose espera que eles estejam rodando no host.

```bash
docker compose --profile internal-db up -d
```

Esse comando sobe: `db`, `redis`, `backend`, `worker`, `flower`, `frontend`, `landing`.

> Com `PROCESSING_MODE=inline` o `worker` e o `flower` iniciam mas ficam ociosos — não causam problemas, podem ser ignorados.

Aguarde os containers estabilizarem (~30 segundos):
```bash
docker compose ps
```

Todos os serviços devem exibir `Up` ou `healthy`.

### Passo 4 — Execute as migrations do banco

No modo de desenvolvimento, as migrations **não rodam automaticamente**. É preciso executar manualmente:

```bash
docker compose run --rm backend alembic upgrade head
```

Saída esperada:
```
INFO  [alembic.runtime.migration] Running upgrade -> 0001, initial schema
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, add indexes
...
INFO  [alembic.runtime.migration] Running upgrade 0014 -> 0015, add ocr blocks
```

### Passo 5 — Reinicie o backend

Após as migrations, reinicie o backend para que o startup hook crie o usuário owner:

```bash
docker compose restart backend
```

### Passo 6 — Acesse a aplicação

| Serviço | URL | Credenciais |
|---|---|---|
| Frontend (UI) | http://localhost:5173 | senha = valor de `APP_PASSWORD` |
| Backend API | http://localhost:8000 | — |
| API Docs | http://localhost:8000/docs | — |
| Health check | http://localhost:8000/health | — |
| Flower (tasks) | http://localhost:5555 | `admin:changeme` |
| Landing page | http://localhost:5174 | — |

---

## Portas Utilizadas

| Porta | Serviço | Observação |
|---|---|---|
| `5173` | Frontend React (Vite) | Interface principal |
| `5174` | Landing page (Next.js) | Página pública |
| `8000` | Backend FastAPI | API REST + webhooks |
| `5555` | Flower | Monitor de tasks Celery |
| `5432` | PostgreSQL | Interno, não exposto |
| `6379` | Redis | Interno, não exposto |

---

## Verificação de Funcionamento

**1. Health check do backend:**
```bash
curl http://localhost:8000/health
```
Resposta esperada:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "mode": "single_user",
  "db": "ok",
  "redis": "ok"
}
```

**2. Verifique os logs do backend:**
```bash
docker compose logs backend --tail=50
```
Procure por:
```
INFO  Application startup complete
INFO  Bootstrap: owner account created/found
INFO  Admin bootstrap complete
```

**3. Confirme que o banco foi migrado:**
```bash
docker compose exec db psql -U signalvault -d signalvault -c "\dt"
```
Deve listar: `users`, `contents`, `content_embeddings`, `system_settings`, `refresh_tokens`, etc.

**4. Acesse a UI e faça login:**
- Abra http://localhost:5173
- No modo `single_user`, insira o valor de `APP_PASSWORD`
- O dashboard deve carregar sem erros

---

## Variáveis de Ambiente — Referência Completa

### Obrigatórias

| Variável | Propósito | Exemplo |
|---|---|---|
| `OPENAI_API_KEY` | GPT-4o (resumos, tags), Whisper (STT), embeddings | `sk-proj-...` |
| `APP_PASSWORD` | Senha do vault (apenas `single_user`) | `minha-senha` |
| `SESSION_SECRET` | Assina cookies de sessão (apenas `single_user`) | `token_hex(32)` |

### Fortemente Recomendadas

| Variável | Propósito | Default |
|---|---|---|
| `SETTINGS_ENCRYPTION_KEY` | Criptografa segredos no banco (tokens, API keys) | vazio (não criptografado) |
| `APP_MODE` | `single_user` ou `multi_user` | `multi_user` |
| `PROCESSING_MODE` | `inline` (sem Redis) ou `worker` (Celery) | `worker` |
| `ENVIRONMENT` | `development` ou `production` | `development` |

### Banco de Dados

| Variável | Propósito | Default (internal-db) |
|---|---|---|
| `POSTGRES_USER` | Usuário do PostgreSQL | `signalvault` |
| `POSTGRES_PASSWORD` | Senha do PostgreSQL | `signalvault` |
| `POSTGRES_DB` | Nome do banco | `signalvault` |
| `DATABASE_URL` | URL de conexão completa | `postgresql://postgres:password@host.docker.internal:5432/signalvault` |

### Opcionais (bots e integrações)

| Variável | Propósito |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram (pode configurar via UI depois) |
| `TELEGRAM_WEBHOOK_SECRET` | Valida requisições do Telegram |
| `WHATSAPP_VERIFY_TOKEN` | Verificação do webhook Meta |
| `WHATSAPP_ACCESS_TOKEN` | Access token da API WhatsApp Business |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número WhatsApp |
| `WHATSAPP_APP_SECRET` | Valida assinatura HMAC do webhook |
| `VITE_TELEGRAM_BOT_LINK` | Link público do bot (ex: `https://t.me/MeuBot`) |
| `SENTRY_DSN` | Rastreamento de erros (Sentry) |
| `INITIAL_ADMIN_USERNAME` | Username promovido a admin no startup (`multi_user`) |
| `FLOWER_BASIC_AUTH` | Auth do Flower (`user:senha`) |
| `JWT_SECRET` | Segredo JWT (`multi_user`) |
| `FRONTEND_URL` | URL de origem do frontend (CORS) |

---

## Configuração de Banco de Dados

### Inicialização automática

Com `--profile internal-db`, o container PostgreSQL é criado com:
- User: `POSTGRES_USER` (default: `signalvault`)
- Senha: `POSTGRES_PASSWORD` (default: `signalvault`)
- Database: `POSTGRES_DB` (default: `signalvault`)
- Extensão `pgvector` já instalada na imagem `ankane/pgvector:v0.5.1`

### Migrations

```bash
# Rodar todas as migrations (0001 → 0015)
docker compose run --rm backend alembic upgrade head

# Ver migration atual
docker compose run --rm backend alembic current

# Ver histórico
docker compose run --rm backend alembic history
```

### Acessar o banco diretamente

```bash
docker compose exec db psql -U signalvault -d signalvault
```

---

## Execução sem Docker (Opcional)

Útil para debug ou desenvolvimento ativo no backend.

### Backend

```bash
cd apps/backend

# Instale as dependências do sistema (macOS)
brew install tesseract ffmpeg

# Crie um virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Instale as dependências Python
pip install -r requirements.txt

# Configure as variáveis de ambiente
export $(cat ../../.env | grep -v '^#' | xargs)
export DATABASE_URL="postgresql://signalvault:signalvault@localhost:5432/signalvault"
export REDIS_URL="redis://localhost:6379/0"

# Rode as migrations
alembic upgrade head

# Inicie o servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd apps/frontend

npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

### Worker Celery (opcional, apenas se `PROCESSING_MODE=worker`)

```bash
cd apps/backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info -Q processing,default
```

---

## O que Pode ser Desativado (Simplificação)

| Componente | Como desativar | Impacto |
|---|---|---|
| Redis + Worker + Flower | `PROCESSING_MODE=inline` no `.env` | Tasks processadas de forma síncrona. Mais lento, sem parallelismo, mas funcional. |
| Telegram Bot | Não configurar `TELEGRAM_BOT_TOKEN` | Não recebe mensagens via Telegram |
| WhatsApp Bot | Não configurar `WHATSAPP_*` | Não recebe mensagens via WhatsApp |
| Landing page | Remover o serviço `landing` do compose | Apenas suprime a página de marketing |
| Flower | Remover o serviço `flower` do compose | Sem monitor de tasks |
| Sentry | Não configurar `SENTRY_DSN` | Sem rastreamento de erros |

**Setup absolutamente mínimo:** apenas `OPENAI_API_KEY`, `APP_MODE=single_user`, `APP_PASSWORD`, `SESSION_SECRET`, e `PROCESSING_MODE=inline`.

---

## Problemas Comuns

### `alembic upgrade head` falha com "connection refused"

O banco ainda não está pronto. Aguarde o healthcheck passar:
```bash
docker compose ps  # Confirme que keepiu-db está "healthy"
docker compose run --rm backend alembic upgrade head
```

### Frontend exibe "Network Error" ou 502

O `VITE_API_URL` está errado. Confirme:
```bash
curl http://localhost:8000/health
```
Se falhar, verifique os logs:
```bash
docker compose logs backend --tail=30
```

### Backend falha com "SETTINGS_ENCRYPTION_KEY not set"

Em desenvolvimento, gera apenas um warning. Para suprimir, gere e adicione ao `.env`:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `host.docker.internal` não resolve (Linux)

No Linux, não é resolvido automaticamente. Use `--profile internal-db`, ou adicione ao `/etc/hosts`:
```bash
echo "172.17.0.1 host.docker.internal" | sudo tee -a /etc/hosts
```

### Migrations rodam mas o usuário owner não é criado

O usuário owner é criado no startup do backend, não nas migrations. Após rodar `alembic upgrade head`, reinicie:
```bash
docker compose restart backend
docker compose logs backend | grep -i "bootstrap\|owner\|startup"
```

### Porta 5173 ou 8000 já em uso

```bash
lsof -i :5173
lsof -i :8000
# Ou mude a porta no docker-compose.yml: "8001:8000"
```

### Build do backend demora muito

A imagem inclui Tesseract, ffmpeg e Chromium (Playwright). Na primeira build, são esperados 3–5 minutos. Nas subsequentes, usa cache.

### Embeddings falham (pgvector)

Certifique-se de estar usando a imagem `ankane/pgvector:v0.5.1` e não um PostgreSQL padrão. O `--profile internal-db` garante isso automaticamente.

---

## Checklist de Setup

```
[ ] Docker e Docker Compose instalados
[ ] Repositório clonado
[ ] .env criado a partir do .env.example
[ ] OPENAI_API_KEY preenchida
[ ] APP_MODE=single_user configurado
[ ] APP_PASSWORD definida
[ ] SESSION_SECRET gerado (token_hex(32))
[ ] PROCESSING_MODE=inline (modo simples) ou worker (com Redis)
[ ] docker compose --profile internal-db up -d executado
[ ] docker compose ps — todos os serviços Up/healthy
[ ] docker compose run --rm backend alembic upgrade head executado
[ ] docker compose restart backend executado
[ ] GET http://localhost:8000/health retorna {"status":"healthy"}
[ ] http://localhost:5173 carrega e aceita login com APP_PASSWORD
```

---

## Resumo dos Comandos

```bash
# Setup completo do zero
git clone <repo> keepiu && cd keepiu
cp .env.example .env
# edite o .env com OPENAI_API_KEY, APP_PASSWORD, SESSION_SECRET

docker compose --profile internal-db up -d
docker compose run --rm backend alembic upgrade head
docker compose restart backend

# Verificação
curl http://localhost:8000/health
open http://localhost:5173
```
