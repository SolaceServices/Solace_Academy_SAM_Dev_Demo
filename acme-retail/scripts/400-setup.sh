#!/usr/bin/env bash
set -euo pipefail

COURSE_ROOT="${1:-/workspaces/Solace_Academy_SAM_Dev_Demo/400-Evals}"
SAM_DIR="$COURSE_ROOT/sam"
SHARED_ENV="/workspaces/Solace_Academy_SAM_Dev_Demo/.env.config"
SAM_ENV="$SAM_DIR/.env"
PORT_DEFAULT=8000

cd "$SAM_DIR"

# ----------------------------
# Helpers
# ----------------------------
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
if [ ! -f ".venv/bin/activate" ]; then
  echo "⚙️  Setting up environment..."
  rm -rf .venv  # Clean up any corrupted venv
  if ! python3 -m venv .venv; then
    echo "❌ Error: Failed to create virtual environment"
    echo "   Try: python3 -m venv .venv"
    exit 1
  fi
else
  echo "✅ Environment configured"
fi

# shellcheck disable=SC1091
if ! source .venv/bin/activate; then
  echo "❌ Error: Failed to activate virtual environment"
  echo "   The .venv directory may be corrupted. Try: rm -rf .venv"
  exit 1
fi

# Check if we need to install/update dependencies
# Reinstall if: 1) marker doesn't exist, OR 2) requirements.txt is newer than marker
if [ ! -f ".venv/.deps_installed" ] || [ "requirements.txt" -nt ".venv/.deps_installed" ]; then
  pip install -q -r requirements.txt >/dev/null 2>&1 &
  spinner $! "📦 Installing dependencies..."
  wait $!
  if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install Python dependencies"
    exit 1
  fi
  echo "✅ Dependencies installed"
  touch ".venv/.deps_installed"
else
  echo "✅ Dependencies installed"
fi

if [ ! -d ".sam" ] && [ ! -f "sam.yaml" ] && [ ! -f "sam.yml" ]; then
  # sam init overwrites requirements.txt — preserve ours first
  cp requirements.txt requirements.txt.bak
  sam init --skip >/dev/null 2>&1
  cp requirements.txt.bak requirements.txt
  rm requirements.txt.bak
fi

if [ -f "$SHARED_ENV" ]; then
  if [ ! -f "$SAM_ENV" ] || ! cmp -s "$SHARED_ENV" "$SAM_ENV"; then
    cp -f "$SHARED_ENV" "$SAM_ENV"
  fi
else
  echo "⚠️  Warning: .env.config not found at $SHARED_ENV"
  echo "    Some environment variables may not be set correctly"
fi

# Load sam/.env into the current shell (so FASTAPI_PORT etc are available)
if [ -f "$SAM_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$SAM_ENV"
  set +a
fi

# ----------------------------
# Infrastructure Setup
# ----------------------------
PORT="$(get_port)"
UI_URL="$(build_ui_url "$PORT")"

# Restart-friendly: free common SAM ports and kill LogisticsAgent (ignore errors)
echo "🧹 Cleaning up..."
for p in 8000 8001 8443 8100; do
  fuser -k "${p}/tcp" >/dev/null 2>&1 || true
done
pkill -9 -f "logistics_agent.server" >/dev/null 2>&1 || true
lsof -ti:8100 | xargs kill -9 >/dev/null 2>&1 || true
sleep 2

# Clear stale SQLite session databases and WAL journal files
rm -f orchestrator.db orchestrator.db-shm orchestrator.db-wal \
      webui_gateway.db webui_gateway.db-shm webui_gateway.db-wal \
      acme_knowledge.db acme_knowledge.db-shm acme_knowledge.db-wal \
      platform.db platform.db-shm platform.db-wal \
      order_fulfillment_agent.db order_fulfillment_agent.db-shm order_fulfillment_agent.db-wal \
      inventory_management_agent.db inventory_management_agent.db-shm inventory_management_agent.db-wal \
      incident_response_agent.db incident_response_agent.db-shm incident_response_agent.db-wal \
      logistics_agent.db logistics_agent.db-shm logistics_agent.db-wal

# Verify Solace Broker container is running
if ! docker ps | grep -q solace; then
  echo "🚀 Starting Solace broker..."
  if ! bash /workspaces/Solace_Academy_SAM_Dev_Demo/.devcontainer/setup-broker.sh; then
    echo "❌ Error: Failed to start Solace broker"
    exit 1
  fi
else
  echo "✅ Solace broker running"
fi

# Stop and remove any existing containers (handles old docker-compose location)
docker stop 300-Agents-qdrant 300-Agents-postgres >/dev/null 2>&1 || true
docker rm 300-Agents-qdrant 300-Agents-postgres >/dev/null 2>&1 || true

# Start postgres and qdrant containers (from infrastructure directory)
echo "🔧 Setting up infrastructure..."
if ! docker compose -f /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure/docker-compose.yaml up -d; then
  echo "❌ Error: Failed to start infrastructure containers"
  exit 1
fi

# Wait for postgres to be healthy before attempting any queries
POSTGRES_TIMEOUT=30
for i in $(seq 1 $POSTGRES_TIMEOUT); do
  if docker exec 300-Agents-postgres pg_isready -U acme -d orders >/dev/null 2>&1; then
    break
  fi
  if [ $i -eq $POSTGRES_TIMEOUT ]; then
    echo "❌ Error: PostgreSQL failed to start within ${POSTGRES_TIMEOUT}s"
    echo "   Check: docker logs 300-Agents-postgres"
    exit 1
  fi
  sleep 1
done

# Reset sam_gateway database (fixes Alembic migration errors on restarts)
docker exec 300-Agents-postgres psql -U acme -d postgres -c "DROP DATABASE IF EXISTS sam_gateway" >/dev/null 2>&1 || true
docker exec 300-Agents-postgres psql -U acme -d postgres -c "CREATE DATABASE sam_gateway" >/dev/null 2>&1

# Seed only if the orders table is empty or doesn't exist yet
if ! docker exec 300-Agents-postgres psql -U acme -d orders -t -c "SELECT 1 FROM orders LIMIT 1;" 2>/dev/null | grep -q 1; then
  echo "🌱 Seeding database..."
  if ! python /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/seed_orders_db.py; then
    echo "❌ Error: Database seeding failed"
    exit 1
  fi
else
  echo "✅ Database seeded"
fi

# Clean up stale SAM event-mesh-gw queues from broker
# Each SAM restart creates new durable queues with unique UUIDs; old ones accumulate and
# eventually hit the broker's 100-endpoint license limit, preventing startup.
if curl -sf -u admin:admin "http://localhost:8080/SEMP/v2/config/msgVpns/default" >/dev/null 2>&1; then
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
for q in queues:
    if 'gdk/event-mesh-gw' in q['queueName'] or 'gdk/viz' in q['queueName']:
        semp(f'config/msgVpns/default/queues/{urllib.parse.quote(q["queueName"], safe="")}', 'DELETE')
PYTHON
fi

# Install MCP server dependencies in centralized infrastructure location
INFRASTRUCTURE_DIR="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure"
if [ ! -d "$INFRASTRUCTURE_DIR/node_modules" ]; then
  cd "$INFRASTRUCTURE_DIR"
  if ! npm install --silent >/dev/null 2>&1; then
    echo "⚠️  Warning: MCP server dependencies installation had errors (may still work)"
  fi
  cd "$SAM_DIR"
fi

# Point the webui gateway at PostgreSQL to avoid SQLite concurrent-write lock errors
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://acme:acme@localhost:5432/sam_gateway"

# Create /tmp/inventory-reports directory for InventoryManagementAgent MCP filesystem tool
mkdir -p /tmp/inventory-reports

# ----------------------------
# Auto-configure Agents
# ----------------------------
if ! python3 /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/auto_create_agents.py "$SAM_DIR"; then
  echo "❌ Error: Agent configuration failed"
  exit 1
fi

# Start LogisticsAgent (Strands-based external agent)
LOGISTICS_AGENT_DIR="$INFRASTRUCTURE_DIR/logistics_agent"
if [ -d "$LOGISTICS_AGENT_DIR" ]; then
  # Ensure LogisticsAgent is fully stopped (already killed above, but double-check)
  pkill -9 -f "logistics_agent.server" >/dev/null 2>&1 || true
  lsof -ti:8100 | xargs kill -9 >/dev/null 2>&1 || true
  sleep 1
  
  # Check and install Strands dependencies if needed
  STRANDS_MISSING=false
  for pkg in strands fastapi uvicorn psycopg2; do
    if ! python3 -c "import $pkg" >/dev/null 2>&1; then
      STRANDS_MISSING=true
      break
    fi
  done
  
  if [ "$STRANDS_MISSING" = true ]; then
    if ! pip install -q strands-agents strands-agents-tools psycopg2-binary fastapi uvicorn pydantic anthropic boto3; then
      echo "⚠️  Warning: Strands dependencies installation failed"
      echo "   LogisticsAgent may not start correctly"
    fi
  fi
  
  # Start the agent (manages its own logging)
  cd "$INFRASTRUCTURE_DIR"
  nohup python -m logistics_agent.server >/dev/null 2>&1 &
  LOGISTICS_PID=$!
  cd "$SAM_DIR"
  
  # Wait for LogisticsAgent to be ready
  LOGISTICS_READY=false
  for i in {1..30}; do
    if curl -fsS "http://localhost:8100/health" >/dev/null 2>&1; then
      LOGISTICS_READY=true
      break
    fi
    sleep 1
  done
  
  if [ "$LOGISTICS_READY" = false ]; then
    echo "⚠️  Warning: LogisticsAgent not responding on port 8100"
    echo "   SAM will start but LogisticsAgent features may not work"
    echo "   Check: ps aux | grep logistics_agent"
  fi
fi

# Print URL once the UI is reachable
echo "🚀 Starting SAM..."
set +m
(
  until ui_is_up "$PORT"; do
    sleep 1
  done
  echo ""
  echo "✅ SAM UI ready: $UI_URL"
  echo ""
) &

sam run
