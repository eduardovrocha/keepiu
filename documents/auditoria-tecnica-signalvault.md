# Auditoria Técnica — SignalVault
*Data: 2026-05-04 | Escopo: codebase completo | Perspectiva: vault pessoal em VPS + uso diário via bot*

---

## 1. Sumário Executivo

**Score geral: 5.5 / 10**
**Status: Protótipo avançado — não está pronto para uso pessoal real sem correções**

O sistema tem uma base arquitetural sólida (FastAPI + Celery + pgvector) e implementou corretamente vários componentes críticos (webhook HMAC, refresh tokens, Fernet para segredos, pipeline de stages). Mas carrega peso de SaaS (quotas, planos, multi-tenant) que conflita com a direção single-user, tem bugs que quebram funcionalidades recém-implementadas, e não possui nenhum teste.

**Principais riscos:**

| Risco | Gravidade |
|---|---|
| Modo `inline` quebrado — tasks com `bind=True` crasham | CRITICAL |
| Autenticação some no F5 — sem persistência de estado | HIGH |
| Setup pgvector em cada conexão do pool | HIGH |
| Nenhum teste automatizado | HIGH |
| Registro aberto no modo single_user | HIGH |
| Dashboard: 7 COUNT queries a cada 30s | MEDIUM |

---

## 2. Falhas Críticas

### 1. `PROCESSING_MODE=inline` está quebrado

**Arquivo:** `apps/backend/app/core/processing.py:33`

```python
def _run_inline(celery_task: Any, *args: Any, **kwargs: Any) -> None:
    celery_task.run(*args, **kwargs)  # ← BUG
```

Todos os tasks usam `@shared_task(bind=True, ...)`. Com `bind=True`, o Celery injeta `self` (a instância do task) como primeiro argumento. Chamar `.run()` diretamente bypassa esse mecanismo — o parâmetro `self` não é injetado e o call falha com `TypeError: process_content_task() missing 1 required positional argument: 'content_id'`.

**Como corrigir:**
```python
# Opção 1: chamar o task como callable (Celery injeta self automaticamente)
celery_task(*args, **kwargs)

# Opção 2: usar __wrapped__ que é a função nua, passando self mock
```
A opção 1 é a correta para manter o comportamento idêntico ao worker.

---

### 2. `content_batch.py` e `instagram.py` ignoram `route_task`

**Arquivos:**
- `apps/backend/app/api/content_batch.py:36` — `process_instagram_task.delay(...)`
- `apps/backend/app/api/instagram.py:29` — `process_instagram_task.delay(...)`

Esses dois endpoints foram esquecidos na migração para `route_task`. Em modo `inline`, processar via Instagram Batch ou via endpoint Instagram sempre vai para o Celery — o modo inline não funciona para esses paths.

**Como corrigir:** substituir `.delay(...)` por `route_task(process_instagram_task, ...)` nos dois arquivos.

---

### 3. Autenticação desaparece no F5

**Arquivo:** `apps/frontend/src/store/authStore.ts`

```typescript
export const useAuthStore = create<AuthState>()((set) => ({
  isAuthenticated: false,  // ← sempre começa falso
  isAdmin: false,
  ...
}))
```

O Zustand store não usa `persist` middleware. Em cada reload da página, `isAuthenticated=false`. Se o `App.tsx` não faz um `/auth/me` no mount, o usuário vê a tela de login toda vez que recarrega a página — mesmo tendo um cookie de sessão válido.

**Impacto real:** O interceptor em `api.ts` faz refresh automaticamente em 401, mas isso só funciona se o React já tentou uma chamada autenticada. Se o App não re-hidrata o estado de auth no mount, o usuário é sempre redirecionado ao login.

**Como corrigir:**
```typescript
// authStore.ts — adicionar persist
import { persist } from 'zustand/middleware'

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({ ... }),
    { name: 'auth-state', partialize: (s) => ({ isAuthenticated: s.isAuthenticated, isAdmin: s.isAdmin }) }
  )
)
```
Ou: fazer `GET /auth/me` no mount do App e atualizar o store.

---

### 4. Lógica de senha no modo single_user é confusa e frágil

**Arquivo:** `apps/backend/app/api/auth.py:148`

```python
if not verify_password(body.password, settings.APP_PASSWORD) and body.password != settings.APP_PASSWORD:
```

`verify_password()` espera um hash bcrypt no segundo argumento. `APP_PASSWORD` é texto plano (variável de ambiente). O `verify_password` sempre retorna `False`, então a autenticação cai no `and body.password != settings.APP_PASSWORD` — comparação de strings em texto plano. O código funciona por acidente.

**Problema adicional:** Comparação de strings em texto plano é vulnerável a timing attacks. Use `secrets.compare_digest()`.

**Como corrigir:**
```python
import secrets
if not secrets.compare_digest(body.password, settings.APP_PASSWORD):
    raise HTTPException(...)
```

---

### 5. `setup_pgvector` executa em cada conexão do pool

**Arquivo:** `apps/backend/app/core/database.py:19`

```python
@event.listens_for(engine, "connect")
def setup_pgvector(dbapi_conn, connection_record):
    with dbapi_conn.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        dbapi_conn.commit()
```

Isso executa um DDL `CREATE EXTENSION` a cada vez que uma conexão é retirada do pool. O SQLAlchemy com `pool_recycle=300` reconecta a cada 5 minutos. Num worker Celery com concorrência 2, isso é 2 conexões ativas mais reconexões periódicas — cada uma executa `CREATE EXTENSION`. Além de ineficiente, essa operação requer permissão de superuser ou `pg_extension_owner` — e pode falhar silenciosamente em alguns ambientes.

**Como corrigir:** Mover para a migration Alembic ou para o evento `first_connect` (dispara uma vez por processo):
```python
@event.listens_for(engine, "first_connect")
def setup_pgvector(dbapi_conn, connection_record):
    ...
```

---

## 3. Problemas por Área

### Arquitetura

**Quota/Planos no modo single_user — peso morto:**
- `Plan`, `UserQuota` são modelos SaaS com colunas `max_contents_per_month`, `max_total_contents`
- `ContentService._get_or_create_quota()` é chamado a cada content criado via API Web
- Mas os webhooks (ingestão real) **não chamam** `increment_quota()` — o tracking de quota é inconsistente por design
- Para single_user isso é complexidade zero-valor

**Anti-pattern: `ensure_defaults()` em cada leitura:**
- `SettingsService.get_all()` chama `ensure_defaults()` que faz `INSERT` para cada chave ausente
- Isso é uma escrita (com `try/commit/rollback`) em toda requisição de leitura das configurações
- Deveria ser executado uma vez no startup em `main.py`

**Duplicação no Content model:**
- `status` (queued/processing/completed/failed) e `processed` (boolean) são redundantes
- `status == "completed"` ↔ `processed == True`
- `processing_stage` repete parte da semântica do `status`
- Três campos para descrever o mesmo estado cria inconsistências (`mark_failed` seta `processed=True` mas status=failed)

**Ingestão via webhook não rastreia quota:**
```python
# webhooks.py _ingest() — sem chamada a increment_quota
content = content_service.create(content_data)
# quota.contents_this_month nunca incrementa via bot
```
Quota tracking só funciona para conteúdo criado pela UI web.

---

### Segurança

| Severidade | Problema | Local |
|---|---|---|
| HIGH | `POST /settings/reveal` retorna TODOS os secrets de uma vez sem re-autenticação | `api/settings.py:54` |
| HIGH | Registro (`/auth/register`) está aberto por padrão em single_user — qualquer pessoa que descubra a URL pode criar conta | `config.py:ALLOW_REGISTRATION=True` |
| HIGH | `APP_PASSWORD` armazenado em plaintext no env — comparado com `!=` (timing attack) | `auth.py:148` |
| MEDIUM | Tokens de reset de senha são logados em plaintext na URL: `reset_url = f"...?token={raw_token}"` — se logs vazarem, tokens são expostos | `auth.py:259` |
| MEDIUM | Rate limit de login é por IP (`get_remote_address`) — atrás de reverse proxy sem `X-Forwarded-For` configurado, todos os IPs aparecem como o proxy | `auth.py:23` |
| MEDIUM | Inline mode sem isolamento — tasks rodam no mesmo processo do servidor web via ThreadPoolExecutor; uma task bloqueante trava workers do uvicorn | `core/processing.py` |
| LOW | `decrypt_setting` retorna o valor raw em caso de `InvalidToken` — silencia erros de chave errada sem aviso | `core/security.py:71` |
| LOW | HMAC da sessão usa SHA-256 mas não inclui expiração no token — um token de sessão válido dura 30 dias fixos sem opção de invalidação individual | `core/session.py` |

---

### Backend

**Dashboard stats — 7 queries a cada 30 segundos:**

`ContentService.get_dashboard_stats()` faz:
1. `COUNT(*)` total
2. `COUNT(*)` processed
3. `COUNT(*)` recent (7 dias)
4. `AVG(importance_score)` processed
5. `GROUP BY category LIMIT 5`
6-10. 4× `COUNT(*)` por status (queued, processing, completed, failed)

São 9 queries separadas num loop de auto-refresh de 30s no frontend. Para um vault pessoal com 5.000 itens, isso é aceitável, mas é desnecessariamente ineficiente. Pode ser uma única query SQL com `GROUP BY status` + `CASE WHEN`.

**`asyncio.run()` dentro de Celery workers:**
- `workers/content_processor.py:35,42,218`
- `workers/whatsapp_tasks.py:54`

Celery workers são síncronos por design. `asyncio.run()` cria um novo event loop por chamada, o que é correto quando não há loop existente. Mas se alguma outra biblioteca no worker já criou um loop (ex: alguns drivers), isso crashará com `RuntimeError: This event loop is already running`. O padrão atual funciona na prática mas é frágil. Usar `httpx.Client` (síncrono) para downloads em vez de clientes assíncronos eliminaria o problema.

**`create_embedding` deleta e recria:**
```python
def create_embedding(self, content_id: UUID, vector: List[float]) -> ContentEmbedding:
    existing = self.db.query(ContentEmbedding).filter(...).first()
    if existing:
        self.db.delete(existing)  # delete + commit
        self.db.commit()
    embedding = ContentEmbedding(...)  # create novo
```
Dois round-trips ao banco para o que poderia ser um `INSERT ... ON CONFLICT DO UPDATE`. Não é crítico mas é o caminho menos eficiente.

**`get_pending_for_batch` filtra por `instagram_agent_processed`:**
```python
def get_pending_for_batch(self, user_id, max_count=20):
    return self.db.query(Content).filter(
        Content.instagram_agent_processed == False,  # ← sempre False para conteúdo não-instagram
        Content.status.in_(["queued", "failed"]),
    )...
```
Qualquer conteúdo não-instagram tem `instagram_agent_processed=False` por padrão — incluindo textos e links do Telegram. Esse método retorna conteúdo de qualquer tipo, não só Instagram, apesar do nome e do campo de filtro.

---

### Frontend

**Estado de auth não persiste:**
Detalhado na seção Falhas Críticas #3.

**Dashboard completamente em inglês; bots e settings em português:**
- Dashboard: "Total Content", "Processed", "Pending", "Avg Score", "Top Categories", "Recent Content"
- Bots: "✅ Recebido! Processando com IA..."
- Settings: "Salvo", "Configuração salva com sucesso"

Inconsistência de idioma visível ao usuário em cada sessão de uso.

**Empty state do Dashboard não é acionável:**
```tsx
<p className="text-muted-foreground">
  No content yet. Start by sending a message to your Telegram bot!
</p>
```
Não há link para configurar o bot, não há botão de ação. Para um novo usuário que acabou de instalar, a tela inicial é uma dead end.

**`useContents` auto-refetch global a cada 30s:**
Todo componente que usa `useContents` faz polling a 30s. Isso significa que a lista de conteúdo, o dashboard e as stats fazem requests simultâneos a cada meio minuto. Para uso pessoal em VPS modesta, isso é ruído constante mas aceitável. Poderia usar WebSocket/SSE para processos ativos.

**`useSearch` não é debounced:**
```typescript
export const useSearch = (query: string, enabled = false) => {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => searchContents(query),
    enabled: enabled && query.length > 0,
  })
}
```
Se a página de Search usa essa hook com `enabled=true` e digita a cada keystroke, cada letra dispara uma query de embedding no OpenAI (caro e lento). O `enabled` flag mitiga isso apenas se o caller não ativar até um `onSubmit`, mas a implementação permite uso incorreto.

---

### Infra

**Dev compose: nenhuma variável tem default seguro:**
```yaml
DATABASE_URL: postgresql://postgres:password@host.docker.internal:5432/signalvault
```
A senha `password` está hardcoded no compose. Se o dev esquecer de trocar, vai para produção.

**`docker-compose.yml` entrypoint comentado incorretamente:**
```yaml
# Skip entrypoint in dev — run migrations manually when needed:
#   docker compose run --rm backend alembic upgrade head
entrypoint: []
```
O backend de dev não roda migrations automaticamente. Num ambiente fresh, o dev precisa lembrar de rodar o comando manual — não está documentado no README ou em nenhum script de setup.

**Worker e backend compartilham a mesma imagem sem otimização:**
- A imagem inclui Tesseract, Chromium (Playwright), OCR libs — ~2GB de imagem Docker
- O backend puro não precisa de Tesseract ou Playwright — só o worker precisa
- Para VPS com pouco disco, isso é desperdício

**`SETTINGS_ENCRYPTION_KEY` sem geração automática:**
O `.env.example` explica como gerar (python3 -c "..."), mas não há script helper. Um usuário não-técnico não vai fazer isso. Resultado: `SETTINGS_ENCRYPTION_KEY` vazio, secrets salvos em plaintext no banco.

---

### Produto

**Bot sem comando `/add` ou ação para submeter URL:**
Os dispatchers implementados (/help, /status, /search) são bons, mas falta o fluxo inverso: o usuário quer adicionar um conteúdo específico por URL via bot. Hoje, qualquer URL enviada é capturada automaticamente — mas não há feedback claro de que isso aconteceu (a confirmação "✅ Recebido!" existe, mas o usuário não sabe se foi processada com sucesso depois).

**Notificação de conclusão pode chegar muito depois:**
`_send_completion_notification` é chamado no fim do task Celery. Para links complexos (Instagram com Playwright), o processamento pode levar 2-5 minutos. A notificação chega tarde — o usuário já esqueceu que enviou o link.

**Nenhum fluxo de onboarding:**
Um usuário que instala o sistema do zero não tem guia:
1. Gerar `SETTINGS_ENCRYPTION_KEY`
2. Configurar OpenAI no Settings
3. Configurar Telegram bot
4. Registrar webhook

Cada etapa pode falhar silenciosamente. O `/health` endpoint agora retorna status do DB/Redis, mas não valida se OpenAI está configurado ou se algum bot está ativo.

---

## 4. Aderência ao Novo Modelo (Personal AI Vault)

### O que está alinhado ✅

| Componente | Status |
|---|---|
| Single-user mode (APP_MODE=single_user) | Implementado, mas com bugs |
| Session cookie HMAC | Implementado corretamente |
| Login com apenas senha | Implementado |
| Dispatchers de comandos bot | Implementados |
| `route_task` para PROCESSING_MODE=inline | Implementado (parcialmente) |
| Webhook HMAC obrigatório em produção | Implementado |
| /health com DB + Redis check | Implementado |
| Settings UI para credenciais | Funcional |
| Stages de processamento visíveis | Funcional |

### O que está desalinhado ❌

| Componente | Problema | Esforço para corrigir |
|---|---|---|
| `UserQuota` / `Plan` — peso SaaS | Complexidade zero-valor para single_user | Médio (pode ignorar sem remover) |
| `password_reset_token` model | Sem email = feature inútil | Baixo (desabilitar endpoint) |
| `ALLOW_REGISTRATION=True` default | Inseguro em single_user | Mínimo |
| Auth state não persiste | UX quebrada no reload | Baixo |
| Inline mode quebrado | Feature anunciada não funciona | Mínimo |
| `_ingest()` sem quota tracking | Inconsistência de dados | Baixo |
| Dashboard em inglês | Inconsistência com o resto da UI | Médio |

### Esforço total de adaptação

~3-5 dias de trabalho focado para corrigir todos os desalinhamentos críticos e transformar o sistema em algo utilizável no dia a dia.

---

## 5. Quick Wins

| Ação | Impacto | Esforço |
|---|---|---|
| Corrigir `celery_task.run()` → `celery_task()` em `processing.py` | ALTO — desbloqueia modo inline | 5 min |
| `secrets.compare_digest` na comparação de senha | ALTO — elimina timing attack | 5 min |
| `ALLOW_REGISTRATION=False` default quando `APP_MODE=single_user` | ALTO — fecha brecha óbvia | 10 min |
| Persistir authStore com Zustand persist ou `/auth/me` no mount | ALTO — elimina logout no F5 | 30 min |
| `route_task` em `content_batch.py` e `instagram.py` | MÉDIO — inline mode completo | 10 min |
| `event.listens_for(engine, "first_connect")` para pgvector | MÉDIO — remove DDL por conexão | 5 min |
| `ensure_defaults()` mover para startup do app | MÉDIO — remove write em read | 15 min |
| Empty state acionável no Dashboard | MÉDIO — UX para novos usuários | 1h |
| `/health` verificar se OpenAI key está configurada | MÉDIO — onboarding observability | 15 min |
| Consolidar idioma para português em todo o frontend | BAIXO-MÉDIO — consistência | 2h |

---

## 6. Dívida Técnica (priorizada)

### P1 — Quebrado agora

1. **Inline mode quebrado** (`processing.py:33`)
2. **`content_batch.py` / `instagram.py` ignoram `route_task`**
3. **Auth state sem persistência**
4. **Registro aberto no single_user**
5. **Timing attack na comparação de senha**

### P2 — Impacta uso diário

6. **`setup_pgvector` em cada conexão do pool**
7. **9 queries separadas no dashboard stats**
8. **`ensure_defaults()` escrevendo em cada leitura de settings**
9. **Notificação de conclusão sem timeout/retry**
10. **`asyncio.run()` dentro de Celery workers (frágil)**

### P3 — Peso SaaS para remover progressivamente

11. **`UserQuota` / `Plan` — complexidade sem valor em single_user**
12. **`password_reset_token` sem infraestrutura de email**
13. **`processed` boolean redundante com `status`**
14. **`instagram_agent_processed` — campo específico de um pipeline experimental**
15. **Imagem Docker única para backend e worker (Tesseract + Playwright em todos)**

### P4 — Qualidade e manutenibilidade

16. **Zero testes automatizados** — nenhum `tests/` no repositório
17. **Nenhum script de setup** — onboarding manual e propenso a erros
18. **Mistura de idiomas no frontend**
19. **Logs sem correlation_id** — difícil debugar uma requisição específica

---

## 7. Riscos Reais (não teóricos)

### Segurança

**Risco 1 — Session hijacking em VPS sem HTTPS:**
O cookie de sessão tem `secure=COOKIE_SECURE` (default `False`). Em HTTP, o cookie viaja em plaintext. Se o VPS não tiver HTTPS configurado (situação comum em dev/setup inicial), qualquer observador na rede captura o cookie e assume a sessão.
**Mitigação:** Forçar `COOKIE_SECURE=True` quando `ENVIRONMENT=production`.

**Risco 2 — Todos os secrets expostos com uma requisição:**
`POST /settings/reveal` retorna todos os tokens (OpenAI, Telegram, WhatsApp) em JSON. Se o cookie de sessão vazar, o atacante tem acesso a todos os seus tokens de API com uma chamada.
**Mitigação:** Exigir re-autenticação (senha) para revelar secrets.

**Risco 3 — Registro aberto:**
Com `ALLOW_REGISTRATION=True` (default), qualquer pessoa que descobre `POST /auth/register` pode criar uma conta. Em single_user mode, a conta criada não terá `is_admin=True`, mas terá acesso ao sistema e poderá submeter conteúdo para processamento (consumindo quota OpenAI).

### Operação

**Risco 4 — Worker perde mensagem sem retry:**
Se o worker crasha no meio de um task `acks_late=True`, a mensagem volta para a fila e é reprocessada. Se a task já tinha salvo dados parciais no DB mas não marcado `processed=True`, o conteúdo fica em estado inconsistente (stage=ai_processing para sempre).
**Situação atual:** `mark_processing()` seta o status, mas se o worker morre após esse ponto sem chegar ao `update_processed()`, o item fica eternamente em `status=processing`.

**Risco 5 — Temp files não limpos em falha de download:**
`process_image_task` e `process_whatsapp_image_task` usam `finally: os.unlink(temp_file)`, mas se a criação de `temp_file` falhar (download error), `temp_file` é `None` e `os.unlink(None)` não é chamado — isso está correto. Porém, se o path existir mas o unlink falhar (permissão), o arquivo permanece no `/tmp`. Em uso intenso, `/tmp` pode encher.

### Uso Diário

**Risco 6 — Bot sem feedback de falha:**
Se o processamento falhar (OpenAI timeout, link inválido), o usuário recebe "✅ Recebido! Processando com IA..." mas nunca recebe notificação de falha. O conteúdo fica `status=failed` no banco, visível na UI, mas sem notificação proativa via bot. Para uso via mobile sem acesso constante à UI, falhas silenciosas são frustrantes.

**Risco 7 — Custo OpenAI imprevisto:**
Toda mensagem recebida via bot dispara `ai_service.analyze_content()` + `generate_embedding()`. Para texto longo, isso pode ser caro. Não há limite de tamanho de texto sendo passado para a API, nem estimativa de tokens antes da chamada. Um arquivo de texto grande enviado via Telegram pode gerar uma fatura inesperada.

---

## 8. Roadmap de Correção (30 dias)

### Semana 1 — Bugs críticos e segurança

| Dia | Tarefa |
|---|---|
| 1 | Corrigir `processing.py`: `celery_task.run()` → `celery_task()` |
| 1 | Corrigir timing attack na senha single_user |
| 1 | `route_task` em `content_batch.py` e `instagram.py` |
| 2 | Persistir authStore ou `/auth/me` no mount do App |
| 2 | `ALLOW_REGISTRATION=False` quando `APP_MODE=single_user` |
| 3 | `event.listens_for(engine, "first_connect")` para pgvector |
| 3 | Mover `ensure_defaults()` para startup do `main.py` |
| 4 | Notificação de falha via bot (task falhou → mensagem ao usuário) |
| 4 | Limitar tamanho de texto passado para OpenAI (max 8k tokens) |
| 5 | `COOKIE_SECURE=True` forçado quando `ENVIRONMENT=production` |

### Semana 2 — Performance e confiabilidade

| Dia | Tarefa |
|---|---|
| 6-7 | Consolidar `get_dashboard_stats` em 1-2 queries SQL |
| 8 | Adicionar compound index `(user_id, status)` e `(user_id, created_at)` |
| 9 | Substituir `asyncio.run()` em workers por clientes síncronos (httpx.Client) |
| 10 | Implementar `/health` que valida OpenAI configurado e bot ativo |

### Semana 3 — UX e produto

| Dia | Tarefa |
|---|---|
| 11-12 | Traduzir Dashboard para português |
| 13 | Empty state do Dashboard com guia de setup (link para Settings) |
| 14 | Onboarding checklist na primeira entrada (OpenAI, bot, webhook) |
| 15 | Debounce na busca semântica (300ms) |

### Semana 4 — Simplificação e testes

| Dia | Tarefa |
|---|---|
| 16-17 | Primeiro conjunto de testes: `test_auth.py`, `test_webhooks.py` |
| 18 | Script de setup automatizado (gera chaves, valida .env) |
| 19 | Desabilitar `password_reset_token` endpoints em single_user mode |
| 20 | Documentar variáveis obrigatórias no README com exemplos reais |

---

## 9. Conclusão Direta

**Vale a pena evoluir essa base?**
Sim. A stack é correta (FastAPI + Celery + pgvector), o pipeline de processamento existe e funciona, as abstrações de serviços estão no lugar certo, e os componentes críticos de segurança (HMAC, Fernet, httpOnly cookies) estão implementados. Jogar fora e reescrever seria um passo atrás.

**Está próximo de algo utilizável?**
Com as correções da Semana 1, sim — para uso pessoal básico (enviar links e textos via Telegram, buscar via dashboard). O modo inline requer a correção do bug crítico. O WhatsApp funciona mas requer setup mais complexo (Meta Developer App).

**Maior gargalo atual:**
A ausência de persistência de estado de auth no frontend é o problema mais visível no uso diário — toda vez que o usuário recarrega a página, precisa fazer login novamente se o `App.tsx` não re-hidratar o estado via `/auth/me`. Isso quebra a experiência básica de usar a UI. Esse bug, combinado com o inline mode quebrado, são os dois bloqueadores imediatos.

**O que falta para "pronto para uso pessoal real":**
1. ✅ Corrigir os 5 bugs P1 (Semana 1)
2. ✅ Notificação proativa de falha via bot
3. ✅ Guia de setup no onboarding
4. ✅ Modo inline funcional (para VPS sem Redis)

Após essas correções, o sistema está em condições de uso diário real via bot + dashboard.

---

*Auditoria realizada em: 2026-05-04*
*Base de código analisada: apps/backend + apps/frontend + docker-compose + .env.example*
*Versão do modelo de análise: Personal AI Vault (single-user, bot-first, Docker-first)*
