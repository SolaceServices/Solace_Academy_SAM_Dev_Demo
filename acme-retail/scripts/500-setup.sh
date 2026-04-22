#!/usr/bin/env bash
set -euo pipefail

COURSE_ROOT="${1:-/workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins}"
SAM_DIR="$COURSE_ROOT/sam"
INFRASTRUCTURE_DIR="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SAM_DIR"

# shellcheck disable=SC1091
source "$SCRIPTS_DIR/common.sh"

# ----------------------------
# EMAIL SERVICE SETUP (Module 500 only)
# ----------------------------
EMAIL_SERVICE_DIR="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/services"
EMAIL_SERVICE_PID_FILE="/tmp/email-service.pid"

# Stop any existing email service
if [ -f "$EMAIL_SERVICE_PID_FILE" ]; then
  OLD_PID=$(cat "$EMAIL_SERVICE_PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$EMAIL_SERVICE_PID_FILE"
fi
fuser -k 3000/tcp >/dev/null 2>&1 || true

cd "$EMAIL_SERVICE_DIR"
if [ ! -d "node_modules" ]; then
  if ! npm install --silent >/dev/null 2>&1; then
    echo "⚠️  Warning: Email service npm install had errors (may still work)"
  fi
fi

PORT=3000 node email-service.js </dev/null >/tmp/email-service.log 2>&1 &
EMAIL_SERVICE_PID=$!
echo $EMAIL_SERVICE_PID > "$EMAIL_SERVICE_PID_FILE"

EMAIL_SERVICE_TIMEOUT=10
for i in $(seq 1 $EMAIL_SERVICE_TIMEOUT); do
  if curl -fsS "http://localhost:3000/health" >/dev/null 2>&1; then
    echo "✅ Email service running (PID: $EMAIL_SERVICE_PID)"
    echo "   Inbox: http://localhost:3000"
    break
  fi
  if [ $i -eq $EMAIL_SERVICE_TIMEOUT ]; then
    echo "⚠️  Warning: Email service did not respond within ${EMAIL_SERVICE_TIMEOUT}s"
    echo "   Check logs: tail -f /tmp/email-service.log"
  fi
  sleep 1
done

cd "$SAM_DIR"

# ----------------------------
# Auto-configure Agents and Gateways
# ----------------------------
if ! python3 /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/auto_create_agents.py "$SAM_DIR"; then
  echo "❌ Error: Agent configuration failed"
  return 1
fi

# ----------------------------
# Enable Scheduler Service in WebUI Gateway (Module 500 only)
# ----------------------------
WEBUI_GATEWAY="$SAM_DIR/configs/gateways/webui.yaml"

if [ -f "$WEBUI_GATEWAY" ]; then
  python3 - "$WEBUI_GATEWAY" <<'PYTHON_SCHEDULER'
import sys
import re

webui_file = sys.argv[1]

with open(webui_file, 'r') as f:
    content = f.read()

if 'scheduler_service:' in content:
    content = re.sub(
        r'(scheduler_service:\s*\n\s*)enabled:\s*false',
        r'\1enabled: true',
        content
    )
else:
    scheduler_config = '''
      # --- Scheduler Service Configuration ---
      scheduler_service:
        enabled: true
        check_interval_seconds: 60
        stale_execution_timeout_seconds: 3600
        leadership_lease_seconds: 300
'''
    pattern = r'(background_tasks:\s*\n\s*default_timeout_ms:[^\n]*\n)'
    replacement = r'\1' + scheduler_config
    content = re.sub(pattern, replacement, content)

with open(webui_file, 'w') as f:
    f.write(content)
PYTHON_SCHEDULER

  echo "✅ Scheduler service enabled in WebUI gateway"
else
  echo "⚠️  Warning: WebUI gateway configuration not found at $WEBUI_GATEWAY"
fi

# ----------------------------
# Generate Morning Briefing Workflow (Module 500 only)
# ----------------------------
WORKFLOW_DIR="$SAM_DIR/configs/workflows"
mkdir -p "$WORKFLOW_DIR"

cat > "$WORKFLOW_DIR/acme-morning-briefing-workflow.yaml" <<'EOF'
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: acme-morning-briefing-workflow.log

apps:
  - name: acme_morning_briefing_workflow
    app_module: solace_agent_mesh.workflow.app
    broker:
      broker_type: solace
      broker_url: ${SOLACE_BROKER_URL}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
      broker_vpn: ${SOLACE_BROKER_VPN}
    app_config:
      namespace: ${NAMESPACE}
      name: "AcmeMorningBriefingWorkflow"
      max_workflow_execution_time_seconds: 900
      default_node_timeout_seconds: 120
      session_service:
        type: "memory"
        default_behavior: "PERSISTENT"
      artifact_service:
        type: "filesystem"
        base_path: "/tmp/samv2"
        artifact_scope: namespace
      agent_card_publishing:
        interval_seconds: 60
      agent_discovery:
        enabled: true
      workflow:
        description: "Daily executive briefing combining inventory alerts, open incidents, and blocked orders"
        version: "1.0.0"
        input_schema:
          type: object
          properties:
            trigger_date:
              type: string
              description: "Date for the briefing (YYYY-MM-DD format)"
          required: [trigger_date]
        output_schema:
          type: object
          properties:
            briefing_content:
              type: string
              description: "The complete morning briefing in markdown format"
          required: [briefing_content]

        nodes:
          - id: query_inventory
            type: agent
            agent_name: "OrchestratorAgent"
            input:
              task: "Get inventory status report"
            output_schema_override:
              type: object
              properties:
                response:
                  type: string
                  description: "Plain text response with inventory data"
              required: [response]
            instruction: |
              Call the InventoryManagementAgent to get a complete list of all inventory items that currently have low_stock or out_of_stock status. Include the SKU, product name, current available quantity, and reorder level for each item.

              Provide the information as plain text in the response field.
              If the agent is unavailable or returns an error, set response to: 'UNAVAILABLE'.
            timeout: "60s"
            on_error:
              action: continue
              default_output:
                response: "UNAVAILABLE"

          - id: query_incidents
            type: agent
            agent_name: "OrchestratorAgent"
            input:
              task: "Get open incidents report"
            output_schema_override:
              type: object
              properties:
                response:
                  type: string
                  description: "Plain text response with incident data"
              required: [response]
            instruction: |
              Call the IncidentResponseAgent to get a complete list of all incidents with status 'open' or 'investigating'. Include the incident ID, type, severity, status, and a brief description for each incident.

              Provide the information as plain text in the response field.
              If the agent is unavailable or returns an error, set response to: 'UNAVAILABLE'.
            timeout: "60s"
            on_error:
              action: continue
              default_output:
                response: "UNAVAILABLE"

          - id: query_orders
            type: agent
            agent_name: "OrchestratorAgent"
            input:
              task: "Get blocked orders report"
            output_schema_override:
              type: object
              properties:
                response:
                  type: string
                  description: "Plain text response with blocked order data"
              required: [response]
            instruction: |
              Call the OrderFulfillmentAgent to get a complete list of all orders currently in 'blocked' status. Include the order ID, customer ID, and the reason the order is blocked.

              Provide the information as plain text in the response field.
              If the agent is unavailable or returns an error, set response to: 'UNAVAILABLE'.
            timeout: "60s"
            on_error:
              action: continue
              default_output:
                response: "UNAVAILABLE"

          - id: merge_briefing
            type: agent
            agent_name: "OrchestratorAgent"
            depends_on: [query_inventory, query_incidents, query_orders]
            input:
              inventory_data: "{{query_inventory.output.response}}"
              incidents_data: "{{query_incidents.output.response}}"
              orders_data: "{{query_orders.output.response}}"
              briefing_date: "{{workflow.input.trigger_date}}"
            output_schema_override:
              type: object
              properties:
                briefing_text:
                  type: string
                  description: "The complete briefing text in markdown format"
              required: [briefing_text]
            instruction: |
              Create an executive morning briefing in MARKDOWN format using the following structure.

              # Acme Retail Morning Briefing — {{workflow.input.trigger_date}}

              ## 📦 INVENTORY ALERTS (X items)

              [For each low_stock or out_of_stock item from inventory_data:]
              - **SKU-XXX-XXX**: [Product Name] — **[STATUS]** ([available quantity] units[if low_stock: , reorder level: X])

              ## 🚨 OPEN INCIDENTS (X)

              [For each open/investigating incident from incidents_data:]
              - **[Incident ID]**: [Type] — [Brief description] `[Severity / Status]`

              ## ⛔ BLOCKED ORDERS (X)

              [For each blocked order from orders_data:]
              - **[Order ID]**: [Customer ID] — blocked waiting on [item causing blockage]

              ## ⚠️ ACTION REQUIRED

              [Summary of high-priority items requiring immediate attention.]

              Output the complete briefing markdown as the briefing_text field.
              Do NOT create any artifacts in this step.
            timeout: "120s"

          - id: create_briefing_artifact
            type: agent
            agent_name: "OrchestratorAgent"
            depends_on: [merge_briefing]
            input:
              briefing_text: "{{merge_briefing.output.briefing_text}}"
              briefing_date: "{{workflow.input.trigger_date}}"
            output_schema_override:
              type: object
              properties:
                filename:
                  type: string
                  description: "The filename of the created artifact"
              required: [filename]
            instruction: |
              Create a markdown artifact with the morning briefing:
              - Filename: "Morning Briefing - {{workflow.input.trigger_date}}.md"
              - Content: The complete briefing text from the briefing_text input
              - Do NOT add the "__working" tag
              - Description: "Daily executive briefing for {{workflow.input.trigger_date}}"

              After creating the artifact, output the filename in the filename field.
            timeout: "60s"

        output_mapping:
          briefing_content: "{{merge_briefing.output.briefing_text}}"
EOF

echo "✅ Morning briefing workflow configured"

# shellcheck disable=SC1091
source "$SCRIPTS_DIR/start_logistics_agent.sh"

# Print URL once the UI is reachable and create scheduled task
echo "🚀 Starting SAM..."
set +m
(
  until ui_is_up "$PORT"; do
    sleep 1
  done
  echo ""
  echo "✅ SAM UI ready: $UI_URL"
  echo ""

  sleep 5

  echo "📅 Creating scheduled task: Daily Morning Briefing..."

  SCHEDULED_TASK_RESPONSE=$(curl -sS -X POST "http://127.0.0.1:${PORT}/api/v1/scheduled-tasks/" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Daily Morning Briefing",
      "description": "Automated executive briefing at 6:00 AM daily",
      "schedule_type": "cron",
      "schedule_expression": "0 6 * * *",
      "timezone": "America/New_York",
      "target_agent_name": "AcmeMorningBriefingWorkflow",
      "target_type": "agent",
      "enabled": true,
      "task_message": [{"type": "text", "text": "{}"}]
    }' 2>&1)

  if [ $? -eq 0 ] && echo "$SCHEDULED_TASK_RESPONSE" | grep -q '"id"'; then
    echo "✅ Scheduled task created successfully"
  else
    echo "⚠️  Warning: Failed to create scheduled task"
    echo "   Response: $SCHEDULED_TASK_RESPONSE"
    echo "   You can create it manually using the SAM UI or API"
  fi
  echo ""
) &

sam run
