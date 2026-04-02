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
  # sam init overwrites requirements.txt — preserve ours first
  cp requirements.txt requirements.txt.bak
  sam init --skip
  cp requirements.txt.bak requirements.txt
  rm requirements.txt.bak
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

# Restart-friendly: free common SAM ports and kill LogisticsAgent (ignore errors)
echo "🧹 Stopping any existing SAM and LogisticsAgent processes..."
for p in 8000 8001 8443 8100; do
  fuser -k "${p}/tcp" >/dev/null 2>&1 || true
done
# Kill LogisticsAgent by process name (more reliable than port-based)
pkill -9 -f "logistics_agent.server" >/dev/null 2>&1 || true
# Also kill any orphaned python processes on port 8100
lsof -ti:8100 | xargs kill -9 >/dev/null 2>&1 || true
sleep 2

# Clear stale SQLite session databases and WAL journal files
echo "🧹 Clearing stale session databases..."
rm -f orchestrator.db orchestrator.db-shm orchestrator.db-wal \
      webui_gateway.db webui_gateway.db-shm webui_gateway.db-wal \
      acme_knowledge.db acme_knowledge.db-shm acme_knowledge.db-wal \
      platform.db platform.db-shm platform.db-wal \
      order_fulfillment_agent.db order_fulfillment_agent.db-shm order_fulfillment_agent.db-wal \
      inventory_management_agent.db inventory_management_agent.db-shm inventory_management_agent.db-wal \
      incident_response_agent.db incident_response_agent.db-shm incident_response_agent.db-wal \
      logistics_agent.db logistics_agent.db-shm logistics_agent.db-wal

  # Verify Solace Broker container is running
  if docker ps | grep -q solace; then
    echo "🧩 Broker already running (skipping)."
  else
    bash ../../.devcontainer/setup-broker.sh
  fi

  # Stop and remove any existing containers (handles old docker-compose location)
  echo "🧹 Cleaning up old infrastructure containers..."
  docker stop 300-Agents-qdrant 300-Agents-postgres >/dev/null 2>&1 || true
  docker rm 300-Agents-qdrant 300-Agents-postgres >/dev/null 2>&1 || true

  # Start postgres and qdrant containers (from infrastructure directory)
  echo "🚀 Starting infrastructure containers..."
  docker compose -f /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure/docker-compose.yaml up -d

  # Wait for postgres to be healthy before attempting any queries
  until docker exec 300-Agents-postgres pg_isready -U acme -d orders >/dev/null 2>&1; do
    sleep 1
  done

  # Create sam_gateway database if it doesn't exist (used by webui gateway instead of SQLite)
  if ! docker exec 300-Agents-postgres psql -U acme -d postgres -tc \
      "SELECT 1 FROM pg_database WHERE datname='sam_gateway'" 2>/dev/null | grep -q 1; then
    echo "🗄️  Creating sam_gateway database..."
    docker exec 300-Agents-postgres psql -U acme -d postgres -c "CREATE DATABASE sam_gateway" >/dev/null
  fi

  # Seed only if the orders table is empty or doesn't exist yet
  if docker exec 300-Agents-postgres psql -U acme -d orders -t -c "SELECT 1 FROM orders LIMIT 1;" 2>/dev/null | grep -q 1; then
    echo "🌱 Database already seeded (skipping)."
  else
    echo "🌱 Seeding database..."
    python /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/seed_orders_db.py
  fi

  # Clean up stale SAM event-mesh-gw queues from broker
  # Each SAM restart creates new durable queues with unique UUIDs; old ones accumulate and
  # eventually hit the broker's 100-endpoint license limit, preventing startup.
  if curl -sf -u admin:admin "http://localhost:8080/SEMP/v2/config/msgVpns/default" >/dev/null 2>&1; then
    echo "🧹 Cleaning up stale broker queues..."
    python3 - <<'PYTHON'
import urllib.request, urllib.parse, base64, json, sys
creds = base64.b64encode(b'admin:admin').decode()
def semp(path, method='GET'):
    req = urllib.request.Request(f'http://localhost:8080/SEMP/v2/{path}', method=method)
    req.add_header('Authorization', f'Basic {creds}')
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except Exception:
        return {}
queues = semp('monitor/msgVpns/default/queues?count=200').get('data', [])
deleted = sum(
    1 for q in queues
    if 'gdk/event-mesh-gw' in q['queueName'] or 'gdk/viz' in q['queueName']
    if not semp(f'config/msgVpns/default/queues/{urllib.parse.quote(q["queueName"], safe="")}', 'DELETE')
       or True
)
if deleted:
    print(f'  Deleted {deleted} stale broker queue(s)')
PYTHON
  else
    echo "⚠️  Broker SEMP not reachable — skipping queue cleanup"
  fi

# Install MCP server dependencies in centralized infrastructure location
INFRASTRUCTURE_DIR="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure"
if [ ! -d "$INFRASTRUCTURE_DIR/node_modules" ]; then
  echo "📦 Installing MCP server dependencies..."
  cd "$INFRASTRUCTURE_DIR"
  npm install
  cd "$SAM_DIR"
else
  echo "📦 MCP server dependencies already installed (skipping)."
fi

# Point the webui gateway at PostgreSQL to avoid SQLite concurrent-write lock errors
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://acme:acme@localhost:5432/sam_gateway"

# Create /tmp/inventory-reports if InventoryManagementAgent exists
# (MCP filesystem server requires this directory to exist at startup)
if [ -f "$SAM_DIR/configs/agents/inventory_management_agent_agent.yaml" ] && \
   [ -f "$SAM_DIR/configs/gateways/acme-inventory-events.yaml" ]; then
  if [ ! -d "/tmp/inventory-reports" ]; then
    echo "📁 Creating /tmp/inventory-reports for InventoryManagementAgent MCP filesystem tool..."
    mkdir -p /tmp/inventory-reports
  fi
fi

# Start LogisticsAgent (Strands-based external agent) if it exists
LOGISTICS_AGENT_DIR="$INFRASTRUCTURE_DIR/logistics_agent"
if [ -d "$LOGISTICS_AGENT_DIR" ] && [ -f "$SAM_DIR/configs/agents/a2a.yaml" ]; then
  echo "🚢 Starting LogisticsAgent (Strands)..."
  
  # Ensure LogisticsAgent is fully stopped (already killed above, but double-check)
  pkill -9 -f "logistics_agent.server" >/dev/null 2>&1 || true
  lsof -ti:8100 | xargs kill -9 >/dev/null 2>&1 || true
  sleep 1
  
  # Ensure Strands dependencies are installed
  if [ ! -f "$LOGISTICS_AGENT_DIR/.deps_installed" ]; then
    echo "📦 Installing Strands dependencies..."
    pip install strands-agents strands-agents-tools psycopg2-binary fastapi uvicorn pydantic anthropic boto3 >/dev/null 2>&1
    touch "$LOGISTICS_AGENT_DIR/.deps_installed"
  fi
  
  # Set environment variables for LogisticsAgent
  # These are read by logistics_agent/agent.py's detect_and_configure_model() function
  export LLM_SERVICE_ENDPOINT="${LLM_SERVICE_ENDPOINT:-https://lite-llm.mymaas.net}"
  export LLM_SERVICE_API_KEY="${LLM_SERVICE_API_KEY}"
  export LLM_SERVICE_GENERAL_MODEL_NAME="${LLM_SERVICE_GENERAL_MODEL_NAME:-openai/vertex-claude-4-5-sonnet}"
  export ORDERS_DB_CONNECTION_STRING="${ORDERS_DB_CONNECTION_STRING:-postgresql://acme:acme@localhost:5432/orders}"
  
  # Start LogisticsAgent in background (cd to infrastructure dir for Python module resolution)
  cd "$INFRASTRUCTURE_DIR"
  nohup python -m logistics_agent.server > "$SAM_DIR/logistics_agent.log" 2>&1 &
  LOGISTICS_PID=$!
  cd "$SAM_DIR"  # Return to SAM_DIR
  
  # Wait for LogisticsAgent to be fully ready (health check)
  echo "⏳ Waiting for LogisticsAgent to be ready..."
  LOGISTICS_READY=false
  for i in {1..30}; do
    if curl -fsS "http://localhost:8100/health" >/dev/null 2>&1; then
      LOGISTICS_READY=true
      break
    fi
    sleep 1
  done
  
  if [ "$LOGISTICS_READY" = true ]; then
    echo "✅ LogisticsAgent ready (PID: $LOGISTICS_PID, port 8100)"
  else
    echo "⚠️  LogisticsAgent started but not responding on port 8100. Check $SAM_DIR/logistics_agent.log for details."
    echo "   SAM will continue starting - the A2A proxy will discover it when ready."
  fi
else
  echo "📦 LogisticsAgent not found (skipping)."
fi

# Print URL once the UI is reachable
echo "⏳ Loading UI..."
set +m
(
  until ui_is_up "$PORT"; do
    sleep 1
  done
  echo ""
  echo "🌐 SAM UI: $UI_URL"
  echo ""
  exit 0
) &

# Run SAM in the foreground so logs behave normally and it stays running
echo "🏃 Running SAM..."
sam run