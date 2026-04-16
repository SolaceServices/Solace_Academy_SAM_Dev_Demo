# Course 500: Agent Mesh — Tooling and Plugins

## Overview

This course explores how to extend agent capabilities through tools and plugins. You'll learn the plugin lifecycle, create custom tools, integrate REST APIs, and connect to external services like AWS Bedrock Knowledge Bases.

By the end of this course, you'll understand:
- The SAM plugin ecosystem and architecture
- How to install, configure, and manage plugins
- Creating custom Python tools for agents
- Integrating REST APIs as agent capabilities
- Connecting to AWS services (Bedrock KB, S3, DynamoDB)

## Prerequisites

- Completed **Course 100**, **200**, and **300**
- Working SAM installation with multiple agents
- Familiarity with Python and REST APIs
- (Optional) AWS account for Bedrock integration

## Quick Setup

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts
bash 500-setup.sh /workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins
```

## What are Tools and Plugins?

**Tools** are capabilities that agents can use to accomplish tasks:
- Query databases
- Call APIs
- Read/write files
- Perform calculations
- Access external services

**Plugins** are pre-packaged bundles of tools, configurations, and dependencies:
- SAM RAG Agent → includes document scanner, vector DB, semantic search
- SQL Database Tool → provides database query capabilities
- Event Mesh Gateway → enables event-driven workflows

### Tool Types in SAM

#### 1. Builtin Tools
Pre-installed with SAM, no configuration needed:

```yaml
tools:
  - tool_type: builtin
    tool_name: create_chart_from_plotly_config
  
  - tool_type: builtin
    tool_name: load_artifact
  
  - tool_type: builtin
    tool_name: list_artifacts
```

**Available builtins**:
- `create_chart_from_plotly_config` — Generate charts
- `create_table_from_csv_string` — Render tables
- `load_artifact`, `list_artifacts` — Artifact management
- `create_artifact`, `update_artifact` — Artifact CRUD

#### 2. Python Tools
Custom Python classes implementing specific functionality:

```yaml
tools:
  - tool_type: python
    component_module: "sam_sql_database_tool.tools"
    component_base_path: .
    class_name: "SqlDatabaseTool"
    tool_config:
      tool_name: "orders_db"
      tool_description: "Query the Acme Retail orders database"
      connection_string: "${ORDERS_DB_CONNECTION_STRING}"
```

#### 3. MCP Tools
Model Context Protocol servers (external processes):

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "node"
      args:
        - "/path/to/mcp_postgres_rw.js"
        - "postgresql://user:pass@host:port/database"
      timeout: 10
    tool_name_prefix: "postgres"
```

#### 4. A2A Tools
External agents discovered via A2A protocol:

```yaml
tools:
  - tool_type: a2a_agent
    agent_name: "LogisticsAgent"
    agent_url: "http://localhost:8100"
    agent_card_url: "http://localhost:8100/.well-known/agent.json"
```

## The Plugin Lifecycle

### 1. Discovery

View available plugins:

```bash
sam plugin catalog
```

Or browse programmatically:

```bash
sam plugin list-available
```

### 2. Installation

Install a plugin by name:

```bash
sam plugin add agent_name --plugin plugin_name
```

Examples:

```bash
# Install RAG agent
sam plugin add acme_knowledge --plugin sam-rag

# Install SQL tool
sam plugin add order_agent --plugin sam-sql-database-tool

# Install event mesh gateway
sam plugin add acme-orders --plugin sam-event-mesh-gateway
```

### 3. Configuration

After installation, edit the generated YAML config:

```bash
# Agent plugin
configs/agents/acme_knowledge.yaml

# Gateway plugin
configs/gateways/acme-orders.yaml
```

Configure environment variables, tool parameters, and agent instructions.

### 4. Activation

Restart SAM to load the plugin:

```bash
sam run
```

SAM auto-discovers all YAML files in `configs/` (except `shared_config*.yaml` and `_*` prefixed files).

### 5. Update

Update plugin to latest version:

```bash
sam plugin update plugin_name
```

### 6. Removal

Uninstall a plugin:

```bash
sam plugin remove agent_name
```

This deletes the YAML config and uninstalls dependencies.

## Creating Custom Python Tools

Let's create a custom tool that calls an external pricing API.

### Step 1: Create Tool Class

```python
# pricing_tool.py

from typing import Dict, Any
import requests

class PricingTool:
    """Tool to query product pricing from external API."""
    
    def __init__(self, api_endpoint: str, api_key: str):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
    
    def get_price(self, product_sku: str) -> Dict[str, Any]:
        """
        Get current price for a product SKU.
        
        Args:
            product_sku: The product SKU to query
        
        Returns:
            Dict with price, currency, and availability
        """
        try:
            response = requests.get(
                f"{self.api_endpoint}/prices/{product_sku}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            return {
                "sku": product_sku,
                "price": data.get("current_price"),
                "currency": data.get("currency", "USD"),
                "available": data.get("in_stock", False),
                "last_updated": data.get("updated_at")
            }
        except Exception as e:
            return {"error": str(e)}
```

### Step 2: Add Tool to Agent Config

```yaml
# configs/agents/pricing_agent.yaml

tools:
  - tool_type: python
    component_module: "pricing_tool"
    component_base_path: "/path/to/pricing_tool.py"
    class_name: "PricingTool"
    tool_config:
      api_endpoint: "${PRICING_API_ENDPOINT}"
      api_key: "${PRICING_API_KEY}"
```

### Step 3: Update Agent Instruction

```yaml
instruction: |
  You are a Pricing Agent. Use the PricingTool to query current product prices.
  
  When asked about pricing:
  1. Call get_price(product_sku) to fetch current price
  2. Return the price, currency, and availability
  3. Mention the last_updated timestamp
  
  Example:
  User: "What is the price of SKU-LAPTOP-002?"
  You: [Call get_price("SKU-LAPTOP-002")]
  You: "SKU-LAPTOP-002 is currently $899.99 USD. It is in stock. Last updated 2026-04-14."
```

### Step 4: Test

```bash
sam run
```

Ask the agent: *"What is the price of SKU-LAPTOP-002?"*

The agent should call the tool and return formatted pricing information.

## Integrating REST APIs

### Method 1: Custom Python Tool (Above)

Best for:
- APIs requiring custom authentication
- Complex request/response transformations
- Stateful API clients

### Method 2: OpenAPI Spec (SAM Native)

SAM can auto-generate tools from OpenAPI specs:

```bash
sam add tool --openapi https://api.example.com/openapi.json
```

This generates a Python tool class with methods for each API endpoint.

### Method 3: Direct HTTP Calls (Agent Code)

For simple cases, agents can use builtin HTTP capabilities:

```yaml
instruction: |
  You can make HTTP requests using the requests library.
  
  Example:
  import requests
  response = requests.get("https://api.example.com/endpoint")
  data = response.json()
```

**Note**: This is less structured than dedicated tools but works for ad-hoc queries.

## AWS Bedrock Knowledge Base Integration

Connect SAM to AWS Bedrock Knowledge Bases for enterprise RAG.

### Prerequisites

- AWS account with Bedrock access
- Knowledge Base created in AWS Console
- IAM credentials with `bedrock:RetrieveAndGenerate` permission

### Step 1: Install AWS SDK

```bash
pip install boto3
```

### Step 2: Configure AWS Credentials

```bash
# ~/.aws/credentials
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
```

Or via environment variables:

```bash
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY"
export AWS_DEFAULT_REGION="us-east-1"
```

### Step 3: Create Bedrock Tool

```python
# bedrock_kb_tool.py

import boto3
from typing import Dict, Any

class BedrockKnowledgeTool:
    """Tool to query AWS Bedrock Knowledge Base."""
    
    def __init__(self, knowledge_base_id: str, region: str = "us-east-1"):
        self.kb_id = knowledge_base_id
        self.client = boto3.client('bedrock-agent-runtime', region_name=region)
    
    def query_knowledge(self, question: str) -> Dict[str, Any]:
        """
        Query the knowledge base.
        
        Args:
            question: Natural language question
        
        Returns:
            Dict with answer and source documents
        """
        try:
            response = self.client.retrieve_and_generate(
                input={'text': question},
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': self.kb_id,
                        'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
                    }
                }
            )
            
            return {
                "answer": response['output']['text'],
                "sources": [
                    {
                        "content": ref['content']['text'],
                        "location": ref.get('location', {}).get('s3Location', {})
                    }
                    for ref in response.get('citations', [])
                ]
            }
        except Exception as e:
            return {"error": str(e)}
```

### Step 4: Add to Agent

```yaml
tools:
  - tool_type: python
    component_module: "bedrock_kb_tool"
    component_base_path: "/path/to/bedrock_kb_tool.py"
    class_name: "BedrockKnowledgeTool"
    tool_config:
      knowledge_base_id: "${BEDROCK_KB_ID}"
      region: "${AWS_REGION, us-east-1}"
```

### Step 5: Test

```bash
sam run
```

Ask the agent: *"What is our company's return policy?"*

The agent queries Bedrock KB and returns the answer with source citations.

## Plugin Best Practices

### Configuration
- Use environment variables for secrets (`${VAR_NAME}`)
- Store configs in `shared_config.yaml` for reuse
- Always validate tool parameters before use

### Error Handling
- Tools should return error objects (not raise exceptions)
- Include helpful error messages for debugging
- Log errors without exposing sensitive data

### Documentation
- Provide clear tool descriptions (agents read these)
- Include examples in agent instructions
- Document required parameters and return formats

### Performance
- Set reasonable timeouts (10s for network calls)
- Cache expensive operations when possible
- Use connection pooling for databases

### Security
- Never hardcode API keys in YAML
- Use IAM roles (not long-lived credentials) for AWS
- Validate input parameters to prevent injection

## Common Plugin Issues

### Issue: Plugin installation fails

**Cause**: Missing dependencies or version conflicts

**Solution**:
```bash
pip install --upgrade plugin-name
pip list | grep plugin-name  # Verify version
```

### Issue: Tool not discovered by agent

**Cause**: Incorrect tool configuration

**Solution**:
- Verify `tool_type` matches implementation
- Check `component_module` path is correct
- Ensure YAML is in `configs/agents/` (not `_configs/`)

### Issue: MCP server fails to start

**Cause**: Missing Node.js dependencies or wrong paths

**Solution**:
```bash
npm install @modelcontextprotocol/server-postgres
which node  # Verify node is in PATH
```

### Issue: Custom tool returns errors

**Cause**: Incorrect parameters or authentication

**Solution**:
- Test tool directly (outside SAM) to isolate issue
- Check environment variables are loaded: `echo $VAR_NAME`
- Verify API credentials and endpoints

## Key Takeaways

### Tool Architecture
- **Builtin tools** are pre-installed, no config needed
- **Python tools** are custom classes for specific functionality
- **MCP tools** are external processes (Node.js servers, etc.)
- **A2A tools** are external agents discovered dynamically

### Plugin Management
- Use `sam plugin catalog` to browse available plugins
- Install with `sam plugin add name --plugin plugin_name`
- Configure via generated YAML files
- Restart SAM to activate changes

### Custom Tools
- Implement as Python classes with clear method signatures
- Return structured data (dicts, not exceptions)
- Include comprehensive error handling
- Document parameters and return values

### Integration Patterns
- REST APIs → Custom Python tools or OpenAPI specs
- AWS Services → Boto3-based tools with IAM credentials
- External Agents → A2A protocol for discovery and routing

## Next Steps

In **Course 600: Troubleshooting**, you'll:
- Learn where SAM logs are stored
- Configure logging levels and formats
- Debug common agent issues
- Use SAM's built-in debugging tools

Your agent mesh now has extended capabilities via custom tools and plugins!

## Additional Resources

- Setup script: `500-env-setup.md`
- SAM plugin catalog: `sam plugin list-available`
- Python tool examples: `/acme-retail/infrastructure/`
- AWS Bedrock docs: https://docs.aws.amazon.com/bedrock/
- MCP protocol spec: https://modelcontextprotocol.io/
