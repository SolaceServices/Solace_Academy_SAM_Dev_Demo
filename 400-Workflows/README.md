# Module 400: Workflows

## Overview

This module teaches **multi-agent workflow orchestration** using Solace Agent Mesh (SAM). Students learn to coordinate multiple AI agents in parallel and sequential patterns to accomplish complex business processes that cannot be achieved with event-driven gateway pipelines alone.

**Course Focus:** Building automated workflows that combine data from multiple agents into executive reports, demonstrating real-world enterprise AI orchestration patterns.

---

## Why Workflows?

In Course 300, you built event-driven agent pipelines using gateways. Those pipelines are powerful, but they have real limitations:

- **Gateways are stateless** — they fire, trigger an agent, and forget
- **No scheduling** — gateways only respond to events, never to time
- **No fan-out + merge** — a gateway routes to one agent; it can't query three agents in parallel and combine their results
- **No pause/resume** — a gateway can't wait for a human decision mid-flow
- **No retry/compensation** — if an agent fails, the gateway publishes to an error topic and stops

**Workflows fill exactly these gaps.**

### The Use Case: Morning Briefing

> *Acme Retail's operations manager needs a daily executive summary covering inventory health, open incidents, and any orders stuck in 'blocked' status — automatically compiled and ready in the WebUI when she arrives each morning at 8 AM. No human should have to trigger it.*

This is something the gateway-per-agent pattern from Course 300 **cannot do**. Workflows enable:
- **Scheduled triggers** (cron-style time-based execution)
- **Parallel fan-out** (query 3 agents simultaneously)
- **Data aggregation** (merge multiple agent responses into one report)
- **Artifact persistence** (save the briefing for later review)

---

## Testing the Morning Briefing Workflow
1. Click the  **"Simulate Events"** button at the bottom of the IDE
4. Select **"6️⃣ Morning Briefing Workflow"**

The workflow takes ~30-40 seconds to complete. You'll see:
- ✅ Workflow invoked successfully
- 🆔 Task ID and Session ID
- 🔗 Link to view results in the WebUI

## Learning Objectives

By completing this module, students will understand:

1. **Workflow Architecture:**
   - How SAM workflows differ from gateway-driven event pipelines
   - When to use workflows vs. dynamic orchestration
   - Parallel vs. sequential execution patterns
   - Workflow state management and artifact persistence

2. **Multi-Agent Coordination:**
   - Calling domain agents via OrchestratorAgent proxy
   - Passing data between workflow nodes
   - Merging responses from multiple agents
   - Handling dependencies between workflow steps

3. **Template Expression System:**
   - Accessing workflow inputs: `{{workflow.input.field}}`
   - Referencing node outputs: `{{node_id.output.field}}`
   - Resolving values in agent instructions
   - Common pitfalls and resolution timing

4. **Artifact Management:**
   - Creating persistent workflow outputs
   - Naming artifacts with dynamic values
   - Accessing artifacts via WebUI and API
   - Understanding artifact scope and visibility

5. **Scheduled Execution:**
   - Configuring cron-based triggers via API
   - Managing scheduled tasks (create, list, update, delete)
   - Viewing scheduled task execution history
   - Accessing scheduled artifacts
   - Understanding persistence limitations

---


## Key Concepts & Design Patterns

### 1. Orchestrator as Proxy Pattern

**Why:** Domain agents (InventoryManagementAgent, IncidentResponseAgent, OrderFulfillmentAgent) expect gateway-formatted events, not workflow inputs. They are not designed for direct workflow invocation.

**Solution:** All workflow nodes call `OrchestratorAgent` with natural language instructions. The Orchestrator then calls domain agents via A2A (agent-to-agent communication).

```yaml
# ❌ Direct call (fails - agent expects gateway event format)
- id: query_inventory
  agent_name: "InventoryManagementAgent"

# ✅ Via Orchestrator (works - Orchestrator translates)
- id: query_inventory
  agent_name: "OrchestratorAgent"
  instruction: "Call the InventoryManagementAgent to get inventory..."
```

**Key Point:** The OrchestratorAgent acts as a translation layer between workflow inputs and domain agent expectations.

### 2. Parallel Execution

Nodes with no dependencies run simultaneously, dramatically reducing total execution time.

```yaml
# These 3 nodes run in parallel (concurrent execution):
- id: query_inventory
  # No depends_on field
  
- id: query_incidents
  # No depends_on field
  
- id: query_orders
  # No depends_on field

# This node waits for all 3 to finish (sequential dependency):
- id: merge_results
  depends_on: [query_inventory, query_incidents, query_orders]
```

**Performance Impact:** Parallel execution reduces workflow time from ~60s (sequential) to ~30-40s (parallel).

### 3. Template Expression System

Workflow input values must be resolved in agent instructions using the correct syntax:

```yaml
# In workflow input schema
input:
  briefing_date: "{{workflow.input.trigger_date}}"  # ✅ Resolves at node execution

# In downstream node instruction
instruction: |
  Save with filename "Morning Briefing - {{save_briefing.input.briefing_date}}.md"
  # ↑ References the resolved input field from previous node
```

**Common Mistakes:**
- ❌ Using `{{workflow.input.trigger_date}}` directly in artifact filenames (not resolved in agent context)
- ❌ Using `{{workflow.input.trigger_date}}` in `output_mapping` (resolved too late)
- ✅ Always reference resolved node inputs: `{{node_id.input.field}}`

### 4. Output Schema Overrides

Force agents to return structured JSON that the workflow can reference:

```yaml
output_schema_override:
  type: object
  properties:
    data:
      type: string
      description: "The query results in markdown format"
  required: [data]
```

This ensures you can access outputs via template expressions like `{{node_id.output.data}}`.

**Why This Matters:** Without schema overrides, agents may return free-form text that cannot be reliably parsed by subsequent workflow nodes.

---

## Scheduling Workflows via API

### Using SAM Scheduled Tasks (v1.18.28+)

SAM v1.18.28 introduced a **Scheduled Tasks** feature that allows workflows to run on cron-like schedules via REST API.

**Important Notes:**
- As of SAM v1.18.29, scheduled tasks are managed via API calls
- The WebUI for scheduled tasks is experimental and behind a feature flag
- **Persistence Issue:** The setup script (`300-setup.sh`) drops and recreates the `sam_gateway` database on every restart, which **deletes all scheduled tasks**
- **Workaround:** Save your scheduled task creation commands in a script for easy recreation after restarts

### Creating a Scheduled Task

```bash
curl -X POST http://127.0.0.1:8000/api/v1/scheduled-tasks/ \
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
    "task_message": [
      {
        "type": "text",
        "text": "{}"
      }
    ]
  }'
```

**Key Fields:**
- `schedule_expression`: Cron expression (not `cron_expression`)
- `target_agent_name`: Workflow name (not `agent_name`)
- `task_message`: Array of message parts with workflow input as JSON string
- Empty JSON `{}` in text causes workflow to use today's date for `trigger_date`

**Response:** Returns the created task with an `id` field that you'll use for subsequent operations.

### Managing Scheduled Tasks

**List all scheduled tasks:**
```bash
curl http://127.0.0.1:8000/api/v1/scheduled-tasks/
```

**Get a specific task:**
```bash
curl http://127.0.0.1:8000/api/v1/scheduled-tasks/{task_id}
```

**Update a task:**
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/scheduled-tasks/{task_id} \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_expression": "0 8 * * 1-5",
    "description": "Updated to weekdays at 8 AM"
  }'
```

**Enable/Disable a task:**
```bash
# Enable
curl -X POST http://127.0.0.1:8000/api/v1/scheduled-tasks/{task_id}/enable

# Disable
curl -X POST http://127.0.0.1:8000/api/v1/scheduled-tasks/{task_id}/disable
```

**Delete a task:**
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/scheduled-tasks/{task_id}
```

### Cron Expression Examples

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Daily 6 AM | `0 6 * * *` | Every day at 6:00 AM |
| Weekdays 8 AM | `0 8 * * 1-5` | Monday-Friday at 8:00 AM |
| Hourly | `0 * * * *` | Every hour at :00 minutes |
| Every 30 min | `*/30 * * * *` | Every 30 minutes |
| Every minute (testing) | `* * * * *` | Every minute |

### Viewing Execution History

**Get all executions for a task:**
```bash
curl "http://127.0.0.1:8000/api/v1/scheduled-tasks/{task_id}/executions"
```

**Get recent executions:**
```bash
curl "http://127.0.0.1:8000/api/v1/scheduled-tasks/executions/recent"
```

**Get execution by A2A task ID:**
```bash
curl "http://127.0.0.1:8000/api/v1/scheduled-tasks/executions/by-a2a-task/{a2a_task_id}"
```

**Access scheduled artifacts:**
```bash
curl "http://127.0.0.1:8000/api/v1/artifacts/scheduled/{session_id}/{filename}"
```

---

## Performance & Best Practices

### Execution Metrics

| Phase | Duration | Notes |
|-------|----------|-------|
| Parallel queries | ~18-22s | 3 nodes run concurrently |
| Merge briefing | ~10-15s | LLM formats markdown |
| Save artifact | ~3-5s | Create + persist artifact |
| **Total** | **~30-40s** | End-to-end workflow |

### Resource Usage

- **LLM Calls:** 4 total (3 queries + 1 merge)
- **Database Queries:** ~6-8 (via domain agents)
- **Memory:** ~50MB (workflow state + artifacts)
- **Disk:** ~3-5KB per briefing artifact

### Best Practices

#### 1. Always Use Orchestrator as Proxy

❌ **Don't:**
```yaml
- id: query_inventory
  agent_name: "InventoryManagementAgent"  # Direct call fails
```

✅ **Do:**
```yaml
- id: query_inventory
  agent_name: "OrchestratorAgent"
  instruction: "Call the InventoryManagementAgent to..."
```

#### 2. Override Output Schemas

Always specify `output_schema_override` to ensure structured responses:

```yaml
output_schema_override:
  type: object
  properties:
    data:
      type: string
  required: [data]
```

#### 3. Use Template Expressions Carefully

- ✅ Use `{{workflow.input.field}}` in node `input` blocks
- ✅ Use `{{node_id.input.field}}` in agent instructions
- ✅ Use `{{node_id.output.field}}` in `depends_on` nodes
- ❌ Don't use `{{workflow.input.field}}` in artifact filenames (not resolved)

#### 4. Set Appropriate Timeouts

```yaml
# LLM-heavy nodes
timeout: "120s"

# Simple data transformations
timeout: "30s"

# External API calls or database queries
timeout: "300s"
```

#### 5. Handle Errors Gracefully

Use workflow-level error handlers:

```yaml
on_exit:
  on_failure: log_error_and_notify
  always: cleanup_resources
```

---

## Troubleshooting

### Workflow doesn't start

**Check:** Is SAM running?
```bash
curl http://127.0.0.1:8000/api/v1/config
```

**Fix:** Start SAM:
```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows/sam
sam run
```

### Workflow doesn't execute

**Symptom:** Test script shows "submitted" but workflow never completes.

**Checks:**
1. Verify all domain agents are registered:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/agentCards | grep -E "(InventoryManagement|IncidentResponse|OrderFulfillment)"
   ```

2. Check SAM logs for errors:
   ```bash
   cd /workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows/sam
   tail -100 sam.log | grep -i "error\|exception"
   ```

3. Ensure OrchestratorAgent has agent_discovery enabled:
   ```yaml
   agent_discovery:
     enabled: true  # Required for A2A calls
   ```

### Empty briefing (all sections show "0 items")

**Check:** Is database seeded?
```bash
psql postgresql://acme:acme@localhost:5432/orders -c "SELECT COUNT(*) FROM inventory WHERE status='out_of_stock';"
```

**Fix:** Seed database:
```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts
python3 seed_orders_db.py
```

**Additional checks:**
1. Check MCP server status in agent logs:
   ```bash
   grep -i "mcp" /workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows/sam/sam.log | tail -20
   ```

2. Verify infrastructure is running:
   ```bash
   docker ps | grep -E "(postgres|qdrant)"
   ```

### Workflow times out

**Symptom:** Workflow execution exceeds `max_workflow_execution_time_seconds`.

**Causes:**
1. LLM provider slow/unavailable
2. Database queries hanging
3. MCP tools not responding

**Fixes:**
1. Increase timeouts in workflow YAML:
   ```yaml
   max_workflow_execution_time_seconds: 1200  # 20 minutes
   default_node_timeout_seconds: 300          # 5 minutes
   ```

2. Check LiteLLM proxy health:
   ```bash
   curl -s https://lite-llm.mymaas.net/health
   ```

3. Test database connectivity:
   ```bash
   psql postgresql://acme:acme@localhost:5432/orders -c "SELECT COUNT(*) FROM inventory WHERE status IN ('low_stock', 'out_of_stock');"
   ```

### Can't find artifacts in WebUI

**Option 1:** Toggle "Show hidden working files" in the WebUI artifact view

**Option 2:** Access via filesystem:
```bash
find /tmp/samv2/sam_dev_user -name "Morning Briefing*"
```

**Option 3:** Use API:
```bash
curl http://127.0.0.1:8000/api/v1/artifacts/{session_id}
```

**Note:** Workflow artifacts are sometimes tagged as `__working` (hidden by default) in SAM v1.18.x. This is a known behavior that may be improved in future versions.

### Artifact has wrong filename

**Symptom:** Artifact created as `Morning Briefing - {{workflow.input.trigger_date}}.md`

**Cause:** Template expression not resolved in the instruction.

**Fix:** Ensure the instruction uses `{{save_briefing.input.briefing_date}}` (resolved input field) instead of `{{workflow.input.trigger_date}}` (not resolved in agent context).

### Scheduled task disappeared after SAM restart

**Symptom:** Scheduled task is no longer listed after restarting SAM.

**Cause:** The `Run Course Serup` script drops and recreates the `sam_gateway` database on every run to avoid migration conflicts. This deletes all scheduled tasks.

**Fix:** Recreate the scheduled task using the API command after each SAM restart.

---


## What You Should Have By Now

After completing this module, you should have:

1. ✅ A working Morning Briefing workflow that queries 3 agents in parallel
2. ✅ Understanding of when to use workflows vs. gateways
3. ✅ Knowledge of how to schedule workflows via API
4. ✅ Ability to troubleshoot workflow execution issues
5. ✅ Experience with artifact management and template expressions
6. ✅ Foundation for building your own multi-agent workflows

**Artifact:** `400-Workflows/sam/configs/workflows/acme-morning-briefing-workflow.yaml`

