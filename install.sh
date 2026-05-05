#!/bin/bash
# install.sh — Setup automático do Keepiu em localhost (modo single-user)
set -euo pipefail

# ── Cores ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Configuração ───────────────────────────────────────────────────────────────
REPO_URL="https://github.com/eduardovrocha/keepiu.git"
PROJECT_DIR="keepiu"
BACKEND_URL="http://localhost:8000"
HEALTH_RETRIES=30
HEALTH_INTERVAL=3

# ── Utilitários de log ─────────────────────────────────────────────────────────
log()     { echo -e "  ${BLUE}→${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${NC}  $*"; }
die()     { echo -e "\n  ${RED}✗ Erro: $*${NC}" >&2; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}$*${NC}\n  $(printf '─%.0s' {1..48})${NC}"; }

# ── Leitura e escrita segura de variáveis no .env ──────────────────────────────
# Ignora linhas comentadas; retorna vazio se a variável não existe.
get_env() {
  local key="$1" file="${2:-.env}"
  grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d'=' -f2- || true
}

# Define ou atualiza uma variável no .env.
# Usa variáveis de ambiente para passar key/value ao Python — seguro para
# qualquer caractere especial (incluindo =, /, \, aspas, caracteres base64).
set_env() {
  local key="$1" value="$2" file="${3:-.env}"
  ENV_KEY="$key" ENV_VALUE="$value" ENV_FILE="$file" python3 - <<'PYEOF'
import re, os
key   = os.environ['ENV_KEY']
value = os.environ['ENV_VALUE']
path  = os.environ['ENV_FILE']
with open(path) as f:
    content = f.read()
pat = re.compile(r'^' + re.escape(key) + r'=.*$', re.MULTILINE)
line = f'{key}={value}'
if pat.search(content):
    content = pat.sub(line, content)
else:
    content = content.rstrip('\n') + '\n' + line + '\n'
with open(path, 'w') as f:
    f.write(content)
PYEOF
}

# ── Verificação de porta ───────────────────────────────────────────────────────
port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -i :"$port" >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep -q ":${port} "
  else
    return 1  # não conseguiu verificar — assume livre
  fi
}

# ── Aguardar /health com retry ─────────────────────────────────────────────────
wait_for_health() {
  local retries=$HEALTH_RETRIES
  printf "  ${BLUE}→${NC} Aguardando backend"
  while [ "$retries" -gt 0 ]; do
    if curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1; then
      echo ""
      return 0
    fi
    retries=$((retries - 1))
    printf "."
    sleep $HEALTH_INTERVAL
  done
  echo ""
  return 1
}

# ── Trap de erro ───────────────────────────────────────────────────────────────
trap 'echo -e "\n  ${RED}✗ Setup interrompido.${NC}\n  Verifique os logs: ${BOLD}docker compose logs backend${NC}" >&2' ERR

# ══════════════════════════════════════════════════════════════════════════════
#  BANNER
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}  ╔═══════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}  ║         Keepiu — Local Setup          ║${NC}"
echo -e "${BOLD}${CYAN}  ║     single-user · Docker · localhost   ║${NC}"
echo -e "${BOLD}${CYAN}  ╚═══════════════════════════════════════╝${NC}"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
#  1. DEPENDÊNCIAS
# ══════════════════════════════════════════════════════════════════════════════
section "1/8  Verificando dependências"

command -v docker >/dev/null 2>&1 \
  || die "Docker não encontrado. Instale em: https://docs.docker.com/get-docker/"

docker compose version >/dev/null 2>&1 \
  || die "Docker Compose não disponível. Instale o Docker Desktop ou o plugin compose."

command -v python3 >/dev/null 2>&1 \
  || die "python3 não encontrado. É necessário para gerar os secrets de segurança."

ok "Docker        $(docker --version | awk '{print $3}' | tr -d ',')"
ok "Docker Compose $(docker compose version --short 2>/dev/null || docker compose version | awk '{print $NF}')"
ok "Python        $(python3 --version | awk '{print $2}')"

# ══════════════════════════════════════════════════════════════════════════════
#  2. CLONE / NAVEGAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
section "2/8  Localizando projeto"

if [ -f "docker-compose.yml" ] && [ -f ".env.example" ]; then
  ok "Já dentro do repositório: $(pwd)"
elif [ -d "$PROJECT_DIR" ]; then
  log "Diretório '$PROJECT_DIR' já existe — pulando clone."
  cd "$PROJECT_DIR"
  ok "Navegado para: $(pwd)"
else
  log "Clonando $REPO_URL ..."
  git clone "$REPO_URL" "$PROJECT_DIR"
  cd "$PROJECT_DIR"
  ok "Repositório clonado em: $(pwd)"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  3. VERIFICAÇÃO DE PORTAS
# ══════════════════════════════════════════════════════════════════════════════
section "3/8  Verificando portas"

BLOCKED=()
for p in 8000 5173 5174 5555; do
  if port_in_use "$p"; then
    BLOCKED+=("$p")
  fi
done

if [ ${#BLOCKED[@]} -gt 0 ]; then
  warn "Portas em uso: ${BLOCKED[*]}"
  warn "Isso pode causar conflito com os containers."
  echo -n "  Continuar mesmo assim? [s/N] "
  read -r RESP
  [[ "$RESP" =~ ^[sS]$ ]] || die "Abortado. Libere as portas e tente novamente."
else
  ok "Portas 8000, 5173, 5174, 5555 disponíveis"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  4. ARQUIVO .env
# ══════════════════════════════════════════════════════════════════════════════
section "4/8  Configurando .env"

if [ -f ".env" ]; then
  warn ".env já existe — valores existentes serão mantidos."
else
  cp .env.example .env
  ok ".env criado a partir do .env.example"
fi

# ── OpenAI API Key ─────────────────────────────────────────────────────────────
CURRENT_KEY=$(get_env "OPENAI_API_KEY")
if [ -z "$CURRENT_KEY" ] || [[ "$CURRENT_KEY" == sk-your* ]]; then
  echo ""
  echo -e "  ${BOLD}OPENAI_API_KEY${NC} é necessária para processamento de conteúdo (resumos, tags, busca semântica)."
  echo -n "  Cole sua chave (sk-...): "
  read -rs OPENAI_INPUT
  echo ""
  [ -z "$OPENAI_INPUT" ] && die "OPENAI_API_KEY não pode ser vazia."
  set_env "OPENAI_API_KEY" "$OPENAI_INPUT"
  ok "OPENAI_API_KEY configurada"
else
  ok "OPENAI_API_KEY já configurada"
fi

# ── APP_PASSWORD ───────────────────────────────────────────────────────────────
CURRENT_PASS=$(get_env "APP_PASSWORD")
if [ -z "$CURRENT_PASS" ]; then
  echo ""
  echo -e "  ${BOLD}APP_PASSWORD${NC} é a senha de acesso à interface web (modo single_user)."
  while true; do
    echo -n "  Escolha uma senha (mínimo 6 caracteres): "
    read -rs PASS_INPUT
    echo ""
    [ ${#PASS_INPUT} -ge 6 ] && break
    warn "Senha muito curta. Use pelo menos 6 caracteres."
  done
  set_env "APP_PASSWORD" "$PASS_INPUT"
  ok "APP_PASSWORD configurada"
else
  ok "APP_PASSWORD já configurada"
fi

# ── Secrets automáticos ────────────────────────────────────────────────────────
CURRENT_SESSION=$(get_env "SESSION_SECRET")
if [ -z "$CURRENT_SESSION" ]; then
  SESSION_VAL=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  set_env "SESSION_SECRET" "$SESSION_VAL"
  ok "SESSION_SECRET gerado"
else
  ok "SESSION_SECRET já configurado"
fi

CURRENT_ENC=$(get_env "SETTINGS_ENCRYPTION_KEY")
if [ -z "$CURRENT_ENC" ]; then
  ENC_VAL=$(python3 -c "
try:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
except ImportError:
    import base64, os
    print(base64.urlsafe_b64encode(os.urandom(32)).decode())
")
  set_env "SETTINGS_ENCRYPTION_KEY" "$ENC_VAL"
  ok "SETTINGS_ENCRYPTION_KEY gerado"
else
  ok "SETTINGS_ENCRYPTION_KEY já configurado"
fi

# ── Configuração mínima para localhost ────────────────────────────────────────
set_env "APP_MODE"         "single_user"
set_env "PROCESSING_MODE"  "inline"
set_env "ENVIRONMENT"      "development"
set_env "VITE_API_URL"     "http://localhost:8000"
set_env "FRONTEND_URL"     "http://localhost:5173"

ok "Modo configurado: APP_MODE=single_user  PROCESSING_MODE=inline"

# ══════════════════════════════════════════════════════════════════════════════
#  5. BUILD E START DOS CONTAINERS
# ══════════════════════════════════════════════════════════════════════════════
section "5/8  Iniciando containers"

log "Build e start via docker compose (pode levar alguns minutos na primeira vez)..."
docker compose --profile internal-db up -d --build

ok "Containers iniciados"

# ══════════════════════════════════════════════════════════════════════════════
#  6. AGUARDAR BANCO DE DADOS
# ══════════════════════════════════════════════════════════════════════════════
section "6/8  Aguardando banco de dados"

DB_USER=$(get_env "POSTGRES_USER")
DB_USER="${DB_USER:-signalvault}"
DB_RETRIES=30

printf "  ${BLUE}→${NC} Verificando PostgreSQL"
until docker compose exec -T db pg_isready -U "$DB_USER" >/dev/null 2>&1; do
  DB_RETRIES=$((DB_RETRIES - 1))
  if [ "$DB_RETRIES" -eq 0 ]; then
    echo ""
    die "Banco de dados não ficou disponível. Verifique: docker compose logs db"
  fi
  printf "."
  sleep 2
done
echo ""
ok "PostgreSQL disponível"

# ══════════════════════════════════════════════════════════════════════════════
#  7. MIGRATIONS
# ══════════════════════════════════════════════════════════════════════════════
section "7/8  Executando migrations"

docker compose run --rm backend alembic upgrade head
ok "Migrations aplicadas"

log "Reiniciando backend para inicializar usuário owner..."
docker compose restart backend

# ══════════════════════════════════════════════════════════════════════════════
#  8. HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════
section "8/8  Verificando saúde da aplicação"

if wait_for_health; then
  HEALTH_JSON=$(curl -s "${BACKEND_URL}/health")
  ok "Backend respondeu: $HEALTH_JSON"
else
  warn "Backend ainda não respondeu ao /health após $((HEALTH_RETRIES * HEALTH_INTERVAL))s."
  warn "A aplicação pode estar ainda inicializando."
  warn "Verifique com: docker compose logs backend"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  RESULTADO FINAL
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}  ┌─────────────────────────────────────────────┐${NC}"
echo -e "${BOLD}${GREEN}  │        Keepiu está rodando!                 │${NC}"
echo -e "${BOLD}${GREEN}  └─────────────────────────────────────────────┘${NC}"
echo ""
echo -e "  ${BOLD}Interface web:${NC}  http://localhost:5173"
echo -e "  ${BOLD}API / Backend:${NC}  http://localhost:8000"
echo -e "  ${BOLD}Docs da API:${NC}    http://localhost:8000/docs"
echo -e "  ${BOLD}Landing page:${NC}   http://localhost:5174"
echo -e "  ${BOLD}Flower:${NC}         http://localhost:5555  ${CYAN}(admin:changeme)${NC}"
echo ""
echo -e "  ${BOLD}Login:${NC}          use a senha definida em APP_PASSWORD"
echo ""
echo -e "  ${YELLOW}Parar:${NC}    docker compose --profile internal-db down"
echo -e "  ${YELLOW}Logs:${NC}     docker compose logs -f backend"
echo -e "  ${YELLOW}Reiniciar:${NC} docker compose restart backend"
echo ""
