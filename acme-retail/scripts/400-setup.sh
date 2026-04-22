#!/usr/bin/env bash
set -euo pipefail

# Bug fix: was 400-Evals (directory does not exist)
COURSE_ROOT="${1:-/workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows}"
SAM_DIR="$COURSE_ROOT/sam"
INFRASTRUCTURE_DIR="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SAM_DIR"

# shellcheck disable=SC1091
source "$SCRIPTS_DIR/common.sh"

# Auto-configure agents and gateways
if ! python3 /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/auto_create_agents.py "$SAM_DIR"; then
  echo "❌ Error: Agent configuration failed"
  return 1
fi

# shellcheck disable=SC1091
source "$SCRIPTS_DIR/start_logistics_agent.sh"

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
