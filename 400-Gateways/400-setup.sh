#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📂 Course root: $REPO_ROOT"

cd "$REPO_ROOT/sam"

echo "🔧 Creating virtual environment..."
python3 -m venv .venv

echo "⚡ Activating virtual environment..."
source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🎭 Installing Playwright..."
playwright install

echo "🚀 Initializing SAM..."
sam init --skip

# Sync with shared .env file
SHARED_ENV="../../.env.config"
SAM_ENV="$COURSE_ROOT/sam/.env"

if [ -f "$SHARED_ENV" ]; then
  echo "🔁 Syncing root .env → sam/.env"
  cp "$SHARED_ENV" "$SAM_ENV"
else
  echo "⚠️ Root .env not found, creating new sam/.env"
  touch "$SAM_ENV"
fi

# Append VAR=VALUE if VAR isn't already defined in sam/.env
ensure_env_var() {
  local var_name="$1"
  local default_value="$2"

  if ! grep -qE "^[[:space:]]*${var_name}=" "$SAM_ENV"; then
    echo "${var_name}=${default_value}" >> "$SAM_ENV"
  fi
}

# Add header Comment
if ! grep -q "# --- SQL Agent config for customer-sql-db ---" "$SAM_ENV"; then
  {
    echo ""
    echo "# --- SQL Agent config for customer-sql-db ---"
  } >> "$SAM_ENV"
fi

# Install Module Specific Agents
echo "🤖 Installing Agents"
sam plugin add customer-sql-agent --plugin sam-sql-database

# Only set if they DON'T already exist in .env.config
ensure_env_var "CUSTOMER_SQL_AGENT_DB_TYPE" "sqlite"
ensure_env_var "CUSTOMER_SQL_AGENT_DB_HOST" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_PORT" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_USER" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_PASSWORD" ""
ensure_env_var "CUSTOMER_SQL_AGENT_DB_NAME" "customer_sql_agent.db"
echo "✅ Setup complete"
set +e

echo "🏃 Running SAM"
sam run