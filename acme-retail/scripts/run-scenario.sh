#!/bin/bash
# Dispatcher: routes Simulate Events task choices to the right runner.
# Called by VS Code tasks as: bash ./run-scenario.sh <value>

set -e

case "$1" in
  --test-order-fulfillment)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python \
      -m tests.test_order_fulfillment_parallel
    ;;
  --test-inventory-management)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python \
      -m tests.test_inventory_management_parallel
    ;;
  --test-incident-response)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python \
      -m tests.test_incident_response_parallel
    ;;
  --test-knowledge-query)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python \
      -m tests.test_knowledge_query_parallel
    ;;
  --test-logistics)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python \
      -m tests.test_logistics_parallel
    ;;
  *)
    exec bash ./simulate-events.sh "$@"
    ;;
esac
