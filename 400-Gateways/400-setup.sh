#!/usr/bin/env bash
set -euo pipefail

COURSE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAM_DIR="$COURSE_ROOT/sam"
SHARED_ENV="$COURSE_ROOT/../.env.config"
SAM_ENV="$SAM_DIR/.env"
PORT_DEFAULT=8000
AGENT_CFG="$SAM_DIR/configs/agents/customer-sql-agent.yaml"

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

ensure_env_var() {
  local var_name="$1"
  local default_value="$2"

  if ! grep -qE "^[[:space:]]*${var_name}=" "$SAM_ENV"; then
    echo "${var_name}=${default_value}" >> "$SAM_ENV"
  fi
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

# ----------------------------
# Install Module Specific Agents
# ----------------------------
echo "🤖 Installing Agents"

if [ -f "$AGENT_CFG" ]; then
  echo "✅ customer-sql-agent already configured (skipping)"
else
  sam plugin add customer-sql-agent --plugin sam-sql-database
fi

# Ensure SAM env contains SQL agent config
if ! grep -qF "# --- SQL Agent config for customer-sql-db ---" "$SAM_ENV"; then
  {
    echo ""
    echo "# --- SQL Agent config for customer-sql-db ---"
  } >> "$SAM_ENV"
fi

ensure_env_var "CUSTOMER_SQL_AGENT_DB_TYPE" "sqlite"
ensure_env_var "CUSTOMER_SQL_AGENT_DB_HOST" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_PORT" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_USER" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_PASSWORD" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_NAME" "customer_sql_agent.db"
set +e

# Load sam/.env into the current shell (so FASTAPI_PORT etc are available)
if [ -f "$SAM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$SAM_ENV"
  set +a
fi

# ----------------------------
# Run SAM with “Loading UI → URL → SAM logs”
# ----------------------------
PORT="$(get_port)"
UI_URL="$(build_ui_url "$PORT")"

# Kill anything holding the ports (restart-friendly)
for p in 8000 8001 8443; do
  fuser -k "${p}/tcp" >/dev/null 2>&1 || true
done

echo "⏳ Loading UI..."

# Print URL once the UI responds
set +m
(
  until ui_is_up "$PORT"; do
    sleep 1
  done
  echo "🌐 SAM UI: $UI_URL"
  echo ""
) &

echo "🏃 Running SAM..."
sam run