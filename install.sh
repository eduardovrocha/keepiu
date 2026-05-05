#!/bin/bash
# install.sh — Automated local setup for Keepiu (single-user mode)
set -euo pipefail

# ── Colors ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Config ─────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/eduardovrocha/keepiu.git"
PROJECT_DIR="keepiu"
BACKEND_URL="http://localhost:8000"
HEALTH_RETRIES=30
HEALTH_INTERVAL=3

# ── Logging helpers ────────────────────────────────────────────────────────────
log()     { echo -e "  ${BLUE}→${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${NC}  $*"; }
die()     { echo -e "\n  ${RED}✗ Error: $*${NC}" >&2; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}$*${NC}\n  $(printf '─%.0s' {1..48})${NC}"; }

# ── Safe .env read/write ───────────────────────────────────────────────────────
# Reads a variable from .env, ignoring commented lines. Returns empty if missing.
get_env() {
  local key="$1" file="${2:-.env}"
  grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d'=' -f2- || true
}

# Sets or updates a variable in .env.
# Passes key/value via environment variables to Python — safe for any special
# characters (including =, /, \, quotes, base64 padding).
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

# ── Port check ─────────────────────────────────────────────────────────────────
port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -i :"$port" >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep -q ":${port} "
  else
    return 1  # cannot check — assume available
  fi
}

# ── Health check with retry ────────────────────────────────────────────────────
wait_for_health() {
  local retries=$HEALTH_RETRIES
  printf "  ${BLUE}→${NC} Waiting for backend"
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

# ── Error trap ─────────────────────────────────────────────────────────────────
trap 'echo -e "\n  ${RED}✗ Setup interrupted.${NC}\n  Check the logs: ${BOLD}docker compose logs backend${NC}" >&2' ERR

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
#  1. DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════
section "1/8  Checking dependencies"

command -v docker >/dev/null 2>&1 \
  || die "Docker not found. Install it at: https://docs.docker.com/get-docker/"

docker compose version >/dev/null 2>&1 \
  || die "Docker Compose not available. Install Docker Desktop or the compose plugin."

command -v python3 >/dev/null 2>&1 \
  || die "python3 not found. Required to generate security secrets."

ok "Docker         $(docker --version | awk '{print $3}' | tr -d ',')"
ok "Docker Compose $(docker compose version --short 2>/dev/null || docker compose version | awk '{print $NF}')"
ok "Python         $(python3 --version | awk '{print $2}')"

# ══════════════════════════════════════════════════════════════════════════════
#  2. CLONE / NAVIGATE
# ══════════════════════════════════════════════════════════════════════════════
section "2/8  Locating project"

if [ -f "docker-compose.yml" ] && [ -f ".env.example" ]; then
  ok "Already inside the repository: $(pwd)"
elif [ -d "$PROJECT_DIR" ]; then
  log "Directory '$PROJECT_DIR' already exists — skipping clone."
  cd "$PROJECT_DIR"
  ok "Navigated to: $(pwd)"
else
  log "Cloning $REPO_URL ..."
  git clone "$REPO_URL" "$PROJECT_DIR"
  cd "$PROJECT_DIR"
  ok "Repository cloned to: $(pwd)"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  3. PORT CHECK
# ══════════════════════════════════════════════════════════════════════════════
section "3/8  Checking ports"

BLOCKED=()
for p in 8000 5173 5174 5555; do
  if port_in_use "$p"; then
    BLOCKED+=("$p")
  fi
done

if [ ${#BLOCKED[@]} -gt 0 ]; then
  warn "Ports already in use: ${BLOCKED[*]}"
  warn "This may conflict with the containers."
  echo -n "  Continue anyway? [y/N] "
  read -r RESP
  [[ "$RESP" =~ ^[yY]$ ]] || die "Aborted. Free the ports and try again."
else
  ok "Ports 8000, 5173, 5174, 5555 available"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  4. .env FILE
# ══════════════════════════════════════════════════════════════════════════════
section "4/8  Configuring .env"

if [ -f ".env" ]; then
  warn ".env already exists — existing values will be kept."
else
  cp .env.example .env
  ok ".env created from .env.example"
fi

# ── OpenAI API Key ─────────────────────────────────────────────────────────────
CURRENT_KEY=$(get_env "OPENAI_API_KEY")
if [ -z "$CURRENT_KEY" ] || [[ "$CURRENT_KEY" == sk-your* ]]; then
  echo ""
  echo -e "  ${BOLD}OPENAI_API_KEY${NC} is required for content processing (summaries, tags, semantic search)."
  echo -n "  Paste your key (sk-...): "
  read -rs OPENAI_INPUT
  echo ""
  [ -z "$OPENAI_INPUT" ] && die "OPENAI_API_KEY cannot be empty."
  set_env "OPENAI_API_KEY" "$OPENAI_INPUT"
  ok "OPENAI_API_KEY set"
else
  ok "OPENAI_API_KEY already configured"
fi

# ── APP_PASSWORD ───────────────────────────────────────────────────────────────
CURRENT_PASS=$(get_env "APP_PASSWORD")
if [ -z "$CURRENT_PASS" ]; then
  echo ""
  echo -e "  ${BOLD}APP_PASSWORD${NC} is the password to access the web interface (single_user mode)."
  while true; do
    echo -n "  Choose a password (minimum 6 characters): "
    read -rs PASS_INPUT
    echo ""
    [ ${#PASS_INPUT} -ge 6 ] && break
    warn "Password too short. Use at least 6 characters."
  done
  set_env "APP_PASSWORD" "$PASS_INPUT"
  ok "APP_PASSWORD set"
else
  ok "APP_PASSWORD already configured"
fi

# ── Auto-generated secrets ─────────────────────────────────────────────────────
CURRENT_SESSION=$(get_env "SESSION_SECRET")
if [ -z "$CURRENT_SESSION" ]; then
  SESSION_VAL=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  set_env "SESSION_SECRET" "$SESSION_VAL"
  ok "SESSION_SECRET generated"
else
  ok "SESSION_SECRET already configured"
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
  ok "SETTINGS_ENCRYPTION_KEY generated"
else
  ok "SETTINGS_ENCRYPTION_KEY already configured"
fi

# ── Minimum localhost configuration ───────────────────────────────────────────
set_env "APP_MODE"         "single_user"
set_env "PROCESSING_MODE"  "inline"
set_env "ENVIRONMENT"      "development"
set_env "VITE_API_URL"     "http://localhost:8000"
set_env "FRONTEND_URL"     "http://localhost:5173"

ok "Mode set: APP_MODE=single_user  PROCESSING_MODE=inline"

# ══════════════════════════════════════════════════════════════════════════════
#  5. BUILD AND START CONTAINERS
# ══════════════════════════════════════════════════════════════════════════════
section "5/8  Starting containers"

log "Building and starting services (first run may take a few minutes)..."
docker compose --profile internal-db up -d --build

ok "Containers started"

# ══════════════════════════════════════════════════════════════════════════════
#  6. WAIT FOR DATABASE
# ══════════════════════════════════════════════════════════════════════════════
section "6/8  Waiting for database"

DB_USER=$(get_env "POSTGRES_USER")
DB_USER="${DB_USER:-signalvault}"
DB_RETRIES=30

printf "  ${BLUE}→${NC} Checking PostgreSQL"
until docker compose exec -T db pg_isready -U "$DB_USER" >/dev/null 2>&1; do
  DB_RETRIES=$((DB_RETRIES - 1))
  if [ "$DB_RETRIES" -eq 0 ]; then
    echo ""
    die "Database did not become available. Check: docker compose logs db"
  fi
  printf "."
  sleep 2
done
echo ""
ok "PostgreSQL ready"

# ══════════════════════════════════════════════════════════════════════════════
#  7. MIGRATIONS
# ══════════════════════════════════════════════════════════════════════════════
section "7/8  Running migrations"

docker compose run --rm backend alembic upgrade head
ok "Migrations applied"

log "Restarting backend to initialize owner user..."
docker compose restart backend

# ══════════════════════════════════════════════════════════════════════════════
#  8. HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════
section "8/8  Verifying application health"

if wait_for_health; then
  HEALTH_JSON=$(curl -s "${BACKEND_URL}/health")
  ok "Backend responded: $HEALTH_JSON"
else
  warn "Backend did not respond to /health after $((HEALTH_RETRIES * HEALTH_INTERVAL))s."
  warn "The application may still be initializing."
  warn "Check with: docker compose logs backend"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  FINAL OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}  ┌─────────────────────────────────────────────┐${NC}"
echo -e "${BOLD}${GREEN}  │         Keepiu is running!                  │${NC}"
echo -e "${BOLD}${GREEN}  └─────────────────────────────────────────────┘${NC}"
echo ""
echo -e "  ${BOLD}Web interface:${NC}  http://localhost:5173"
echo -e "  ${BOLD}API / Backend:${NC}  http://localhost:8000"
echo -e "  ${BOLD}API Docs:${NC}       http://localhost:8000/docs"
echo -e "  ${BOLD}Landing page:${NC}   http://localhost:5174"
echo -e "  ${BOLD}Flower:${NC}         http://localhost:5555  ${CYAN}(admin:changeme)${NC}"
echo ""
echo -e "  ${BOLD}Login:${NC}          use the password set in APP_PASSWORD"
echo ""
echo -e "  ${YELLOW}Stop:${NC}     docker compose --profile internal-db down"
echo -e "  ${YELLOW}Logs:${NC}     docker compose logs -f backend"
echo -e "  ${YELLOW}Restart:${NC}  docker compose restart backend"
echo ""
