#!/bin/bash
# Dispatcher: routes Simulate Events task choices to the right runner.
# Called by VS Code tasks as: bash ./run-scenario.sh <value>

set -e

# Detect which SAM directory is currently running.
#
# Each setup script does: cd "$SAM_DIR" && sam run
# so the running SAM process's working directory IS the SAM directory.
# Detection cascade:
#   1. $SAM_DIR env var if already set (explicit override)
#   2. Running 'sam run' process → read /proc/<pid>/cwd
#   3. Most recently modified sam.log across known directories
#   4. Hard fallback to 300-Agents/sam
_detect_sam_dir() {
    if [ -n "${SAM_DIR:-}" ] && [ -d "${SAM_DIR}" ]; then
        echo "$SAM_DIR"
        return
    fi

    local pid cwd
    pid=$(pgrep -f "sam run" 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null)
        if [ -n "$cwd" ] && [ -d "$cwd" ]; then
            echo "$cwd"
            return
        fi
    fi

    local best_dir="" best_time=0 mtime
    for dir in \
        "/workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins/sam" \
        "/workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows/sam" \
        "/workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam" \
        "/workspaces/Solace_Academy_SAM_Dev_Demo/200-Orchestration/sam"; do
        [ -f "$dir/sam.log" ] || continue
        mtime=$(stat -c %Y "$dir/sam.log" 2>/dev/null || echo 0)
        if [ "$mtime" -gt "$best_time" ]; then
            best_time=$mtime
            best_dir=$dir
        fi
    done
    [ -n "$best_dir" ] && echo "$best_dir" && return

    echo "/workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam"
}

export SAM_DIR
SAM_DIR=$(_detect_sam_dir)

case "$1" in
  --test-order-fulfillment)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_order_fulfillment_parallel
    ;;
  --test-inventory-management)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_inventory_management_parallel
    ;;
  --test-incident-response)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_incident_response_parallel
    ;;
  --test-knowledge-query)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_knowledge_query_parallel
    ;;
  --test-logistics)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_logistics_parallel
    ;;
  --test-morning-briefing-workflow)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_morning_briefing_workflow
    ;;
  --test-email-tool)
    cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
    exec "${SAM_DIR}/.venv/bin/python" -m tests.test_email_tool_parallel
    ;;
  *)
    exec bash ./simulate-events.sh "$@"
    ;;
esac
