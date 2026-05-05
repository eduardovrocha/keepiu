# SignalVault — Diagnóstico SaaS + Plano de Transformação

> Elaborado em 2026-05-04. Arquiteto: Claude Sonnet 4.6.

---

## 1. DIAGNÓSTICO ATUAL

### O que funciona bem

O core do produto é sólido. O pipeline de ingestão → fila → IA → embedding → busca está implementado de ponta a ponta. A arquitetura de domínios (services, schemas, normalizers) está bem separada. A base de dados já suporta múltiplos canais (`ingestion_channel`), múltiplas identidades de usuário (`telegram_id`, `whatsapp_phone`, `username`) e isolamento por `user_id`. Plans e quotas existem no schema.

### Problemas críticos reais (não genéricos)

**1. Usuários WhatsApp não têm acesso ao dashboard**
`get_or_create_whatsapp(phone, name)` cria o registro mas não emite tokens. Não existe fluxo de autenticação para esses usuários chegarem ao frontend. A conta existe; a porta está trancada.

**2. Webhook bypass de quota**
`_ingest()` em `webhooks.py` chama `content_service.create()` diretamente sem passar por `check_quota()`. O limite de 100 itens/mês do plano free não se aplica a mensagens WhatsApp ou Telegram. Qualquer usuário pode enviar ilimitadamente via bot.

**3. Assinatura HMAC do WhatsApp é opcional**
```python
if app_secret:  # se não configurado, aceita qualquer POST
    sig = hmac.new(...)
```
Sem `WHATSAPP_APP_SECRET`, o endpoint `/webhooks/whatsapp` aceita requisições de qualquer origem. Blocker de segurança para produção.

**4. Sem OTP / auth alternativa**
O único fluxo de login é `username + password`. Para SaaS WhatsApp-first isso é uma contradição: o usuário envia conteúdo via WhatsApp mas precisa criar conta manualmente para ver no dashboard.

**5. Sem billing real**
`Plan` e `UserQuota` existem no schema mas não há integração de pagamento. O plano `pro` está no banco sem forma de um usuário ativá-lo.

**6. Rate limiting por IP, não por usuário**
`slowapi` com `get_remote_address` não protege contra abuso autenticado. Um usuário pode fazer 1000 chamadas de IPs diferentes.

**7. Secrets podem estar em plaintext**
`SETTINGS_ENCRYPTION_KEY` é opcional (`str = ""`). Se não configurado, `whatsapp_access_token`, `openai_api_key` etc. ficam em texto plano no banco.

---

## 2. LISTA DE FUNCIONALIDADES (estado real)

### Ingestão

| Feature | Estado | Canal |
|---|---|---|
| Telegram text/link | ✅ Produção | Telegram webhook |
| Telegram image (OCR) | ✅ Produção | Telegram webhook |
| WhatsApp text/link | ✅ Produção | WhatsApp webhook |
| WhatsApp image (OCR) | ✅ Produção | WhatsApp webhook + Celery |
| Instagram post capture | ✅ Produção | Browser automation |
| Web UI submit (link) | ✅ Produção | `POST /contents` |
| Deduplicação por URL | ✅ Produção | `get_by_url()` antes de criar |

### Processamento

| Feature | Estado | Detalhe |
|---|---|---|
| OCR (Tesseract) | ✅ | Imagens Telegram + WhatsApp |
| IA: título, resumo, tags | ✅ | GPT-4o-mini |
| IA: categoria, score, actionable | ✅ | GPT-4o-mini |
| IA: Instagram (tone, niche, CTA, sentiment) | ✅ | Pipeline separado |
| Embeddings (1536d) | ✅ | text-embedding-3-small |
| Retry com backoff | ✅ | max_retries=3 |
| Stage tracking granular | ✅ | queued→capturing→ocr→ai→finalizing |

### Armazenamento

| Feature | Estado |
|---|---|
| PostgreSQL + pgvector | ✅ |
| Isolamento por user_id | ✅ (query level) |
| Retenção configurável | ✅ (`CONTENT_RETENTION_DAYS`) |
| Embeddings separados | ✅ (`content_embeddings`) |

### Recuperação

| Feature | Estado |
|---|---|
| Busca semântica (pgvector) | ✅ |
| Filtros (categoria, tipo, canal, plataforma) | ✅ |
| Dashboard com stats | ✅ |
| Workers monitor (Flower + custom) | ✅ |

### Auth / Identidade

| Feature | Estado |
|---|---|
| Username + password | ✅ |
| httpOnly cookies (access + refresh) | ✅ |
| Refresh token rotation | ✅ |
| Admin bootstrap | ✅ |
| OTP via WhatsApp | ❌ Não existe |
| Login via Telegram | ❌ Não existe |

### Billing

| Feature | Estado |
|---|---|
| Modelo de plans no banco | ✅ (estrutura) |
| Quota enforcement (API) | ✅ |
| Quota enforcement (webhook) | ❌ Bug |
| Pagamento / Stripe | ❌ Não existe |
| Upgrade de plano | ❌ Não existe |

---

## 3. GAPS PARA SAAS

### Gap 1 — Autenticação WhatsApp-first (Blocker crítico)

**Situação**: Usuário envia mensagem WhatsApp → conta criada via `get_or_create_whatsapp()` → sem password, sem tokens → não consegue acessar o dashboard.

**O que falta**:
- Modelo `OTPToken` (phone, code_hash, expires_at, used, created_at)
- `POST /auth/request-otp` → gera código 6 dígitos → envia via WhatsApp → salva hash
- `POST /auth/verify-otp` → valida código → `get_or_create_whatsapp()` → emite access + refresh tokens
- Frontend: tela de "Entrar com WhatsApp" antes da tela de senha

### Gap 2 — Quota não aplicada no webhook (Bug de receita)

**Situação**: `webhooks.py/_ingest()` → `content_service.create()` diretamente.

**O que falta**:
```python
# webhooks.py _ingest() — adicionar antes do create:
content_service = ContentService(db)
allowed, quota_info = content_service.check_quota(user.id)
if not allowed:
    await wa.send_text(to=normalized.external_user_id,
                       text="⚠️ Limite do plano atingido. Faça upgrade em: ...")
    return {"ok": True, "quota_exceeded": True}
```

### Gap 3 — Billing (Blocker de monetização)

**Situação**: `Plan.price_cents` existe mas não há forma de cobrar.

**O que falta**:
- Integração Stripe: Customer, Subscription, Webhook
- Modelo `Subscription` linkando user → stripe_subscription_id → plan
- `POST /billing/portal` (Stripe Customer Portal para gerenciar)
- Webhook `POST /billing/stripe` para atualizar plano automaticamente
- Lógica de downgrade gracioso (conteúdo existente preservado, novos bloqueados)

### Gap 4 — Onboarding sem fricção

**Situação**: Para usar o produto hoje, o usuário precisa:
1. Criar conta manualmente no dashboard
2. Configurar tokens no `.env` (só admin)
3. Procurar o bot no Telegram

**O que falta**: fluxo onde o usuário só precisa do número de telefone.

### Gap 5 — Bot sem interface de comando

**Situação**: Qualquer texto enviado ao bot é tratado como conteúdo. Não há `/status`, `/search`, `/help`.

**O que falta**: dispatcher de comandos no normalizer antes de criar conteúdo.

### Gap 6 — Observabilidade insuficiente

**Situação**: Sentry opcional, task metrics existem, mas sem user context nos logs, sem latência por endpoint, sem alertas.

**O que falta**:
- Middleware de request logging com `user_id`, `duration_ms`, `status_code`
- Sentry `set_user()` no middleware de auth
- Alertas básicos (taxa de erro > 5% em 5 min)

---

## 4. ARQUITETURA PROPOSTA

```
                     ┌─────────────────────────────────┐
                     │         META CLOUD API           │
                     └──────────────┬──────────────────┘
                                    │ HMAC-SHA256 validado
                     ┌──────────────▼──────────────────┐
                     │    POST /webhooks/whatsapp       │
                     │    (rate limit: 60/min global)   │
                     └──────────────┬──────────────────┘
                                    │
                     ┌──────────────▼──────────────────┐
                     │       CommandDispatcher          │
                     │  /start /status /help → reply    │
                     │  conteúdo normal → _ingest()     │
                     └──────────────┬──────────────────┘
                                    │
                     ┌──────────────▼──────────────────┐
                     │         _ingest()                │
                     │  1. get_or_create_whatsapp()     │
                     │  2. check_quota() → 429 via WA   │
                     │  3. detect_source() / dedup URL  │
                     │  4. content_service.create()     │
                     │  5. enqueue (default|processing) │
                     └──────────────┬──────────────────┘
                                    │
              ┌─────────────────────▼────────────────────┐
              │           CELERY WORKERS                   │
              │  Queue: default → process_content_task     │
              │  Queue: processing → image/instagram tasks │
              └─────────────────────┬────────────────────┘
                                    │
              ┌─────────────────────▼────────────────────┐
              │           AI PIPELINE                      │
              │  capture → OCR → GPT-4o-mini → embed      │
              └─────────────────────┬────────────────────┘
                                    │
              ┌─────────────────────▼────────────────────┐
              │         PostgreSQL + pgvector              │
              │  contents + content_embeddings             │
              └─────────────────────┬────────────────────┘
                                    │
              ┌─────────────────────▼────────────────────┐
              │        React Dashboard                     │
              │  Auth via OTP WhatsApp → httpOnly cookie   │
              │  Busca semântica, library, processing view  │
              └───────────────────────────────────────────┘
```

---

## 5. ONBOARDING WHATSAPP (DETALHADO)

### Fluxo completo

```
Usuário abre link de onboarding
        ↓
Frontend: /start?phone=
  Input: número de telefone
        ↓
POST /auth/request-otp
  { phone: "+5511999999999" }
        ↓
Backend:
  1. Normaliza phone (E.164)
  2. Verifica se já existe User com whatsapp_phone
  3. Gera OTP: secrets.token_hex(3) → "a3f9b2" → 6 chars hex → display como "492618"
  4. Salva OTPToken(phone_hash, code_hash, expires_at=+10min)
  5. WhatsAppService.send_text(phone, "Seu código: 492618")
  Response: { "sent": true, "expires_in": 600 }
        ↓
Frontend: tela de input do código
  Input: 6 dígitos
        ↓
POST /auth/verify-otp
  { phone: "+5511999999999", code: "492618" }
        ↓
Backend:
  1. Verifica rate limit: 5 tentativas por phone por 15min
  2. Busca OTPToken por phone_hash não expirado e não usado
  3. Compara code_hash (bcrypt ou hmac)
  4. Marca OTP como usado
  5. get_or_create_whatsapp(phone, name="")
  6. _issue_tokens(response, user, db)
  Response: { "authenticated": true, "is_new_user": true }
        ↓
Frontend: redireciona para /dashboard
  Se is_new_user: mostra welcome screen com instrução de enviar mensagem
```

### Modelo OTPToken

```python
class OTPToken(Base):
    __tablename__ = "otp_tokens"
    id         = Column(UUID, primary_key=True, default=uuid.uuid4)
    phone_hash = Column(String(64), nullable=False, index=True)   # sha256(phone)
    code_hash  = Column(String(64), nullable=False)                # sha256(code)
    expires_at = Column(DateTime, nullable=False)
    used       = Column(Boolean, default=False, nullable=False)
    attempts   = Column(Integer, default=0, nullable=False)        # brute force guard
    created_at = Column(DateTime, default=datetime.utcnow)
```

Não armazenar phone em texto — apenas hash. Não armazenar code em texto — apenas hash. O rate limit de 5 tentativas fica no campo `attempts` + check no backend antes de validar.

### Endpoints novos

```
POST /auth/request-otp   rate: 3/min por IP, 5/hora por phone_hash
POST /auth/verify-otp    rate: 5 tentativas por OTP antes de invalidar
```

### Frontend: tela de onboarding

```
/login → dois tabs:
  [Continuar com WhatsApp]  [Entrar com senha]

Tab WhatsApp:
  Step 1: Input phone → "Enviar código"
  Step 2: Input 6 dígitos → "Verificar"
  → Redirect /dashboard com welcome modal se is_new_user
```

---

## 6. MODELO DE DADOS NOVO

### User (mudanças mínimas — já está bom)

```sql
users
  id                UUID       PK
  phone             VARCHAR(20) UNIQUE NULL   -- E.164, novo campo preferencial
  whatsapp_phone    VARCHAR(30) UNIQUE NULL   -- manter para compatibilidade
  telegram_id       BIGINT      UNIQUE NULL   -- manter
  username          VARCHAR(100) UNIQUE NULL  -- manter para admin
  email             VARCHAR(255) UNIQUE NULL
  hashed_password   VARCHAR(255) NULL
  name              VARCHAR(255) NULL
  is_admin          BOOLEAN     DEFAULT FALSE
  created_at        TIMESTAMP
```

Migração: adicionar coluna `phone VARCHAR(20) UNIQUE` e popular a partir de `whatsapp_phone` (reformatando para E.164). `whatsapp_phone` pode ser deprecado gradualmente.

### OTPToken (novo)

```sql
otp_tokens
  id          UUID       PK
  phone_hash  VARCHAR(64) NOT NULL INDEX  -- sha256(E.164 phone)
  code_hash   VARCHAR(64) NOT NULL
  expires_at  TIMESTAMP  NOT NULL
  used        BOOLEAN    DEFAULT FALSE
  attempts    SMALLINT   DEFAULT 0
  created_at  TIMESTAMP
```

### Subscription (novo — billing)

```sql
subscriptions
  id                     UUID PK
  user_id                UUID FK → users.id ON DELETE CASCADE
  stripe_customer_id     VARCHAR(255) UNIQUE NOT NULL
  stripe_subscription_id VARCHAR(255) UNIQUE NULL
  plan_id                UUID FK → plans.id
  status                 VARCHAR(50)  -- active|past_due|canceled|trialing
  current_period_end     TIMESTAMP NULL
  cancel_at_period_end   BOOLEAN DEFAULT FALSE
  created_at             TIMESTAMP
  updated_at             TIMESTAMP
```

### Plan (sem mudança estrutural — adicionar campos)

```sql
plans  -- adicionar:
  stripe_price_id        VARCHAR(255) UNIQUE NULL  -- ID do price no Stripe
  trial_days             SMALLINT DEFAULT 0
  max_search_per_day     INTEGER NULL              -- limite de buscas semânticas
  max_storage_mb         INTEGER NULL              -- limite de storage (futuro)
```

### WA Bot Session (novo — estado do bot por usuário)

```sql
wa_bot_sessions
  phone         VARCHAR(20) PK          -- E.164
  state         VARCHAR(50) DEFAULT 'idle'  -- idle|awaiting_otp|onboarding
  context       JSONB       DEFAULT '{}'
  updated_at    TIMESTAMP
```

Permite ao bot manter estado mínimo por conversa sem overhead de memória externa.

---

## 7. MUDANÇAS TÉCNICAS NECESSÁRIAS

### 7.1 Backend — Correções imediatas

**Fix 1: Quota no webhook** (`apps/backend/app/api/webhooks.py`)

```python
async def _ingest(normalized: NormalizedMessage, db: Session) -> dict:
    # ... user lookup ...

    content_service = ContentService(db)
    allowed, quota_info = content_service.check_quota(user.id)
    if not allowed:
        if channel == "whatsapp":
            await WhatsAppService(db).send_text(
                normalized.external_user_id,
                "⚠️ Você atingiu o limite do seu plano. "
                "Faça upgrade para continuar: https://app.signalvault.io/upgrade"
            )
        return {"ok": True, "quota_exceeded": True, **quota_info}

    content = content_service.create(content_data)
    content_service.increment_quota(user.id)
    # ...
```

**Fix 2: HMAC obrigatório em produção** (`config.py`)

```python
WHATSAPP_APP_SECRET_REQUIRED: bool = False  # True em produção
```

No webhook:
```python
if not app_secret and settings.WHATSAPP_APP_SECRET_REQUIRED:
    raise HTTPException(503, "WhatsApp not fully configured")
```

**Fix 3: Rate limiting por usuário autenticado** (`search.py`)

```python
def get_user_or_ip(request: Request) -> str:
    token = request.cookies.get("access_token")
    if token:
        payload = verify_token(token)
        if payload:
            return f"user:{payload['sub']}"
    return get_remote_address(request)
```

### 7.2 Novos endpoints

```
POST /auth/request-otp      → gera e envia OTP via WhatsApp
POST /auth/verify-otp       → valida OTP → issue tokens
POST /billing/portal        → Stripe Customer Portal URL
POST /billing/stripe        → Stripe webhook (plan sync)
GET  /me/quota              → quota atual do usuário logado
POST /auth/link-whatsapp    → vincula phone a conta existente (username/password)
```

### 7.3 CommandDispatcher WhatsApp

```python
# app/services/ingestion/whatsapp_dispatcher.py

COMMANDS = {
    "/start":  handle_start,
    "/help":   handle_help,
    "/status": handle_status,
    "/search": handle_search,
    "/plano":  handle_plan,
}

async def dispatch(normalized: NormalizedMessage, db: Session) -> bool:
    """Returns True if was a command (skip content creation)."""
    text = (normalized.text or "").strip()
    if not text.startswith("/"):
        return False

    command = text.split()[0].lower()
    handler = COMMANDS.get(command)
    if handler:
        await handler(normalized, db)
        return True
    return False
```

Respostas dos comandos via `WhatsAppService.send_text()`:
- `/start` → mensagem de boas vindas + link do dashboard
- `/status` → "📊 Você tem X itens processados este mês. Plano: Free (Y restantes)."
- `/search texto` → busca semântica top-3 e retorna resumos
- `/plano` → plano atual + link de upgrade

### 7.4 BillingService

```python
class BillingService:
    def create_customer(user: User) -> str:
        """Create Stripe customer, return stripe_customer_id."""

    def create_checkout_session(user_id, plan_name, success_url, cancel_url) -> str:
        """Create Stripe Checkout session, return URL."""

    def create_portal_session(stripe_customer_id, return_url) -> str:
        """Create Stripe Customer Portal session."""

    def handle_webhook(event_type, event_data) -> None:
        """Sync plan from Stripe events:
           customer.subscription.created → activate plan
           customer.subscription.updated → update plan
           customer.subscription.deleted → downgrade to free
           invoice.payment_failed → notify user via WhatsApp
        """

    def get_user_subscription(user_id) -> Subscription | None:
        """Current subscription with plan details."""
```

### 7.5 Middleware de observabilidade

```python
# app/middleware/logging.py
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)

    user_id = getattr(request.state, "user_id", None)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=str(user_id) if user_id else None,
    )
    return response
```

### 7.6 Frontend — mudanças

**Login page**: adicionar tab "WhatsApp" com fluxo de 2 steps (phone → código).

**Me/quota endpoint**: banner no dashboard mostrando uso:
```
📊 47/100 itens usados este mês — Plano Free
[Fazer upgrade para Pro]
```

**Upgrade page** (`/upgrade`): mostra planos, redireciona para Stripe Checkout.

**Welcome modal**: ao detectar `is_new_user=true` após OTP, mostrar instrução de enviar primeira mensagem.

---

## 8. ROADMAP DE IMPLEMENTAÇÃO

### Fase 1 — Foundation (2–3 semanas)
**Objetivo**: usuário consegue criar conta e acessar dashboard só com WhatsApp.

| Tarefa | Arquivo(s) | Critério de aceite |
|---|---|---|
| Modelo OTPToken + migração 0013 | `models/otp_token.py` + migration | tabela criada |
| `POST /auth/request-otp` | `api/auth.py` | OTP enviado via WhatsApp |
| `POST /auth/verify-otp` | `api/auth.py` | token emitido, user criado |
| Login WhatsApp no frontend | `pages/Login.tsx` | fluxo 2-step funcionando |
| Fix quota no webhook | `api/webhooks.py` | WhatsApp bloqueado em 100 itens |
| HMAC obrigatório em staging | `config.py` + `webhooks.py` | POST sem assinatura → 401 |
| Ativar `SETTINGS_ENCRYPTION_KEY` | `.env` + docs | secrets criptografados no banco |

### Fase 2 — Pipeline hardening (1–2 semanas)
**Objetivo**: pipeline WhatsApp robusto e com feedback ao usuário.

| Tarefa | Arquivo(s) | Critério de aceite |
|---|---|---|
| CommandDispatcher WhatsApp | `services/ingestion/whatsapp_dispatcher.py` | `/status`, `/help` respondem |
| `/status` command → quota info | dispatcher | mensagem com uso/mês |
| Notificação de processamento concluído | `workers/content_processor.py` | WA message ao terminar |
| Rate limit por usuário em `/search` | `api/search.py` | 30/min por user_id |
| Retry de OTP com backoff | `api/auth.py` | brute force bloqueado em 5 tentativas |
| Limpeza de OTPs expirados (beat) | `workers/cleanup_tasks.py` | tarefa diária |

### Fase 3 — SaaS Core (3–4 semanas)
**Objetivo**: produto monetizável.

| Tarefa | Arquivo(s) | Critério de aceite |
|---|---|---|
| Modelo Subscription + migração 0014 | `models/subscription.py` | tabela criada |
| BillingService + Stripe SDK | `services/billing_service.py` | customer criado no Stripe |
| `POST /billing/stripe` webhook | `api/billing.py` | plan sync automático |
| `POST /billing/portal` | `api/billing.py` | redirect para Stripe Portal |
| Página /upgrade no frontend | `pages/Upgrade.tsx` | checkout abre |
| Banner de quota no dashboard | `pages/Dashboard.tsx` | uso/mês visível |
| `GET /me/quota` endpoint | `api/auth.py` | dados de consumo |
| Notificação WhatsApp no payment_failed | `services/billing_service.py` | WA message enviada |
| Downgrade gracioso | `services/billing_service.py` | conteúdo preservado, novos bloqueados |

### Fase 4 — UX & Scale (2–3 semanas)
**Objetivo**: experiência polida e base para crescimento.

| Tarefa | Arquivo(s) | Critério de aceite |
|---|---|---|
| Welcome modal para novos usuários | `pages/Dashboard.tsx` | aparece apenas uma vez |
| Middleware de request logging | `middleware/logging.py` | logs com user_id + duration |
| Sentry com user context | `main.py` | erros tagueados por usuário |
| WebSocket para status em tempo real | `api/ws.py` | Processing view sem polling |
| `/search` via WhatsApp command | dispatcher | top-3 resultados no bot |
| `link-whatsapp` para usuários existentes | `api/auth.py` | usuários antigos vinculam WhatsApp |
| Página de onboarding guiado | `pages/Onboarding.tsx` | passo a passo após cadastro |

---

## 9. RISCOS E TRADE-OFFS

### Risco 1 — API da Meta (alto impacto)
A Cloud API do WhatsApp requer número de telefone verificado, conta Business Manager aprovada e HTTPS público. Em desenvolvimento, você precisa de `ngrok` ou similar. O processo de aprovação da Meta pode levar dias. **Mitigação**: usar número de teste da Meta durante desenvolvimento; ter fallback via Telegram para beta.

### Risco 2 — OTP via WhatsApp = custo por mensagem (médio)
Cada `request-otp` gasta uma mensagem na API da Meta (conversas de autenticação têm pricing próprio). Com volume alto de cadastros, o custo pode surpreender. **Mitigação**: rate limit agressivo (3 OTPs por hora por phone), cache de OTP não usado (reenviar mesmo código se < 2min).

### Risco 3 — Stripe + plano free = churn sem conversão (médio)
Plano free generoso (100/mês) pode resultar em muitos usuários que nunca pagam. **Trade-off**: free muito restrito → alta fricção no onboarding; free generoso → difícil converter. **Decisão recomendada**: free com 30 itens/mês (não 100), trial pro de 14 dias no cadastro. Atualizar migration 0012.

### Risco 4 — Isolamento multi-tenant apenas no ORM (baixo-médio)
O isolamento atual é `WHERE user_id = :id` em todas as queries. Se houver SQL injection ou bug de lógica, dados vazam entre usuários. **Mitigação curto prazo**: auditoria de todos os endpoints para garantir `user_id` sempre filtrado. **Mitigação longo prazo**: Row-Level Security no PostgreSQL (adicionar policies por `app.current_user_id`).

### Risco 5 — WhatsApp como único canal de auth (médio)
Se a conta Meta for suspensa ou o número bloqueado, usuários perdem acesso ao produto. **Mitigação**: após primeiro login, oferecer configuração de senha opcional. Guardar email opcionalmente. Manter fallback de login por senha para usuários que configuraram.

### Risco 6 — Custo de IA não controlado por usuário (alto)
Atualmente cada item consome GPT-4o-mini + embedding independente do plano. Um usuário free com 100 itens/mês de imagens grandes pode custar mais do que um pro. **Mitigação**: `max_tokens` agressivo para resumos (500 tokens output); cache de embeddings para URLs duplicadas entre usuários diferentes; considerar modelo menor para plano free.

### Trade-off — OTP vs Magic Link
OTP (6 dígitos) é mais familiar para mobile mas tem risco de brute force. Magic link (link no WhatsApp) é mais seguro mas o usuário precisa abrir no mesmo dispositivo onde clicou. **Recomendação**: OTP para MVP (mais simples de implementar e testar); magic link como melhoria na Fase 4.

### Trade-off — WebSocket vs polling
O frontend atual usa polling para status de processamento. WebSocket é mais elegante mas adiciona complexidade (conexões persistentes, Redis Pub/Sub para notificar workers → API). Para o MVP, polling com intervalo de 3s é suficiente. WebSocket entra na Fase 4 quando escala exigir.

---

**Resumo executivo**: o produto tem um core técnico sólido. Os três desbloqueadores para SaaS são, em ordem de prioridade: **(1) OTP WhatsApp para autenticação** (sem isso o canal principal não gera usuários no dashboard), **(2) fix do bypass de quota no webhook** (sem isso não há billing real), **(3) Stripe integration** (sem isso não há receita). Tudo mais é melhoria incremental.
