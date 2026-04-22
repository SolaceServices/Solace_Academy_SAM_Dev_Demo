#!/usr/bin/env bash
# start_logistics_agent.sh — Start the Strands-based LogisticsAgent on port 8100.
#
# REQUIRED: INFRASTRUCTURE_DIR and SAM_DIR must be set by the caller
# (both are set after sourcing common.sh).

LOGISTICS_AGENT_DIR="$INFRASTRUCTURE_DIR/logistics_agent"

if [ -d "$LOGISTICS_AGENT_DIR" ]; then
  # Double-kill any existing process on port 8100 (already killed in common.sh,
  # but this ensures a clean state immediately before startup)
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

  # Start the agent (inherits environment from sourced .env)
  cd "$INFRASTRUCTURE_DIR"
  nohup python -m logistics_agent.server >/dev/null 2>&1 &
  LOGISTICS_PID=$!
  cd "$SAM_DIR"

  # 30-second health poll
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
