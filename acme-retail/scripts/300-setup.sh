#!/usr/bin/env bash
set -euo pipefail

COURSE_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
SAM_DIR="$COURSE_ROOT/sam"
SHARED_ENV="$COURSE_ROOT/../.env.config"
SAM_ENV="$SAM_DIR/.env"
PORT_DEFAULT=8000

echo "📂 Course root: $COURSE_ROOT"
cd "$SAM_DIR"

# ----------------------------
# Helpers
# ----------------------------
get_port() {
  echo "${FASTAPI_PORT:-$PORT_DEFAULT}"
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

agents_ready() {
  local port="$1"
  local cards
  cards=$(curl -fsS "http://127.0.0.1:${port}/api/v1/agentCards" 2>/dev/null) || return 1
  echo "$cards" | grep -q "OrchestratorAgent" || return 1
  echo "$cards" | grep -q "AcmeKnowledge" || return 1
  return 0
}

# ----------------------------
# Setup (only if needed)
# ----------------------------
if [ ! -d ".venv" ]; then
  echo "🔧 Creating virtual environment..."
  python3 -m venv .venv
fi

echo "⚡ Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ]; then
  echo "📦 Installing dependencies..."
  pip install -r requirements.txt
  playwright install
  touch ".venv/.deps_installed"
else
  echo "📦 Dependencies already installed (skipping)."
fi

if [ ! -d ".sam" ] && [ ! -f "sam.yaml" ] && [ ! -f "sam.yml" ]; then
  echo "🚀 Initializing SAM..."
  sam init --skip
else
  echo "🚀 SAM already initialized (skipping)."
fi

if [ -f "$SHARED_ENV" ]; then
  if [ ! -f "$SAM_ENV" ] || ! cmp -s "$SHARED_ENV" "$SAM_ENV"; then
    echo "🔁 Syncing shared .env.config → sam/.env"
    cp -f "$SHARED_ENV" "$SAM_ENV"
  else
    echo "🔁 sam/.env already up to date (skipping)."
  fi
else
  echo "⚠️ Shared .env.config not found at: $SHARED_ENV (skipping env sync)"
fi

# Load sam/.env into the current shell (so FASTAPI_PORT etc are available)
if [ -f "$SAM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$SAM_ENV"
  set +a
fi

# ----------------------------
# Running SAM
# ----------------------------
PORT="$(get_port)"
UI_URL="$(build_ui_url "$PORT")"

# Restart-friendly: free common SAM ports (ignore errors)
for p in 8000 8001 8443; do
  fuser -k "${p}/tcp" >/dev/null 2>&1 || true
done

# Clear stale session databases to prevent history conflicts on restart
echo "🧹 Clearing stale session databases..."
rm -f orchestrator.db webui_gateway.db acme_knowledge.db platform.db

  # Verify Solace Broker container is running
  if docker ps | grep -q solace; then
    echo "🧩 Broker already running (skipping)."
  else
    bash ../../.devcontainer/setup-broker.sh
  fi

  # Start postgres container and seed db
  docker compose up -d

  # Wait for postgres to be healthy before attempting any queries
  until docker exec 300-Agents-postgres pg_isready -U acme -d orders >/dev/null 2>&1; do
    sleep 1
  done

  # Seed only if the orders table is empty or doesn't exist yet
  if docker exec 300-Agents-postgres psql -U acme -d orders -t -c "SELECT 1 FROM orders LIMIT 1;" 2>/dev/null | grep -q 1; then
    echo "🌱 Database already seeded (skipping)."
  else
    echo "🌱 Seeding database..."
    python /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/seed_orders_db.py
  fi

# Print URL once the UI is reachable and all agents have registered
echo "⏳ Loading UI and waiting for agents..."
set +m
(
  until ui_is_up "$PORT"; do
    sleep 1
  done
  until agents_ready "$PORT"; do
    sleep 2
  done
  echo ""
  echo "🌐 SAM UI: $UI_URL"
  echo ""
  exit 0
) &

# Run SAM in the foreground so logs behave normally and it stays running
echo "🏃 Running SAM..."
sam run