# Course 700: Agent Mesh — Agentic System Design

## Overview

This final course focuses on **architecture and best practices** for designing production-ready agent mesh systems. You'll learn hierarchical design patterns, domain separation strategies, scaling considerations, and how to structure multi-level A2A systems.

By the end of this course, you'll understand:
- Best practices for agent mesh architecture
- Hierarchical multi-level A2A system design
- Domain separation and ownership patterns
- Scaling strategies for production deployments
- Security and governance considerations
- Migration from POC to production

## Prerequisites

- Completed all previous courses (100-600)
- Built and tested the complete Acme Retail agent mesh
- Understanding of event-driven architecture
- Familiarity with enterprise system design

## The Architecture Spectrum

### Monolithic Orchestrator (Simple)

```
User → Orchestrator → All Tools → Database
```

**Pros**:
- Simple to understand
- Easy to debug
- Low latency

**Cons**:
- Single point of failure
- No specialization
- Scaling limitations
- All logic in one place

**Use When**: Prototype, single domain, <5 capabilities

### Flat Agent Mesh (Moderate)

```
User → Orchestrator ← A2A → [Agent A, Agent B, Agent C, Agent D]
                                ↓         ↓         ↓         ↓
                              Tool A    Tool B    Tool C    Tool D
```

**Pros**:
- Domain specialization
- Parallel execution
- Independent scaling
- Clear responsibility boundaries

**Cons**:
- Orchestrator knows all agents
- No sub-delegation
- Flat coordination model

**Use When**: 5-20 specialized agents, single organization level

**This is what you built in Course 300.**

### Hierarchical Agent Mesh (Advanced)

```
User → Orchestrator A → A2A → Orchestrator B → A2A → [Agent X, Agent Y]
                     ↘ A2A → Orchestrator C → A2A → [Agent Z, Agent W]
                                              ↘ A2A → Orchestrator D → [...]
```

**Pros**:
- Scalable to 100+ agents
- Multi-level delegation
- Regional/domain hierarchy
- Team ownership boundaries

**Cons**:
- Complex to debug
- Higher latency (multi-hop)
- Requires careful design

**Use When**: Enterprise-scale, multiple teams, >20 agents

## Domain-Driven Design for Agent Meshes

### Core Principle: Domain Ownership

Each agent owns **exactly one domain** and is the single source of truth for that domain.

#### Good Domain Separation (Acme Retail)

| Agent | Domain | Owns | Never Touches |
|-------|--------|------|--------------|
| OrderFulfillmentAgent | Order lifecycle | orders, order_items | inventory, incidents, shipments |
| InventoryManagementAgent | Stock levels | inventory | orders, incidents, shipments |
| IncidentResponseAgent | Incident lifecycle | incidents, incident_items | orders, inventory, shipments |
| LogisticsAgent | Shipment tracking | shipments, shipment_events | orders, inventory, incidents |
| AcmeKnowledge | Knowledge retrieval | (Qdrant collection) | (no database writes) |

**Key Pattern**: Agents publish **facts** (domain state changes), not commands.

#### Publishing Facts, Not Commands

**Good (Fact)**:
```
InventoryManagementAgent publishes:
Topic: acme/inventory/updated
Payload: {"item_id": "SKU-TABLET-055", "available_quantity": 50, "status": "in_stock"}
```

Other agents subscribe and decide what to do with this fact:
- OrderFulfillmentAgent: "Stock is now available, re-validate blocked orders"
- IncidentResponseAgent: "Stock sufficient, move incident to 'monitoring'"

**Bad (Command)**:
```
InventoryManagementAgent publishes:
Topic: acme/commands/revalidate-orders
Payload: {"command": "revalidate", "item_id": "SKU-TABLET-055"}
```

This violates domain separation — InventoryManagementAgent shouldn't know about OrderFulfillmentAgent's logic.

### The Single Incident Creator Pattern

**Rule**: Only ONE agent creates incident records.

**Why**: Prevents duplicates, inconsistent escalation, and data corruption.

**Implementation (Acme Retail)**:
- IncidentResponseAgent is the **sole incident creator**
- Other agents publish domain facts
- IncidentResponseAgent subscribes and decides what's incident-worthy

**Example Flow**:
```
OrderFulfillmentAgent validates order → blocked (insufficient stock)
  ↓ publishes fact
acme/orders/decision: {"order_id": "ORD-001", "status": "blocked", "reason": "insufficient_stock"}
  ↓ subscribed by
IncidentResponseAgent receives event
  ↓ decision logic
"Blocked order = inventory shortage = high severity incident"
  ↓ creates
incidents table: INSERT INTO incidents (type='inventory_shortage', severity='high', ...)
  ↓ publishes
acme/incidents/created: {"incident_id": "INC-2026-042", "type": "inventory_shortage", ...}
```

**Anti-Pattern**: OrderFulfillmentAgent creates incident directly → violates domain separation.

## Event Schema Design

### Schema Consistency

All events on a topic should follow the same schema:

```yaml
# acme/orders/decision schema (consistent)
{
  "order_id": "ORD-2026-001",
  "status": "validated" | "blocked",
  "reason": "string (optional)",
  "timestamp": "ISO8601",
  "total": 123.45
}
```

**Benefits**:
- Predictable for consumers
- Easy to validate
- Supports versioning

### Schema Evolution

When adding fields:

```yaml
# Version 1
{
  "order_id": "ORD-001",
  "status": "validated"
}

# Version 2 (backward compatible)
{
  "order_id": "ORD-001",
  "status": "validated",
  "priority": "standard"  # New field, optional
}
```

**Backward Compatibility Rules**:
- New fields must be optional
- Don't remove existing fields
- Don't change field types
- Use schema version field: `"schema_version": "2.0"`

### Topic Naming Convention

Follow a consistent hierarchy:

```
{company}/{domain}/{entity}/{action}

Examples:
acme/orders/created
acme/orders/decision
acme/inventory/updated
acme/incidents/created
acme/incidents/response
acme/logistics/updated
```

**Benefits**:
- Wildcard subscriptions: `acme/orders/>`
- Clear ownership: `acme/domain/...`
- Hierarchical organization

## Hierarchical System Design

### When to Use Hierarchy

Use multi-level orchestrators when:
- **Scale** exceeds 20 agents
- **Teams** own different agent groups
- **Regions** require local coordination
- **Complexity** requires sub-delegation

### Example: Multi-Region Retail

```
Global Orchestrator
  ├─ North America Orchestrator
  │    ├─ US Orders Agent
  │    ├─ US Inventory Agent
  │    └─ US Logistics Agent
  ├─ Europe Orchestrator
  │    ├─ EU Orders Agent
  │    ├─ EU Inventory Agent
  │    └─ EU Logistics Agent
  └─ APAC Orchestrator
       ├─ APAC Orders Agent
       ├─ APAC Inventory Agent
       └─ APAC Logistics Agent
```

**Benefits**:
- Regional autonomy
- Reduced global orchestrator complexity
- Localized error handling
- Team ownership boundaries

### Delegation Depth

**General Rule**: Keep delegation to ≤3 levels.

**Why**: Each level adds latency and complexity.

```
Level 1: Global Orchestrator (route to region)
Level 2: Regional Orchestrator (route to domain)
Level 3: Domain Agent (execute task)
```

Beyond 3 levels, consider flattening or restructuring.

## Scaling Strategies

### Horizontal Scaling (More Agents)

Add agent instances for the same domain:

```
OrderFulfillmentAgent Instance 1 (handles 50% of orders)
OrderFulfillmentAgent Instance 2 (handles 50% of orders)
```

**Load Balancing**:
- Solace broker round-robins messages across instances
- Agents must be stateless (no shared memory)
- Use sticky sessions for stateful workflows

**Configuration**:
```yaml
# Both instances use identical config
agent_name: "OrderFulfillmentAgent"
instance_id: "${INSTANCE_ID}"  # Set via environment
```

### Vertical Scaling (Bigger Agents)

Increase agent resources:

```yaml
# Agent runtime config
max_workers: 4  # Number of concurrent tasks
max_tokens: 32000  # Larger context window
```

**When to Use**:
- Complex reasoning tasks
- Multi-step workflows
- Large context requirements

### Partitioning (Domain Sharding)

Split domain by partition key:

```
OrderFulfillmentAgent-US (handles US orders)
OrderFulfillmentAgent-EU (handles EU orders)
OrderFulfillmentAgent-APAC (handles APAC orders)
```

**Routing Logic**:
```python
# Entry point determines partition
if order['region'] == 'US':
    target_agent = "OrderFulfillmentAgent-US"
elif order['region'] == 'EU':
    target_agent = "OrderFulfillmentAgent-EU"
```

**Benefits**:
- Data locality (EU data stays in EU)
- Regulatory compliance (GDPR)
- Reduced blast radius (US outage doesn't affect EU)

## Security and Governance

### Authentication and Authorization

**Agent-to-Agent (A2A)**:
```yaml
# configs/agents/order_fulfillment_agent.yaml

security:
  authentication:
    type: "oauth2"
    token_endpoint: "${AUTH_TOKEN_ENDPOINT}"
    client_id: "${ORDER_AGENT_CLIENT_ID}"
    client_secret: "${ORDER_AGENT_CLIENT_SECRET}"
```

**Event Mesh**:
```yaml
# configs/gateways/acme-order-events.yaml

default_user_identity: "service-account-orders"  # Not anonymous in production!
```

Use service accounts with least-privilege permissions.

### Data Privacy

**PII Handling**:
- Never log sensitive data (credit cards, SSNs)
- Redact PII in events: `"customer_name": "[REDACTED]"`
- Encrypt at rest (database encryption)
- Encrypt in transit (TLS for all connections)

**Agent Instructions**:
```yaml
instruction: |
  SECURITY RULE: Never include full credit card numbers or SSNs in responses.
  Mask sensitive data: 1234-****-****-5678.
```

### Audit Logging

Track all agent actions:

```python
# In custom tools
def query_orders(self, order_id: str):
    audit_log.info(f"Agent {agent_id} queried order {order_id} by user {user_id}")
    
    result = db.query(...)
    return result
```

Store audit logs separately from operational logs for compliance.

### Rate Limiting

Prevent abuse:

```yaml
# Agent config
rate_limits:
  max_requests_per_minute: 60
  max_concurrent_requests: 10
```

Entry point-level rate limiting:

```yaml
# Entry point config
rate_limit:
  requests_per_second: 100
  burst: 200
```

## Production Migration Checklist

### Infrastructure

- [ ] Move from SQLite to PostgreSQL (all entry points)
- [ ] Use managed Solace PubSub+ (not Docker)
- [ ] Deploy Qdrant cluster (not single node)
- [ ] Set up load balancers for Web UI
- [ ] Configure auto-scaling for agent instances

### Security

- [ ] Replace anonymous users with service accounts
- [ ] Enable TLS for all connections (Solace, PostgreSQL, Qdrant)
- [ ] Rotate API keys and secrets
- [ ] Set up secret management (AWS Secrets Manager, HashiCorp Vault)
- [ ] Enable audit logging
- [ ] Configure firewall rules (least-privilege)

### Monitoring

- [ ] Set up log aggregation (ELK, Splunk, CloudWatch)
- [ ] Configure metrics (Prometheus, Grafana)
- [ ] Set up alerting (PagerDuty, Opsgenie)
- [ ] Create dashboards (agent health, latency, error rates)
- [ ] Configure distributed tracing (Jaeger, OpenTelemetry)

### Testing

- [ ] Run full test suite (all 5 tests)
- [ ] Perform load testing (100x normal traffic)
- [ ] Test failover scenarios (agent crashes, DB outages)
- [ ] Validate error handling (network failures, LLM timeouts)
- [ ] Security testing (penetration, vulnerability scans)

### Documentation

- [ ] Architecture diagrams (Mermaid, draw.io)
- [ ] Agent runbooks (startup, shutdown, recovery)
- [ ] Incident response procedures
- [ ] Deployment guides
- [ ] Troubleshooting playbooks

## Anti-Patterns to Avoid

### 1. God Orchestrator

**Anti-Pattern**: Orchestrator contains all business logic.

**Symptom**: Orchestrator instruction is 1000+ lines.

**Solution**: Push logic to specialized agents.

### 2. Chatty Agents

**Anti-Pattern**: Agents make 10+ A2A calls per task.

**Symptom**: High latency, cascading failures.

**Solution**: Batch operations, use caching, denormalize data.

### 3. Circular Dependencies

**Anti-Pattern**: Agent A calls Agent B calls Agent A.

**Symptom**: Infinite loops, deadlocks.

**Solution**: Hierarchical design, one-way dependencies.

### 4. Shared Mutable State

**Anti-Pattern**: Multiple agents modify the same database table.

**Symptom**: Race conditions, data corruption.

**Solution**: Domain ownership, event-driven updates.

### 5. Ignoring Failures

**Anti-Pattern**: No error handling, silent failures.

**Symptom**: Operations partially complete, inconsistent state.

**Solution**: Comprehensive error handling, idempotent operations, compensating transactions.

## Key Design Principles

### 1. Single Responsibility

Each agent has one clear purpose:
- OrderFulfillmentAgent: Order lifecycle
- InventoryManagementAgent: Stock management
- IncidentResponseAgent: Incident lifecycle

### 2. Loose Coupling

Agents communicate via events, not direct calls:
- Publish facts, not commands
- Subscribe to domains, not specific agents
- Use topic hierarchies for organization

### 3. Domain Ownership

Each agent owns one domain:
- Exclusive write access to domain tables
- Single source of truth for domain data
- Publishes domain state changes

### 4. Idempotency

Operations should be safe to retry:
```python
# Idempotent: can run multiple times safely
UPDATE orders SET status = 'validated' WHERE order_id = 'ORD-001'

# Not idempotent: creates duplicate
INSERT INTO orders (order_id, status) VALUES ('ORD-001', 'validated')
```

### 5. Graceful Degradation

System continues functioning when components fail:
- Circuit breakers for LLM API calls
- Fallback to cached data when DB is down
- Queue events for later processing when agent is offline

## Performance Optimization

### Caching Strategies

```python
# Tool-level caching
@lru_cache(maxsize=100)
def get_product_price(sku: str):
    return db.query(f"SELECT price FROM products WHERE sku = '{sku}'")
```

Cache duration depends on data volatility:
- Product prices: 1 hour
- Inventory levels: 5 minutes
- Order status: No caching (real-time)

### Database Query Optimization

```sql
-- Bad: Full table scan
SELECT * FROM orders WHERE status = 'validated'

-- Good: Index on status
CREATE INDEX idx_orders_status ON orders(status)
SELECT order_id, customer_name, total FROM orders WHERE status = 'validated'
```

Use `EXPLAIN` to analyze query plans.

### Parallel Tool Execution

```yaml
# Agent config
tools_parallel: true  # Execute independent tools concurrently
```

**Before** (sequential):
```
get_order_details() → 200ms
get_customer_info() → 150ms
get_shipment_status() → 100ms
Total: 450ms
```

**After** (parallel):
```
get_order_details()    → 200ms
get_customer_info()    → 150ms  } All concurrent
get_shipment_status()  → 100ms
Total: 200ms (max of all)
```

## Key Takeaways

### Architecture Patterns
- **Flat mesh**: 5-20 agents, single coordination level
- **Hierarchical mesh**: 20+ agents, multi-level delegation
- **Domain sharding**: Regional/partition-based separation

### Design Principles
- **Single Responsibility**: One agent, one domain
- **Loose Coupling**: Events, not direct calls
- **Domain Ownership**: Exclusive write access
- **Idempotency**: Safe to retry operations
- **Graceful Degradation**: Continue functioning when components fail

### Production Readiness
- **Security**: Service accounts, TLS, audit logs, rate limits
- **Monitoring**: Logs, metrics, alerts, dashboards, tracing
- **Testing**: Unit, integration, load, failover scenarios
- **Documentation**: Architecture, runbooks, procedures

### Anti-Patterns to Avoid
- God Orchestrator (all logic in one place)
- Chatty Agents (too many A2A calls)
- Circular Dependencies (A calls B calls A)
- Shared Mutable State (race conditions)
- Ignoring Failures (silent errors)

## Congratulations!

You've completed the **Solace Certified Agent Mesh Developer** certification path!

You now have the skills to:
- Design and build event-driven agent mesh systems
- Create specialized agents using multiple methods
- Integrate tools and external services
- Test and evaluate agent behavior
- Debug and troubleshoot production issues
- Scale systems for enterprise deployments

### Next Steps

- Apply these patterns to your own projects
- Contribute to the SAM community
- Explore advanced topics (multi-cloud, edge deployments, federated learning)
- Share your learnings with your team

### Stay Connected

- SAM Documentation: https://docs.solace.com/agent-mesh/
- Solace Community: https://solace.community/
- GitHub: https://github.com/SolaceLabs/

**Thank you for completing this certification series!**

## Additional Resources

- Setup script: `700-env-setup.md`
- Full project documentation: `/FINAL_MASTER_GUIDE.md`
- Architecture reference: `/CLAUDE.md`
- All course guides: `/[100-700]-*/README.md`
