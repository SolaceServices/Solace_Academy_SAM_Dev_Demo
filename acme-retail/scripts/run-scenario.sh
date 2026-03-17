#!/bin/bash
# Dispatcher: routes Simulate Events task choices to the right runner.
# Called by VS Code tasks as: bash ./run-scenario.sh <value>

set -e

case "$1" in
  --test-order-fulfillment)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python \
      -m tests.test_order_fulfillment
    ;;
  *)
    exec bash ./simulate-events.sh "$@"
    ;;
esac
