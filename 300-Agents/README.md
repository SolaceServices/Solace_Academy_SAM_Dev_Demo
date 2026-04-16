# Course 300: Agent Mesh — Creating AI Agents

## Overview

In this course, you'll build **5 specialized agents** for the Acme Retail use case using **5 different creation methods**:

1. **AcmeKnowledgeAgent** (RAG Agent) — Added from SAM plugin catalog
2. **OrderFulfillmentAgent** — Created via CLI
3. **InventoryManagementAgent** — Created via GUI with MCP tools
4. **IncidentResponseAgent** — Created with AI assistant (Context7)
5. **LogisticsAgent** — Integrated from an existing framework (external agent via A2A)

By the end of this course, you'll have a complete event-driven agent mesh that:
- Answers questions about company policies (RAG)
- Processes orders and checks inventory availability
- Manages stock levels and generates reorder recommendations
- Creates and escalates incidents automatically
- Tracks shipments and detects delays

## What You'll Learn

### Conceptual Knowledge
- How agents work in event-driven systems
- The agent lifecycle (discovery, registration, execution)
- Agent-to-Agent (A2A) protocol
- Event mesh gateways and topic routing
- Domain ownership patterns

### Technical Skills
- Adding catalog agents
- Creating agents via CLI and GUI
- Using AI assistants with Context7 for SAM development
- Integrating external agents
- Configuring SQL database tools
- Using MCP (Model Context Protocol) servers
- Creating event mesh gateways
- Publishing and subscribing to event topics

### Integration Patterns
- How agents communicate through Solace Platform
- Sequential event chains (inventory update → order revalidation)
- Cross-domain event handling (logistics delay → incident creation)
- Error handling and incident escalation

## Prerequisites

- Completed **Course 100** and **Course 200**
- Working SAM installation with `.env.config` file
- Basic understanding of PostgreSQL and SQL queries
- Familiarity with YAML configuration

## Quick Setup

We've included some setup automation to make our lives easier going forward, so as long as you've completed course `100-Environment-Installation` and created a `.env.config` file, setting up your environment this time is much simpler. 

At the bottom of your code editor, click the `Run Course Setup` button, then select `300-Agents` from the drop down list. 
#### This will:
- automatically activate the virtual environment
- install the dependencies
- initalize sam using the configurations we added to the `.env.config` file previously.

Alternatively, you can run these commands:
```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents
bash ../acme-retail/scripts/300-setup.sh /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents
```

Once it's running, access the Web UI by naigating to the "Ports" tab and click the web icon next to port `8000`


## The 5 Agents You'll Build

### 1. AcmeKnowledgeAgent (RAG)

**Purpose**: Answer questions about company policies, procedures, and guidelines

**Key Features**:
- Ingests markdown documents
- Converts documents to vector embeddings
- Performs semantic search across company knowledge base
- Returns contextual answers with source citations


### 2. OrderFulfillmentAgent

**Purpose**: Process orders, check inventory, manage order lifecycle

**Key Features**:
- Validates new orders against inventory availability
- Saves orders as `validated` (stock sufficient) or `blocked` (out of stock)
- Re-validates blocked orders when inventory is restocked
- Updates order status through the fulfillment lifecycle
- Handles order cancellations


### 3. InventoryManagementAgent

**Purpose**: Monitor stock levels, apply adjustments, generate reorder recommendations

**Key Features**:
- Queries inventory by SKU, category, supplier, warehouse, or status
- Applies stock adjustments (shipments received, damage write-offs)
- Auto-updates status: `in_stock`, `low_stock`, `out_of_stock`
- Generates reorder recommendations for items below reorder_level
- Creates inventory reports and charts (saved to `/tmp/inventory-reports/`)


### 4. IncidentResponseAgent

**Purpose**: Create, track, and escalate incidents across the organization

**Key Features**:
- Creates incidents from domain events (blocked orders, system errors, delays)
- Auto-escalates high-severity incidents to `investigating` status
- Moves incidents to `monitoring` when underlying issues are resolved
- Deduplicates incidents (prevents creating duplicates for the same issue)
- Tracks incident lifecycle: `open` → `investigating` → `monitoring` → `resolved`


### 5. LogisticsAgent (Strands External Agent)

**Purpose**: Track shipments, log delays, detect delivery issues

**Key Features**:
- Tracks shipments by tracking number or order ID
- Updates shipment status through delivery lifecycle
- Logs delays and recalculates estimated delivery dates
- Detects shipments past their estimated delivery time
- Provides status reports filtered by shipment status

## The Agent Lifecycle - Understand How Agents Work in an Event-Driven System

### Traditional Request-Response Pattern

```
API Call → Agent → Response
```

- Synchronous execution
- Tight coupling between caller and agent
- Agent must be available at call time

### Event-Driven Pattern (SAM)

```
Event Published → Broker → Agent Subscribed → Agent Processes → Result Published
```

- Asynchronous execution
- Loose coupling (producers don't know consumers)
- Agents can be added/removed without breaking the system

### Agent Startup Sequence

When an agent starts:

1. **Initialization**: Load configuration, connect to tools
2. **Discovery**: Broadcast an "Agent Card" to the mesh
3. **Registration**: Orchestrator adds agent to available capabilities
4. **Subscription**: Gateway subscribes to topics on agent's behalf
5. **Ready**: Agent listens for A2A protocol messages

### The Agent Card

Every agent publishes a digital "business card" describing:
- **Identity**: Name, version, description
- **Capabilities**: What input/output modes it supports (text, JSON, files)
- **Skills**: Specific tasks it can perform
- **Contact Info**: How to reach it (HTTP endpoint for external agents)

The orchestrator uses this information to decide when to involve each agent.

## Event Mesh Architecture

The **event mesh** is the communication backbone that connects all agents.

### Key Components

**Solace Broker**
- Routes events between publishers and subscribers
- Supports dynamic topic routing
- Provides guaranteed delivery and deduplication

**Event Mesh Gateways**:
- Subscribe to event topics
- Call agents via A2A protocol when events arrive
- Publish agent responses back to topics

**Topics**:
- `acme/orders/created` — New order submitted
- `acme/inventory/updated` — Stock levels changed
- `acme/orders/decision` — Order validation result
- `acme/incidents/created` — New incident escalated
- `acme/logistics/updated` — Shipment status changed

### Domain Ownership Pattern

Each agent owns **one domain** and publishes **facts**:

| Agent | Owns | Publishes to |
|-------|------|-----------|
| OrderFulfillmentAgent | Order status lifecycle | `acme/orders/decision` |
| InventoryManagementAgent | Inventory quantities & status | `acme/inventory/updated` |
| LogisticsAgent | Shipment tracking & status | `acme/logistics/updated` |
| IncidentResponseAgent | **All incident records** | `acme/incidents/created`, `acme/incidents/response` |


## Building Agents

The following sections walk through creating each agent step-by-step.

### Agent 1: AcmeKnowledgeAgent

#### What is RAG?

**Retrieval-Augmented Generation** combines:
- **Retrieval**: Search a knowledge base for relevant documents
- **Generation**: Use an LLM to answer questions based on retrieved content

#### Step 1: Add the Plugin

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam
source .venv/bin/activate
sam plugin add acme_knowledge --plugin sam-rag
```

Or use the GUI:

```bash
sam plugin catalog
```

Select `sam-rag`, name it `acme_knowledge`, click Install.

#### Step 2: Configure Document Path

Open `configs/agents/acme_knowledge.yaml` and find the `scanner` section.

Add to your `.env` file:

```bash
DOCUMENTS_PATH="/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/data/knowledge/"
```

This points the agent to the markdown files in `/acme-retail/data/knowledge/`.

#### Step 3: Verify  Qdrant Vector Database is reachable

```bash
docker ps  # Verify qdrant/qdrant:latest is running
docker compose up -d  # If not running
```

This docker container spins up when you click the `Run Course Setup` button > 300-Agents 

#### Step 4: Configure Embedding Model

Check available models:

```bash
set -a && source .env && set +a
curl $LLM_SERVICE_ENDPOINT/v1/models \
  -H "Authorization: Bearer $LLM_SERVICE_API_KEY"
```

Look for models with "embed" in the name (e.g., `text-embedding-ada-002`, `text-embedding-3-small`), and make a note of it.

Find the embedding dimension:

```bash
curl -X POST $LLM_SERVICE_ENDPOINT/v1/embeddings \
  -H "Authorization: Bearer $LLM_SERVICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-ada-002",
    "input": "test"
  }' | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Embedding dimension: {len(data[\"data\"][0][\"embedding\"])}')"
```

Then add these to your `.env.config` file:

```bash
OPENAI_API_ENDPOINT=${LLM_SERVICE_ENDPOINT}
OPENAI_API_KEY=${LLM_SERVICE_API_KEY}
OPENAI_MODEL_NAME="vertex-claude-4-5-sonnet"
OPENAI_EMBEDDING_MODEL="<YOUR EMBEDDING MODEL>"
QDRANT_URL="http://localhost:6333"
QDRANT_API_KEY=
QDRANT_COLLECTION="acme-retail-knowledge"
QDRANT_EMBEDDING_DIMENSION="<YOUR EMBEDDING DIMENSION>"
```



#### Step 5: Restart SAM

- Kill the running process (ctrl + c), `pkill -f "sam run"`, or quit the terminal window
- Click `Run Course Setup` > 300-Agents

The RAG agent will automatically:
- Scan the knowledge directory
- Convert documents to embeddings
- Store them in Qdrant
- Be ready to answer questions

#### Step 6: Test the Agent

In the Web UI, ask:

*"What are the shipping label requirements for Acme Retail?"*

The agent should retrieve relevant policy documents and answer based on their content.

#### Troubleshooting

- **"docker network already exists"**: Run `docker network prune`
- **Qdrant version mismatch**: Run `pip install --upgrade qdrant-client`
- **No documents found**: Verify `DOCUMENTS_PATH` points to `/acme-retail/data/knowledge/`

---

### Agent 2: OrderFulfillmentAgent

This agent demonstrates the quickest way to scaffold a new agent.

#### Step 1: Create Agent Template

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam
source .venv/bin/activate
sam add agent order_fulfillment_agent
```

When prompted:

```
Enter namespace (e.g., myorg/dev, or leave for ${NAMESPACE}) [${NAMESPACE}]:
Enable streaming support? [Y/n]: y
Enter model type (planning, general, image_gen, report_gen, multimodal, gemini_pro)
[general]: general
Enter agent instruction [...]:
Artifact service type [...] [use_default_shared_artifact]: filesystem
Artifact service base path [/tmp/samv2]:
Artifact service scope (namespace, app, custom) [namespace]: app
Artifact handling mode (ignore, embed, reference) [reference]:
Enable embed resolution? [Y/n]: y
Enable artifact content instruction? [Y/n]: y
Agent card description [A helpful AI assistant.]: An Agent responsible for order fulfillment that can process new orders, check order status, update order status, and cancel orders.
Agent card default input modes (comma-separated) [text]: text, json
Agent card default output modes (comma-separated) [text,file]: text, file, json
Agent card skills (JSON array string) [[]]:
Enable agent discovery? [Y/n]: y
Agent card publishing interval (seconds) [10]:
Inter-agent allow list (comma-separated) []:
Inter-agent deny list (comma-separated) []:
Inter-agent timeout (seconds) [600]: 60
Tools configuration (JSON string of list) [[]]:
```

This generates `configs/agents/order_fulfillment_agent_agent.yaml`.

#### Step 2: Add Skills

Open the generated YAML and add skills under `agent_card:`:

```yaml
skills:
  - id: process_order
    name: process_order
    description: Validate and process new customer orders with inventory checks
  - id: check_order_status
    name: check_order_status
    description: Query current order status and fulfillment progress
  - id: update_order_status
    name: update_order_status
    description: Update order status and emit status change events
  - id: cancel_order
    name: cancel_order
    description: Process order cancellation and update inventory
  - id: query_orders
    name: query_orders
    description: Query and filter orders by status, customer, date range, or priority
```

Skills tell the orchestrator what this agent can do.

#### Step 3: Add SQL Database Tool

Verify the SQL plugin is installed:

```bash
pip show sam-sql-database-tool
```

Add the tools section:

```yaml
tools:
  - tool_type: python
    component_module: "sam_sql_database_tool.tools"
    component_base_path: .
    class_name: "SqlDatabaseTool"
    tool_config:
      tool_name: "orders_db"
      tool_description: >
        Query the Acme Retail orders database. Use this tool for ALL data lookups
        including orders and order items. Supports both SELECT queries and 
        data-modifying statements (INSERT, UPDATE) for order lifecycle management.
        IMPORTANT: This tool has access ONLY to the orders and order_items tables.
        Do NOT attempt to access inventory, incidents, shipments, or other tables.
      connection_string: "${ORDERS_DB_CONNECTION_STRING, postgresql://acme:acme@localhost:5432/orders}"
```

#### Step 4: Configure the Instruction

Replace the default instruction:

```yaml
instruction: |
  You are an Order Fulfillment Agent responsible for processing customer orders, managing order lifecycles, and coordinating with inventory and logistics systems.

  Your primary responsibilities:
  1. Handle new orders by checking inventory availability and saving each order with status 'validated' if stock is sufficient, or 'blocked' if not.
  2. Track and update order status as orders progress through the fulfillment lifecycle (pending → validated → processing → shipped → delivered) — but only advance status in response to explicit lifecycle events.
  3. Handle order cancellations by updating the order status to 'cancelled'.
  4. Query orders by status, customer, date range, or other criteria.
  5. React to inventory update events to re-validate blocked orders when stock becomes available, updating their status to 'validated'.
  6. React to shipment delay events by updating the estimated_delivery field ONLY. Do not create incident records — the IncidentResponseAgent is solely responsible for incident creation.
  
  DOMAIN RESTRICTION: You have access ONLY to the orders and order_items tables. Never attempt to modify inventory, incidents, or shipments tables.
```


#### Step 5: Start SAM and Test
- Kill the running process (ctrl + c), `pkill -f "sam run"`, or quit the terminal window
- Click `Run Course Setup` > 300-Agents

In the Web UI, ask:

*"What is the status of order ORD-2026-001?"*

The agent should query the database and return the order status.

#### Step 6: Add Event Mesh Gateway

Create the gateway that connects events to this agent:

```bash
sam plugin add acme-order-events --plugin sam-event-mesh-gateway
```

Open `configs/gateways/acme-order-events.yaml`.

Replace the inline shared_config block with:

```yaml
!include ../shared_config.yaml
```

Update the broker config:

```yaml
event_mesh_broker_config:
  broker_url: ${SOLACE_BROKER_URL}
  broker_username: ${SOLACE_BROKER_USERNAME, admin}
  broker_password: ${SOLACE_BROKER_PASSWORD, admin}
  broker_vpn: ${SOLACE_BROKER_VPN, default}
```

Add event handlers (see `/300-Agents/sam/configs/gateways/acme-order-events.yaml` for complete config).

#### Every event handler needs:

```yaml
default_user_identity: "anonymous_event_mesh_user"
```

Without this, SAM silently discards events (no error, agent just never responds).

#### Step 7: Restart and Test Events

- Kill the running process (ctrl + c), `pkill -f "sam run"`, or quit the terminal window
- Click `Run Course Setup` > 300-Agents

Click the "Simulate Events" button > `2. Order fullfilment` to test your agent is now event enabled.

---

### Agent 3: InventoryManagementAgent

This agent demonstrates GUI agent creation and integrating MCP tools.

#### What is MCP?

**Model Context Protocol** is an open standard that lets AI agents connect to external tool servers:
- **MCP Postgres**: Query and update PostgreSQL databases
- **MCP Filesystem**: Read and write files
- **Custom MCP servers**: Build your own integrations

Instead of writing a custom Python plugin, you point SAM at an MCP server and it automatically discovers available tools.

#### Step 1: Launch the GUI

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam
source .venv/bin/activate
sam add agent --gui
```

If you see the initialization page instead of the agent config page, add `?config_mode=addAgent` to the URL.

#### Step 2: Configure Agent Details

- **Agent Name**: `inventory_management_agent`
- **Display Name**: Inventory Management Agent
- **Input Modes**: text, json
- **Output Modes**: text, json, file
- **Enable Agent Discovery**: Yes
- **Inter-Agent Timeout**: 60 seconds

#### Step 3: Add the Instruction

```
You are an Inventory Management Agent responsible for monitoring Acme Retail's product inventory, processing stock adjustments, and notifying other agents of stock level changes.

The inventory table has these columns: item_id, product_name, category, stock_quantity, reserved_quantity, available_quantity, reorder_level, reorder_quantity, unit_cost, unit_price, warehouse_location, supplier_id, supplier_name, last_restocked, expected_restock_date, status, incident_id.

Your primary responsibilities:
1. Query inventory levels for individual SKUs, categories, suppliers, or warehouse locations using SELECT queries on the inventory table.
2. Apply stock adjustments when new stock arrives or quantities change: execute a SINGLE UPDATE query that sets stock_quantity, available_quantity, last_restocked, AND status all at once — never split this into two queries. Compute status inline with a CASE expression: 'out_of_stock' when the new available_quantity = 0, 'low_stock' when new available_quantity > 0 and <= reorder_level, 'in_stock' when new available_quantity > reorder_level.
3. Identify items needing reorder by finding rows where available_quantity <= reorder_level, and produce reorder recommendations using each item's reorder_quantity as the suggested order size.
4. Generate inventory reports and charts on demand — by category, warehouse, supplier, or status — and save report files to /tmp/inventory-reports/.
5. Only modify the inventory table. Never insert, update, or delete rows in any other table (orders, shipments, incidents, etc.).

Data integrity rule: All quantities, product names, and status values in responses must come directly from query results. Never estimate, round, paraphrase, or recall values from memory. When reporting stock levels, always use available_quantity (not stock_quantity) as the measure of usable stock.
```

**Why the detailed instruction?**:
- MCP postgres doesn't inject schema context automatically (unlike SqlDatabaseTool)
- Listing columns prevents hallucination of non-existent fields
- The "SINGLE UPDATE" directive prevents race conditions
- Data integrity rule prevents LLM from making up numbers

Then add a description to the agent card
```
An Agent responsible for monitoring and managing Acme Retail's product inventory. This agent checks stock levels, processes adjustments, identifies reorder needs, and publishes inventory update events to the order fulfillment pipeline.
```

#### Step 4: Add Skills

```yaml
skills:
  - id: check_inventory
    name: check_inventory
    description: Query stock levels by SKU, category, supplier, or warehouse location
  - id: adjust_stock
    name: adjust_stock
    description: Apply stock adjustments and update inventory status
  - id: reorder_recommendations
    name: reorder_recommendations
    description: Identify items below reorder level and generate suggested purchase quantities
  - id: inventory_report
    name: inventory_report
    description: Generate inventory reports and charts
```

#### Step 5: Add Builtin Tool

Add `create_chart_from_plotly_config` (for generating inventory charts).

Save the agent.

#### Step 6: Understanding MCP Tools

**MCP (Model Context Protocol)** is an open standard that lets AI agents connect to external tool servers. Instead of writing a custom Python plugin, we can point SAM at any MCP-compatible server and it will automatically discover the tools that server exposes.

Think of it like an API for agent capabilities. The same MCP server could serve multiple agents, or be swapped out entirely without touching agent code.

**Infrastructure Setup**:
- MCP servers were **pre-installed in `acme-retail/infrastructure/`** when you ran the automated environment set up
- You need to create the directory where the agent will save inventory reports:

```bash
mkdir -p /tmp/inventory-reports
```

We're using `/tmp` because it's a standard temporary file location that exists on all systems. The MCP filesystem server will be restricted to only access files within this directory — it's sandboxed by design.

**The Two MCP Tools**:

1. **Custom PostgreSQL MCP Server** (`mcp_postgres_rw.js`):
   - The standard Postgres MCP server is **read-only**
   - Our pre-installed version allows read-write access (necessary for UPDATE statements)
   - Exposes a single tool: `query` (accepts any SQL statement)


From the agent's perspective, all tools—builtins, Python plugins, and MCP servers—look identical. They're just functions the LLM can call. The difference is only in how they're configured and where the logic runs.

#### Step 7: Add MCP Tools to Config

Open `configs/agents/inventory_management_agent_agent.yaml` and add the MCP tools below the builtin tools:

```yaml
tools:
  - tool_type: builtin-group
    group_name: artifact_management
  
  - tool_type: builtin
    tool_name: create_chart_from_plotly_config
  
  # Custom read-write MCP Postgres server
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "node"
      args:
        - "./mcp_postgres_rw.js"
        - "postgresql://acme:acme@localhost:5432/orders"
      timeout: 30
    tool_name_prefix: "postgres"
  
  # MCP Filesystem server (sandboxed to /tmp/inventory-reports)
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "./node_modules/.bin/mcp-server-filesystem"
      args:
        - "/tmp/inventory-reports"
      timeout: 30
    tool_name_prefix: "filesystem"
    allow_list:
      - "write_file"
      - "read_file"
      - "list_directory"
```

**Configuration Details**:
- **timeout: 30**: Gives MCP servers enough time to process queries
- **allow_list**: Restricts filesystem server to only the 3 tools we nee
- **tool_name_prefix**: Namespaces tools to avoid conflicts (e.g., `postgres_query`, `filesystem_write_file`)

#### Step 8: Restart SAM and Test

- Kill the running process (ctrl + c), `pkill -f "sam run"`, or quit the terminal window
- Click `Run Course Setup` > 300-Agents

Ask the agent:

*"What is the current stock level for SKU-LAPTOP-002?"*

The agent should query the inventory table and return the available_quantity.

---

### Agent 4: IncidentResponseAgent

This agent demonstrates using an AI coding assistant with up-to-date SAM documentation.

#### Why Context7?

Traditional AI coding assistants answer from whatever data they were trained on, which isnt always the most up-to-date. **Context7** connects to live documentation, ensuring accurate and current answers.

Context7 is an MCP server that queries documentation in real-time.

#### Step 1: Install OpenCode

OpenCode is a CLI tool that integrates with Context7 and works with various LLM providers:

```bash
sudo npm install -g opencode-ai@1.3.2
```

#### Step 2: Configure OpenCode

**For standard LLM providers (OpenAI, Anthropic, Google):**

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam
opencode
```

Type `/connect`, select your provider, enter your API key.

Type `/models` to select your model.

Exit OpenCode and create `opencode.json` in the `300-Agents` directory:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "local",
      "command": ["npx", "-y", "@upstash/context7-mcp"],
      "enabled": true
    }
  }
}
```

**For LiteLLM proxy users:**
If you're using a LiteLLM proxy, the `/connect` flow won't work because the proxy key isn't a real provider key. Instead, exit OpenCode and open your config file. Add this block, replacing the baseURL and apiKey with your proxy's values if they differ from the course defaults:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "litellm/vertex-claude-4-5-sonnet",
  "provider": {
    "litellm": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LiteLLM",
      "options": {
        "baseURL": "https://lite-llm.mymaas.net",
        "apiKey": "******************"
      },
      "models": {
        "vertex-claude-4-5-sonnet": {
          "name": "Claude 4.5 Sonnet (via LiteLLM)",
          "limit": { "context": 200000, "output": 65536 }
        }
      }
    }
  },
  "mcp": {
    "context7": {
      "type": "local",
      "command": ["npx", "-y", "@upstash/context7-mcp"],
      "enabled": true
    }
  }
}
```

#### Step 3: Verify Context7

Launch OpenCode and type `/status`.

You should see: `1 MCP` (confirming Context7 is connected).

#### Step 4: Create the Agent

**IMPORTANT**: Always start prompts with `use context7 for solace-agent-mesh`.

Without this, OpenCode answers from training data (potentially stale).

Run this prompt:

```
use context7 for solace-agent-mesh

Read configs/agents/order_fulfillment_agent_agent.yaml to understand the project
patterns, then create a new agent config for an IncidentResponseAgent that uses
SqlDatabaseTool to connect to postgresql://acme:acme@localhost:5432/orders and
handles creating, querying, updating and resolving incidents in the incidents and
incident_items tables.

The incidents table has columns: incident_id, type, severity, status, title,
description, created_date, last_updated, resolved_date, root_cause, supplier_id.
The incident_items table has: id, incident_id, item_id, product_name, quantity_short.

The agent must include escalation logic: severity='high' should set status='investigating'.
The agent must generate incident_id values using this SQL pattern:
SELECT COALESCE(MAX(CAST(SPLIT_PART(incident_id, '-', 3) AS INTEGER)), 0) + 1 AS next_num
FROM incidents WHERE incident_id LIKE 'INC-' || to_char(NOW(), 'YYYY') || '-%'

After creating an incident, the agent MUST return a JSON response with these fields:
incident_id, type, severity, status, title, description, created_date
```

OpenCode will generate `configs/agents/incident_response_agent_agent.yaml`.

#### Step 5: Create the Gateway

```
use context7 for solace-agent-mesh

Read configs/gateways/acme-order-events.yaml then create
configs/gateways/acme-incidents-events.yaml routing these
topics to IncidentResponseAgent:

- acme/orders/decision → if order blocked, create inventory_shortage incident (severity=high)
- acme/logistics/updated → if shipment delayed, create shipment_delay incident (severity=medium)
- acme/inventory/updated → if stock sufficient, update linked incidents to status='monitoring'
- acme/inventory/errors → create system_error incident (severity=high)
- acme/orders/errors → create system_error incident (severity=high)
- acme/logistics/errors → create system_error incident (severity=high)

Requirements:
- default_user_identity goes inside each handler block, not app level
- Use static output topics: static:acme/incidents/created (for new), static:acme/incidents/response (for updates)
- Error topic: static:acme/incidents/errors
- gateway_id must be unique: use "incident-gw-01"
- All handlers must end with "Return a JSON response with the incident details"
```

OpenCode will generate `configs/gateways/acme-incidents-events.yaml`.

#### Step 6: Review and Adjust

Always review AI-generated configs:
- Verify tool configurations
- Check topic routing
- Ensure default_user_identity is present
- Validate escalation logic

#### Step 7: Test

- Kill the running process (ctrl + c), `pkill -f "sam run"`, or quit the terminal window
- Click `Run Course Setup` > 300-Agents

In the Web UI, ask:

*"How many orders do we currently have in transit?"*

The agent should query the database and return the order status.

Click the "Simulate Events" button > `4. Incident Response` to test your agent is now event enabled.

The IncidentResponseAgent should:
1. Detect the blocked order
2. Create an `inventory_shortage` incident
3. Set severity=high, status=investigating
4. Publish to `acme/incidents/created`

---

### Agent 5: LogisticsAgent

This section demonstrates how to integrate a **pre-existing external agent** into your SAM project. In real-world scenarios, you'll often need to connect to agents built and maintained by third parties, different teams, or using alternative frameworks.

#### What is an External Agent?

Unlike SAM-native agents that run inside SAM's runtime, **external agents**:
- Run as independent services (separate processes)
- Can be built with any framework (Strands, LangChain, AutoGen, custom code)
- Communicate via the **A2A (Agent-to-Agent) protocol**
- Are discovered automatically by SAM
- Can be deployed, scaled, and managed independently

#### The LogisticsAgent

For this course, a **LogisticsAgent has already been built** using the Strands framework and is included in the project at `/acme-retail/infrastructure/logistics_agent/`. 

This simulates receiving an agent from:
- A third-party vendor
- Another development team
- An external partner organization
- A legacy system wrapper

**What the LogisticsAgent Does**:
- Tracks shipments by tracking number or order ID
- Updates shipment status through the delivery lifecycle
- Logs delays and recalculates estimated delivery dates
- Detects delayed shipments
- Provides status reports


**Key Points**:
- Runs as a standalone HTTP service on **port 8100**
- Exposes **A2A discovery endpoints**
- SAM's **A2A Proxy** discovers it automatically (no hardcoded references)
- Built with **Strands framework** (but could be any framework supporting A2A)

#### Infrastructure Setup

When you ran the automated course setup up withthe `Run Course Setup` button it already installed and configured the LogisticsAgent. For the purpose of this course we'll pretend it exists outside our project - so you don't need to build or code the agent,just integrate it

#### Step 1: Verify LogisticsAgent is Running

Check that the external agent is accessible:

```bash
# Verify the agent is running on port 8100
curl http://localhost:8100/health
```

You should see: `{"status":"ok"}`

Check the agent card (A2A discovery endpoint):

```bash
curl http://localhost:8100/.well-known/agent.json
```

This returns the agent's capabilities:

```json
{
  "name": "LogisticsAgent",
  "displayName": "Logistics Agent",
  "description": "Tracks shipments and manages delivery status",
  "version": "1.0.0",
  "capabilities": {"text": true, "json": true},
  "defaultInputModes": ["text", "json"],
  "defaultOutputModes": ["text", "json"],
  "skills": [
    {"id": "track_shipment", "name": "Track Shipment"},
    {"id": "get_shipments_for_order", "name": "Get Shipments for Order"},
    {"id": "get_status_report", "name": "Get Status Report"},
    {"id": "detect_delays", "name": "Detect Delays"},
    {"id": "update_status_with_event", "name": "Update Status"},
    {"id": "log_shipment_delay", "name": "Log Delay"}
  ],
  "url": "http://localhost:8100"
}
```

This is how SAM discovers what the agent can do—no hardcoded configuration needed!

#### Step 2: Understanding the A2A Protocol

The **Agent-to-Agent (A2A) protocol** enables SAM to discover and communicate with external agents.


**Discovery Flow**:
```
1. SAM makes GET request → http://localhost:8100/.well-known/agent.json
2. Agent returns capabilities (skills, input/output modes)
3. SAM registers agent in orchestrator's available capabilities
4. When user needs logistics help, orchestrator routes to LogisticsAgent
5. SAM makes POST request → http://localhost:8100/ with task message
6. LogisticsAgent processes and returns response
```

**Benefits**:
- No tight coupling between SAM and external agent
- Agent can be updated independently (as long as A2A contract is maintained)
- Multiple SAM instances can use the same external agent
- External agent can be written in any language/framework

**Six Available Tools**:
1. `track_shipment` — Lookup by tracking number
2. `get_shipments_for_order` — Lookup by order ID
3. `get_status_report` — Filter by status
4. `detect_delays` — Find delayed shipments
5. `update_status_with_event` — Change shipment status
6. `log_shipment_delay` — Record delay and recalculate ETA

#### Step 3: Create A2A Proxy Configuration

Now that you understand how the LogisticsAgent works, let's integrate it with SAM. First, navigate to the agents config directory:

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/configs/agents/
```

Create a new file called `a2a.yaml`. This file will hold references to any proxied agents we might want to add in the future:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: a2a_proxy.log

!include ../shared_config.yaml

apps:
  - name: a2a-proxy-app
    app_module: solace_agent_mesh.agent.proxies.a2a.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      artifact_service: *default_artifact_service
      proxied_agents:
        - name: "LogisticsAgent"
          url: "http://localhost:8100"
          discovery_interval_seconds: 5
```

**Configuration Details**:
- **name**: "LogisticsAgent" — Must match the external agent's name
- **url**: "http://localhost:8100" — Where the external agent is running
- **discovery_interval_seconds**: 5 — How often SAM checks the agent's capabilities

This tells SAM there's an agent at localhost:8100 and to fetch its capabilities and register it.

#### Step 4: Update Environment Variables

Add the following to your `.env` file (or `.env.config` for reuse across modules):

```bash
# LogisticsAgent Database
ORDERS_DB_CONNECTION_STRING="postgresql://acme:acme@localhost:5432/orders"
WEB_UI_GATEWAY_DATABASE_URL="postgresql://acme:acme@localhost:5432/sam_gateway"
```

**That's all you need to let SAM discover and use the agent!**

#### Step 5: Create Event Gateway for LogisticsAgent

Just like the other agents, LogisticsAgent needs an event gateway to react to real time logistics events.

Create a new file here: `configs/gateways/acme-logistics-events.yaml`:

Add the agent's content

```yaml
!include ../shared_config.yaml

gateway_id: "logistics-gw-01"
gateway_type: "event_mesh"

event_mesh_broker_config:
  broker_url: ${SOLACE_BROKER_URL}
  broker_username: ${SOLACE_BROKER_USERNAME, admin}
  broker_password: ${SOLACE_BROKER_PASSWORD, admin}
  broker_vpn: ${SOLACE_BROKER_VPN, default}

app:
  event_handlers:
    # Handle shipment creation events
    - name: "shipment_created_handler"
      default_user_identity: "anonymous_event_mesh_user"
      subscriptions:
        - topic: "acme/logistics/shipment-created"
          qos: 1
      input_expression: >
        template:New shipment created. Track this shipment and confirm it's in the system.
        Shipment details: {{text://input.payload}}
      payload_encoding: "utf-8"
      payload_format: "json"
      target_agent_name: "LogisticsAgent"
      on_success: "logistics_updated_publisher"
      on_error: "error_handler"
    
    # Handle status change events
    - name: "status_changed_handler"
      default_user_identity: "anonymous_event_mesh_user"
      subscriptions:
        - topic: "acme/logistics/status-changed"
          qos: 1
      input_expression: >
        template:Update shipment status.
        Tracking: {{text://input.payload:tracking_number}}
        New status: {{text://input.payload:new_status}}
        Location: {{text://input.payload:location}}
      payload_encoding: "utf-8"
      payload_format: "json"
      target_agent_name: "LogisticsAgent"
      on_success: "logistics_updated_publisher"
      on_error: "error_handler"
    
    # Handle shipment delay events  
    - name: "shipment_delayed_handler"
      default_user_identity: "anonymous_event_mesh_user"
      subscriptions:
        - topic: "acme/logistics/shipment-delayed"
          qos: 1
      input_expression: >
        template:Shipment delayed.
        Tracking: {{text://input.payload:tracking_number}}
        New ETA: {{text://input.payload:new_estimated_delivery}}
        Reason: {{text://input.payload:reason}}
      payload_encoding: "utf-8"
      payload_format: "json"
      target_agent_name: "LogisticsAgent"
      on_success: "logistics_updated_publisher"
      on_error: "error_handler"

  output_handlers:
    # Publish logistics update events
    - name: "logistics_updated_publisher"
      topic_expression: "static:acme/logistics/updated"
      payload_expression: "task_response:text"
      payload_encoding: "utf-8"
      payload_format: "json"
    
    # Error handler
    - name: "error_handler"
      topic_expression: "static:acme/logistics/errors"
      payload_expression: "task_response:text"
      payload_encoding: "utf-8"
      payload_format: "json"
```

#### Step 6: Restart SAM and Verify Discovery

Restart SAM to load the new configurations:

- Kill the running process (ctrl + c), `pkill -f "sam run"`, or quit the terminal window
- Click `Run Course Setup` > 300-Agents

Check the logs for successful discovery:

```bash
grep "LogisticsAgent" sam.log
```

You should see:
```
INFO - Discovered external agent: LogisticsAgent at http://localhost:8100
INFO - Registered agent skills: track_shipment, get_shipments_for_order, get_status_report, detect_delays, update_status_with_event, log_shipment_delay
```

#### Step 7: Verify Discovery in Web UI

Open the SAM Web UI and navigate to **Agents**. You should see **LogisticsAgent** listed alongside your other agents.

Click on LogisticsAgent to see its details:
- **Skills**: track_shipment, get_shipments_for_order, get_status_report, detect_delays, update_status_with_event, log_shipment_delay
- **Input Modes**: text, json
- **Output Modes**: text, json
- **Status**: Active

This confirms SAM successfully discovered the external agent via the A2A protocol!

#### Step 8: Test the Integration

Ask the orchestrator:

*"Track shipment 1Z999AA10123456791"*

**Expected Flow**:
1. Orchestrator receives request
2. Recognizes this is a logistics task (based on LogisticsAgent's skills)
3. Routes request to LogisticsAgent via A2A protocol
4. Makes POST request to `http://localhost:8100/` with task message
5. LogisticsAgent queries PostgreSQL shipments table
6. Returns shipment details (status, location, estimated delivery, events)
7. Orchestrator presents results to user

**Key Takeaway**: The integration is **completely transparent**—from the user's perspective, LogisticsAgent works exactly like SAM-native agents. The orchestrator handles all the A2A communication automatically.

---

## Testing Your Agents

### Manual Testing (Web UI)

Test each agent through the orchestrator:

**AcmeKnowledge**:
```
What are Acme Retail's shipping label requirements?
```

**OrderFulfillmentAgent**:
```
What is the status of order ORD-2026-001?
```

**InventoryManagementAgent**:
```
What is the current stock level for SKU-LAPTOP-002?
```

**IncidentResponseAgent**:
```
Show me all open incidents with high severity.
```

**LogisticsAgent**:
```
What is the status of shipment 1Z999AA10123456791?
```

### Event-Driven Testing

1. Click the **task icon** in the status bar
2. Select **"Simulate Events"**
3. Choose a scenario:
   - Order Fulfillment → Publishes `acme/orders/created`
   - Inventory Management → Publishes `acme/suppliers/restock-received`
   - Incident Response → Publishes `acme/orders/decision`
   - Logistics → Publishes `acme/logistics/shipment-delayed`
   - Knowledge Query → Publishes `acme/knowledge/query`

## Common Issues and Troubleshooting

### Issue: Agent not discovered by orchestrator

**Symptoms**: Orchestrator says "I don't have that capability" when asked to delegate

**Solutions**:
- Verify `agent_discovery.enabled: true` in agent config
- Check agent name matches exactly (case-sensitive)
- Restart SAM: `pkill -f "sam run" && sam run`
- Check agent skills are defined

### Issue: Events not triggering agent

**Symptoms**: Events published but agent never responds

**Solutions**:
- Verify `default_user_identity: "anonymous_event_mesh_user"` in EVERY event handler
- Check topic subscriptions match published topics exactly
- Verify gateway `target_agent_name` matches agent `agent_name`
- Check Solace broker is running: `docker ps | grep solace`

### Issue: MCP tools not working

**Symptoms**: "Tool not found" or "MCP connection failed"

**Solutions**:
- Verify absolute paths to MCP servers (not relative)
- Check Node.js packages installed: `ls node_modules/@modelcontextprotocol`
- Verify PostgreSQL is running: `docker ps | grep postgres`
- Test MCP server directly: `node /path/to/mcp_postgres_rw.js postgresql://...`

### Issue: SQL queries failing

**Symptoms**: "Column does not exist" or "Table does not exist"

**Solutions**:
- Verify database schema: `psql -U acme -d orders -c "\d tablename"`
- Check column names match exactly (snake_case)
- Ensure agent has access to correct tables (domain ownership)
- Verify connection string in `.env`

### Issue: LogisticsAgent not reachable

**Symptoms**: "Connection refused" or "Agent not responding"

**Solutions**:
- Verify LogisticsAgent is running: `lsof -i :8100`
- Check environment variables are exported: `echo $LLM_SERVICE_ENDPOINT`
- Test A2A endpoint: `curl http://localhost:8100/.well-known/agent.json`
- Check logs: `tail -f 300-Agents/sam/logistics_agent.log`

### Issue: LLM refuses to use tools

**Symptoms**: Agent returns text instead of calling database

**Solutions**:
- Make instruction ultra-directive ("YOU MUST call X tool")
- Delete stale session DB: `rm agent_name.db`
- Verify tool_description is detailed
- Use a flagship model (Claude 4.5, GPT-5, Gemini-3)

### Issue: Gateway publishes to wrong topic

**Symptoms**: Events go to `acme/orders/decision` instead of `acme/incidents/created`

**Solutions**:
- Check `on_success` routing in handler config
- Verify output handler topic_expression is correct
- Use `static:acme/topic/name` (not dynamic routing)
- Restart SAM after config changes

## Key Takeaways

### Core Concepts
- **Event-Driven Architecture**: Agents react to broker events via gateways, not direct API calls
- **Separation of Concerns**: Each agent has a single responsibility and owns one domain
- **Decoupled Communication**: Producers and consumers operate independently through the event mesh


### Important Rules
- Agent names must match exactly between YAML and gateway configs
- Static topics only: `static:acme/topic/name`

### A2A Protocol
External agents integrate via HTTP endpoints for discovery. They appear identical to SAM-native agents but can be written in any language and updated independently.


## Next Steps

In **Course 400: Workflows**, you'll:
TBD

Your agents are now operational and ready for evaluation!

