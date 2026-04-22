#!/usr/bin/env bash
# common.sh — shared SAM course setup boilerplate.
#
# REQUIRED: callers must set these variables BEFORE sourcing:
#   SAM_DIR="$COURSE_ROOT/sam"
#   INFRASTRUCTURE_DIR="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure"
#
# REQUIRED: callers must also run: cd "$SAM_DIR"
#
# After sourcing, PORT and UI_URL are available.

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Helper functions ──────────────────────────────────────────────────────
spinner() {
  local pid=$1
  local msg=$2
  local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
  local i=0
  local seconds=0
  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i+1) % 10 ))
    printf "\r${spin:$i:1} $msg (${seconds}s)"
    sleep 0.1
    if [ $((i % 10)) -eq 0 ]; then
      seconds=$((seconds + 1))
    fi
  done
  printf "\r"
}

get_port() {
  echo "${FASTAPI_PORT:-8000}"
}

build_ui_url() {
  local port="$1"
  if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    echo "https://${CODESPACE_NAME}-${port}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"
  else
    echo "http://127.0.0.1:${port}/"
  fi
}

ui_is_up() {
  local port="$1"
  curl -fsS "http://127.0.0.1:${port}/" >/dev/null 2>&1
}

# ── Python venv setup ─────────────────────────────────────────────────────
if [ ! -f ".venv/bin/activate" ]; then
  echo "⚙️  Setting up environment..."
  rm -rf .venv
  if ! python3 -m venv .venv; then
    echo "❌ Error: Failed to create virtual environment"
    echo "   Try: python3 -m venv .venv"
    return 1
  fi
else
  echo "✅ Environment configured"
fi

# shellcheck disable=SC1091
if ! source .venv/bin/activate; then
  echo "❌ Error: Failed to activate virtual environment"
  echo "   The .venv directory may be corrupted. Try: rm -rf .venv"
  return 1
fi

# ── Dependency install ────────────────────────────────────────────────────
# Reinstall if: marker doesn't exist OR requirements.txt is newer than marker
if [ ! -f ".venv/.deps_installed" ] || [ "requirements.txt" -nt ".venv/.deps_installed" ]; then
  pip install -q -r requirements.txt >/dev/null 2>&1 &
  spinner $! "📦 Installing dependencies..."
  if ! wait $!; then
    echo "❌ Error: Failed to install Python dependencies"
    return 1
  fi
  echo "✅ Dependencies installed"
  touch ".venv/.deps_installed"
else
  echo "✅ Dependencies installed"
fi

# ── SAM init ──────────────────────────────────────────────────────────────
if [ ! -d ".sam" ] && [ ! -f "sam.yaml" ] && [ ! -f "sam.yml" ]; then
  cp requirements.txt requirements.txt.bak
  sam init --skip >/dev/null 2>&1
  cp requirements.txt.bak requirements.txt
  rm requirements.txt.bak
fi

# ── .env.config → sam/.env sync ──────────────────────────────────────────
SHARED_ENV="$(cd "$SAM_DIR/../.." && pwd)/.env.config"
SAM_ENV="$SAM_DIR/.env"
if [ -f "$SHARED_ENV" ]; then
  if [ ! -f "$SAM_ENV" ] || ! cmp -s "$SHARED_ENV" "$SAM_ENV"; then
    cp -f "$SHARED_ENV" "$SAM_ENV"
  fi
else
  echo "⚠️  Warning: .env.config not found at $SHARED_ENV"
  echo "    Some environment variables may not be set correctly"
fi

if [ -f "$SAM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$SAM_ENV"
  set +a
fi

# For courses without infrastructure (no PostgreSQL), strip the PostgreSQL DB
# URL from sam/.env so the WebUI gateway falls back to its SQLite default.
if [ -z "${INFRASTRUCTURE_DIR:-}" ] && [ -f "$SAM_ENV" ]; then
  sed -i '/^WEB_UI_GATEWAY_DATABASE_URL=/d' "$SAM_ENV"
  unset WEB_UI_GATEWAY_DATABASE_URL
fi

# ── Port and URL setup ────────────────────────────────────────────────────
PORT="$(get_port)"
UI_URL="$(build_ui_url "$PORT")"
export PORT UI_URL

# ── Port cleanup ──────────────────────────────────────────────────────────
echo "🧹 Cleaning up..."
for p in 8000 8001 8443 8100; do
  fuser -k "${p}/tcp" >/dev/null 2>&1 || true
done
pkill -9 -f "logistics_agent.server" >/dev/null 2>&1 || true
lsof -ti:8100 | xargs kill -9 >/dev/null 2>&1 || true
sleep 2

# ── SQLite WAL removal ────────────────────────────────────────────────────
rm -f orchestrator.db orchestrator.db-shm orchestrator.db-wal \
      webui_gateway.db webui_gateway.db-shm webui_gateway.db-wal \
      acme_knowledge.db acme_knowledge.db-shm acme_knowledge.db-wal \
      platform.db platform.db-shm platform.db-wal \
      order_fulfillment_agent.db order_fulfillment_agent.db-shm order_fulfillment_agent.db-wal \
      inventory_management_agent.db inventory_management_agent.db-shm inventory_management_agent.db-wal \
      incident_response_agent.db incident_response_agent.db-shm incident_response_agent.db-wal \
      logistics_agent.db logistics_agent.db-shm logistics_agent.db-wal

# ── Solace broker check ───────────────────────────────────────────────────
if ! docker ps | grep -q solace; then
  echo "🚀 Starting Solace broker..."
  REPO_ROOT="$(cd "$SCRIPTS_DIR/../.." && pwd)"
  if ! bash "$REPO_ROOT/.devcontainer/setup-broker.sh"; then
    echo "❌ Error: Failed to start Solace broker"
    return 1
  fi
else
  echo "✅ Solace broker running"
fi

# ── Infrastructure setup (skipped if INFRASTRUCTURE_DIR is not set) ───────
if [ -n "${INFRASTRUCTURE_DIR:-}" ]; then

  # ── docker stop/rm old containers + docker compose up ──────────────────
  docker stop 300-Agents-qdrant 300-Agents-postgres >/dev/null 2>&1 || true
  docker rm 300-Agents-qdrant 300-Agents-postgres >/dev/null 2>&1 || true

  echo "🔧 Setting up infrastructure..."
  if ! docker compose -f "$INFRASTRUCTURE_DIR/docker-compose.yaml" up -d; then
    echo "❌ Error: Failed to start infrastructure containers"
    return 1
  fi

  # ── Postgres health poll ────────────────────────────────────────────────
  POSTGRES_TIMEOUT=30
  for i in $(seq 1 $POSTGRES_TIMEOUT); do
    if docker exec 300-Agents-postgres pg_isready -U acme -d orders >/dev/null 2>&1; then
      break
    fi
    if [ $i -eq $POSTGRES_TIMEOUT ]; then
      echo "❌ Error: PostgreSQL failed to start within ${POSTGRES_TIMEOUT}s"
      echo "   Check: docker logs 300-Agents-postgres"
      return 1
    fi
    sleep 1
  done

  # ── sam_gateway DB drop/recreate ────────────────────────────────────────
  docker exec 300-Agents-postgres psql -U acme -d postgres \
    -c "DROP DATABASE IF EXISTS sam_gateway" >/dev/null 2>&1 || true
  docker exec 300-Agents-postgres psql -U acme -d postgres \
    -c "CREATE DATABASE sam_gateway" >/dev/null 2>&1

  # ── DB seeding check ────────────────────────────────────────────────────
  if ! docker exec 300-Agents-postgres psql -U acme -d orders -t \
       -c "SELECT 1 FROM orders LIMIT 1;" 2>/dev/null | grep -q 1; then
    echo "🌱 Seeding database..."
    if ! python "$SCRIPTS_DIR/seed_orders_db.py"; then
      echo "❌ Error: Database seeding failed"
      return 1
    fi
  else
    echo "✅ Database seeded"
  fi

  # ── SEMP queue cleanup ──────────────────────────────────────────────────
  if curl -sf -u admin:admin \
     "http://localhost:8080/SEMP/v2/config/msgVpns/default" >/dev/null 2>&1; then
    python3 "$SCRIPTS_DIR/cleanup_broker_queues.py"
  fi

  # ── MCP npm install check ───────────────────────────────────────────────
  if [ ! -d "$INFRASTRUCTURE_DIR/node_modules" ]; then
    cd "$INFRASTRUCTURE_DIR"
    if ! npm install --silent >/dev/null 2>&1; then
      echo "⚠️  Warning: MCP server dependencies installation had errors (may still work)"
    fi
    cd "$SAM_DIR"
  fi

  # ── WEB_UI_GATEWAY_DATABASE_URL export ─────────────────────────────────
  export WEB_UI_GATEWAY_DATABASE_URL="postgresql://acme:acme@localhost:5432/sam_gateway"

  # ── /tmp/inventory-reports mkdir ───────────────────────────────────────
  mkdir -p /tmp/inventory-reports

fi  # end INFRASTRUCTURE_DIR guard
