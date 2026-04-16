#!/usr/bin/env bash
set -euo pipefail

COURSE_ROOT="${1:-/workspaces/Solace_Academy_SAM_Dev_Demo/200-Orchestration}"
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

if [ ! -f ".venv/.deps_installed" ]; then
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
# Running SAM
# ----------------------------
PORT="$(get_port)"
UI_URL="$(build_ui_url "$PORT")"

# Restart-friendly: free common SAM ports (ignore errors)
for p in 8000 8001 8443; do
  fuser -k "${p}/tcp" >/dev/null 2>&1 || true
done

# Verify Solace Broker container is running
if ! docker ps | grep -q solace; then
  bash ../../.devcontainer/setup-broker.sh >/dev/null 2>&1 &
  spinner $! "🚀 Starting Solace broker..."
  wait $!
  if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to start Solace broker"
    exit 1
  fi
  echo "✅ Solace broker started"
else
  echo "✅ Solace broker running"
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
