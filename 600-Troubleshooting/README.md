# Course 600: Agent Mesh — Logging and Troubleshooting

## Overview

This course covers debugging and troubleshooting SAM applications. You'll learn where logs are stored, how to configure logging levels, common issues and their solutions, and SAM's built-in debugging tools.

By the end of this course, you'll be able to:
- Locate and read SAM log files
- Configure logging levels and formats
- Debug agent behavior issues
- Troubleshoot event mesh connectivity
- Resolve common configuration problems
- Use SAM's debugging and monitoring tools

## Prerequisites

- Completed **Course 100**, **200**, and **300**
- Working SAM installation with multiple agents
- Familiarity with terminal/command line
- Basic understanding of log analysis

## Quick Setup

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts
bash 600-setup.sh /workspaces/Solace_Academy_SAM_Dev_Demo/600-Troubleshooting
```

## SAM Log Locations

### Primary Log File: `sam.log`

Located in the SAM project directory:

```bash
cat 600-Troubleshooting/sam/sam.log
```

Contains:
- Agent startup/shutdown events
- LLM API calls and responses
- Tool executions
- Error stack traces
- Entry point activity
- A2A protocol messages

### Per-Agent Session Databases

Each agent maintains a SQLite database with conversation history:

```bash
# List all session DBs
ls -lh 600-Troubleshooting/sam/*.db

# Example session DBs
orchestrator.db
acme_knowledge.db
order_fulfillment_agent.db
inventory_management_agent.db
incident_response_agent.db
logistics_agent.db  # (in 300-Agents/sam/)
```

### External Agent Logs

External agents (like LogisticsAgent) have separate logs:

```bash
# LogisticsAgent log
cat 300-Agents/sam/logistics_agent.log
```

### Entry Point Logs

Event mesh entry point activity is in `sam.log`, search for:

```bash
grep "gateway" sam.log
grep "event_mesh" sam.log
```

### Docker Container Logs

Infrastructure services:

```bash
# PostgreSQL logs
docker logs acme-postgres

# Solace broker logs
docker logs solace

# Qdrant logs
docker logs acme-qdrant
```

## Configuring Logging

### Log Levels

SAM supports standard Python logging levels:

- **DEBUG**: Verbose output, all operations
- **INFO**: Normal operations, agent decisions
- **WARNING**: Unexpected but handled situations
- **ERROR**: Errors that prevent operations
- **CRITICAL**: System-level failures

### Update Logging Configuration

Edit `configs/logging_config.yaml`:

```yaml
version: 1
disable_existing_loggers: false

formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: default
    stream: ext://sys.stdout
  
  file:
    class: logging.FileHandler
    level: DEBUG  # Capture everything in file
    formatter: detailed
    filename: sam.log
    mode: a

loggers:
  sam:
    level: DEBUG  # Set overall SAM logging level
    handlers: [console, file]
    propagate: false
  
  sam.agents:
    level: DEBUG  # Agent-specific logging
    handlers: [file]
    propagate: false
  
  sam.gateways:
    level: INFO  # Entry point logging
    handlers: [file]
    propagate: false

root:
  level: WARNING
  handlers: [console, file]
```

### Restart SAM to Apply Changes

```bash
sam run
```

## Reading SAM Logs

### Log Entry Anatomy

```
2026-04-14 10:23:45,123 - sam.agents.OrderFulfillmentAgent - INFO - Processing order ORD-2026-001
```

Components:
- **Timestamp**: `2026-04-14 10:23:45,123`
- **Logger name**: `sam.agents.OrderFulfillmentAgent`
- **Level**: `INFO`
- **Message**: `Processing order ORD-2026-001`

### Useful Grep Patterns

```bash
# Find all errors
grep "ERROR" sam.log

# Find specific agent activity
grep "OrderFulfillmentAgent" sam.log

# Find LLM API calls
grep "litellm" sam.log

# Find tool executions
grep "tool_name" sam.log

# Find entry point events
grep "acme/orders/created" sam.log

# Find exceptions
grep -A 10 "Traceback" sam.log  # Show 10 lines after each traceback
```

### Tail Logs in Real-Time

```bash
# Follow new log entries
tail -f sam.log

# Follow specific agent
tail -f sam.log | grep "OrderFulfillmentAgent"
```

## Common Issues and Solutions

### Issue 1: Agent Not Discovered by Orchestrator

**Symptoms**:
```
User: "What is the status of order ORD-2026-001?"
Orchestrator: "I don't have that capability."
```

**Diagnosis**:
```bash
# Check if agent is registered
grep "discovery" sam.log
grep "agent_card" sam.log
```

**Solutions**:
- Verify `agent_discovery.enabled: true` in agent config
- Check agent name matches exactly (case-sensitive)
- Ensure agent started successfully (no errors in log)
- Restart SAM: `pkill -f "sam run" && sam run`

### Issue 2: Events Not Triggering Agent

**Symptoms**:
- Events published to broker
- No agent response
- No activity in logs

**Diagnosis**:
```bash
# Check if entry point received event
grep "acme/orders/created" sam.log

# Check if default_user_identity is present
grep "default_user_identity" configs/gateways/*.yaml
```

**Solutions**:
- Add `default_user_identity: "anonymous_event_mesh_user"` to EVERY event handler
- Verify topic subscriptions match published topics exactly
- Check entry point `target_agent_name` matches agent `agent_name`
- Verify Solace broker is running: `docker ps | grep solace`

### Issue 3: Tool Execution Failures

**Symptoms**:
```
ERROR - sam.agents.OrderFulfillmentAgent - Tool execution failed: orders_db
```

**Diagnosis**:
```bash
# Find the full error
grep -A 20 "Tool execution failed: orders_db" sam.log
```

**Common Causes**:

**Database not reachable**:
```bash
# Test PostgreSQL connection
psql -h localhost -U acme -d orders -c "SELECT 1"
```

**SQL syntax error**:
```
ERROR - psycopg2.ProgrammingError: column "unknown_field" does not exist
```

Solution: Verify column names with `\d tablename` in psql.

**Tool not properly configured**:
```yaml
# Missing connection_string
tools:
  - tool_type: python
    tool_config:
      tool_name: "orders_db"
      # Missing: connection_string!
```

Solution: Add required parameters.

### Issue 4: LLM Refuses to Use Tools

**Symptoms**:
- Agent responds with text instead of calling tools
- No tool executions in logs

**Diagnosis**:
```bash
# Check if tools are available
grep "Registered tools" sam.log

# Check agent instruction
cat configs/agents/order_fulfillment_agent_agent.yaml | grep -A 20 "instruction"
```

**Solutions**:
- Make instruction ultra-directive: "YOU MUST call X tool"
- Delete stale session DB: `rm order_fulfillment_agent.db`
- Verify tool_description is detailed and clear
- Use a flagship model (Claude 4.5, GPT-5, Gemini-3)
- Restart SAM after changes

### Issue 5: MCP Server Connection Failed

**Symptoms**:
```
ERROR - sam.tools.mcp - Failed to connect to MCP server: Connection refused
```

**Diagnosis**:
```bash
# Check if Node.js is installed
node --version

# Test MCP server directly
node /path/to/mcp_postgres_rw.js postgresql://...
```

**Solutions**:
- Install MCP dependencies: `npm install @modelcontextprotocol/server-postgres`
- Use absolute paths (not relative): `/workspaces/.../mcp_postgres_rw.js`
- Verify PostgreSQL is running: `docker ps | grep postgres`
- Check timeout settings (increase to 30s if needed)

### Issue 6: Broker Queue Accumulation

**Symptoms**:
```
ERROR - sam - NO_MORE_NON_DURABLE_QUEUE_OR_TE
SAM exits immediately on startup
```

**Cause**: Each SAM restart creates new durable queues. Solace Standard Edition caps at 100 endpoints (~45 restarts).

**Solution**: Delete stale queues via SEMP (automated in setup scripts):

```bash
curl -s -u admin:admin "http://localhost:8080/SEMP/v2/monitor/msgVpns/default/queues?count=200" | \
  python3 -c "
import sys,json,urllib.request,urllib.parse,base64
creds=base64.b64encode(b'admin:admin').decode()
for q in json.load(sys.stdin).get('data',[]):
    name=q['queueName']
    if 'gdk/event-mesh-gw' in name or 'gdk/viz' in name:
        req=urllib.request.Request(f'http://localhost:8080/SEMP/v2/config/msgVpns/default/queues/{urllib.parse.quote(name,safe=\"\")}',method='DELETE')
        req.add_header('Authorization',f'Basic {creds}')
        try: urllib.request.urlopen(req)
        except: pass
"
```

### Issue 7: WebUI Entry Point SQLite Lock Errors

**Symptoms**:
```
ERROR - sqlite3.OperationalError: database is locked
```

**Cause**: 3 concurrent SQLite connections to `webui_gateway.db`; large SSE payloads hold write lock too long.

**Solution**: Use PostgreSQL instead of SQLite:

```bash
# Add to .env
WEB_UI_GATEWAY_DATABASE_URL=postgresql://acme:acme@localhost:5432/sam_gateway

# Restart SAM
sam run
```

The `webui.yaml` entry point config already supports this via environment variable.

### Issue 8: External Agent Not Reachable

**Symptoms**:
```
ERROR - sam.tools.a2a - Connection refused: http://localhost:8100
```

**Diagnosis**:
```bash
# Check if LogisticsAgent is running
lsof -i :8100

# Test A2A endpoint
curl http://localhost:8100/.well-known/agent.json
```

**Solutions**:
- Start LogisticsAgent: `python3 -m logistics_agent.server`
- Verify environment variables: `echo $LLM_SERVICE_ENDPOINT`
- Check agent logs: `tail -f logistics_agent.log`
- Ensure port 8100 is not blocked by firewall

## Debugging Tools

### SAM CLI Debug Mode

Run SAM with verbose logging:

```bash
sam run --log-level DEBUG
```

### Interactive Python Debugging

Add breakpoints to custom tools:

```python
# pricing_tool.py

def get_price(self, product_sku: str):
    import pdb; pdb.set_trace()  # Debugger breakpoint
    
    response = requests.get(...)
    return response.json()
```

Run SAM and trigger the tool — execution will pause at the breakpoint.

### Database Query Debugging

Connect to PostgreSQL directly:

```bash
psql -h localhost -U acme -d orders
```

Run queries manually:

```sql
-- Check order status
SELECT order_id, status, created_date FROM orders WHERE order_id = 'ORD-2026-001';

-- Check inventory
SELECT item_id, product_name, available_quantity, status FROM inventory WHERE item_id = 'SKU-LAPTOP-002';

-- Check incidents
SELECT incident_id, type, severity, status FROM incidents WHERE status = 'open';
```

### Broker Message Inspection

Use Solace PubSub+ Manager:

1. Open browser: `http://localhost:8080`
2. Login: admin / admin
3. Navigate to: Message VPN → Try Me!
4. Subscribe to topics: `acme/>`
5. Publish test messages

### Entry Point Debug Mode

Enable detailed entry point logging:

```yaml
# configs/gateways/acme-order-events.yaml

logging:
  level: DEBUG  # Add this
```

Restart SAM and check `sam.log` for detailed entry point activity.

## Performance Troubleshooting

### Issue: Slow Agent Responses

**Diagnosis**:
```bash
# Check LLM API latency
grep "litellm" sam.log | grep "duration"
```

**Solutions**:
- Use faster models for simple tasks
- Reduce max_tokens in agent config
- Enable caching (if supported by provider)
- Use parallel tool execution

### Issue: High Memory Usage

**Diagnosis**:
```bash
# Monitor SAM process
top -p $(pgrep -f "sam run")

# Check session DB sizes
du -sh *.db
```

**Solutions**:
- Delete old session DBs: `rm *.db`
- Reduce conversation history retention
- Use PostgreSQL for WebUI entry point
- Restart SAM periodically

### Issue: Database Connection Pool Exhausted

**Diagnosis**:
```bash
# Check active connections
psql -U acme -d orders -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'orders';"
```

**Solutions**:
- Increase PostgreSQL max_connections
- Use connection pooling in tools
- Close connections after queries
- Check for connection leaks in custom tools

## Best Practices for Debugging

### 1. Start Simple

Isolate the problem:
- Test agent directly (not through entry point)
- Use minimal test data
- Remove external dependencies temporarily

### 2. Check Logs Systematically

Follow this order:
1. SAM startup logs (did all agents initialize?)
2. Agent discovery logs (are agents registered?)
3. Entry point logs (did event arrive?)
4. Tool execution logs (did tool run?)
5. Database logs (did query succeed?)

### 3. Use Timestamps

Correlate events across logs using timestamps:

```bash
# Find events around 10:23:45
grep "2026-04-14 10:23:4" sam.log
grep "2026-04-14 10:23:4" logistics_agent.log
docker logs --since "2026-04-14T10:23:00" acme-postgres
```

### 4. Test Components Independently

Before testing full workflows, verify each component:

```bash
# Test PostgreSQL
psql -U acme -d orders -c "SELECT 1"

# Test Solace broker
docker ps | grep solace

# Test LLM API
curl $LLM_SERVICE_ENDPOINT/v1/models \
  -H "Authorization: Bearer $LLM_SERVICE_API_KEY"

# Test Qdrant
curl http://localhost:6333/collections
```

### 5. Compare Working vs. Broken Configs

If something stops working:

```bash
# Check git history
git log --oneline configs/agents/order_fulfillment_agent_agent.yaml

# Show differences
git diff HEAD~1 configs/agents/order_fulfillment_agent_agent.yaml
```

### 6. Enable Verbose Logging Temporarily

Only when debugging (not in production):

```yaml
# configs/logging_config.yaml

loggers:
  sam:
    level: DEBUG  # Normally INFO

root:
  level: DEBUG  # Normally WARNING
```

Restart SAM, reproduce issue, revert logging level.

## Key Takeaways

### Log Management
- **Primary log**: `sam.log` in SAM project directory
- **Session DBs**: Per-agent SQLite files with conversation history
- **External logs**: Separate logs for external agents (LogisticsAgent)
- **Docker logs**: Use `docker logs` for infrastructure services

### Configuration
- **Logging levels**: DEBUG (verbose) → ERROR (minimal)
- **Log format**: Configure via `configs/logging_config.yaml`
- **Restart required**: Changes take effect on next `sam run`

### Debugging Workflow
1. Reproduce the issue
2. Check sam.log for errors
3. Isolate the failing component (agent, tool, entry point)
4. Test component independently
5. Fix and verify

### Common Patterns
- **Agent not discovered**: Check `agent_discovery.enabled: true`
- **Events not triggering**: Check `default_user_identity` in handlers
- **Tool failures**: Verify configuration and test manually
- **Performance issues**: Check LLM latency, DB connection pools

## Next Steps

In **Course 700: System Design**, you'll:
- Learn best practices for agent mesh architecture
- Design hierarchical multi-level A2A systems
- Implement domain separation patterns
- Scale agent meshes for production

Your agent mesh is now debuggable and maintainable!

## Additional Resources

- Setup script: `600-env-setup.md`
- Log configuration: `configs/logging_config.yaml`
- Troubleshooting reference: `/CLAUDE.md` (Infrastructure Issues section)
- SAM documentation: https://docs.solace.com/agent-mesh/
