#!/usr/bin/env python3
"""Auto-generate all agent and gateway YAML configs from 300-Agents course."""
import sys
from pathlib import Path

def create_file(path, content, desc):
    p = Path(path)
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return True

def create_agents(agents_dir: Path):
    """Create all 5 agent YAML files. Returns count of files created."""
    created = 0
    # acme-knowledge.yaml
    content_acme_knowledge = '''# This is a configuration template for the SAM RAG Agent Plugin.
#
# Plugin Metadata:
# Name: sam-rag-agent
# Version: 0.1.0
# Description: This plugin allows you to import one RAG agent as action to be used in your SAM project.
# Author: SolaceLabs <solacelabs@solace.com>

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: acme-knowledge.log

# To use the `shared_config.yaml` file, uncomment the following line and remove the `shared_config` section below.
# !include ../shared_config.yaml

shared_config:
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8080}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}

  - models:
    general: &general_model
      # This dictionary structure tells ADK to use the LiteLlm wrapper.
      # 'model' uses the specific model identifier your endpoint expects.
      model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
      # 'api_base' tells LiteLLM where to send the request.
      api_base: ${LLM_SERVICE_ENDPOINT}
      # 'api_key' provides authentication.
      api_key: ${LLM_SERVICE_API_KEY}

  - services:
    # Default session service configuration
    session_service: &default_session_service
      type: "memory"
      default_behavior: "PERSISTENT"
    
    # Default artifact service configuration
    artifact_service: &default_artifact_service
      type: "filesystem"
      base_path: "/tmp/samv2"
      artifact_scope: "app"

apps:
  - name: acme-knowledge-app
    app_module: solace_agent_mesh.agent.sac.app 
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}" # Your A2A topic namespace
      agent_name: "AcmeKnowledge" 
      display_name: "Acme Knowledge Agent" 
      supports_streaming: true # RAG agent supports streaming responses

      model: *general_model 
      instruction: |
        You are Acme Knowledge, a RAG (Retrieval Augmented Generation) agent that can ingest documents and retrieve relevant information.
        You can search for information in the ingested documents and provide augmented responses.
        Use the 'ingest_document' tool to add new documents to the system.
        Use the 'search_documents' tool to find relevant information based on user queries.

      # --- Configurable Agent Initialization & Cleanup ---
      agent_init_function:
        module: "sam_rag.lifecycle"
        name: "initialize_rag_agent"
        config:
          scanner:
            batch: true
            use_memory_storage: true
            sources:
              - type: filesystem
                directories:
                  - "${DOCUMENTS_PATH}" # Path to documents directory
                filters:
                  file_formats:
                    - ".txt"
                    - ".pdf"
                    - ".docx"
                    - ".md"
                    - ".html"
                    - ".csv"
                    - ".json"
                  max_file_size: 10240  # in KB (10MB)
                schedule:
                  interval: 60 # seconds
            
          # Text splitter configuration
          splitter:
            default:
              method: CharacterTextSplitter
              params:
                chunk_size: 2048 # minimum chunk size
                chunk_overlap: 800
                separator: " "
            splitters:
              # Text file configurations
              text:
                method: CharacterTextSplitter
                params:
                  chunk_size: 2048 # minimum chunk size
                  chunk_overlap: 800
                  separator: " "
                  is_separator_regex: false
                  keep_separator: true
                  strip_whitespace: true
              txt:
                method: CharacterTextSplitter
                params:
                  chunk_size: 2048 # minimum chunk size
                  chunk_overlap: 800
                  separator: "\n"
                  is_separator_regex: false
                  keep_separator: true
                  strip_whitespace: true
              # Structured data configurations
              json:
                method: RecursiveJSONSplitter
                params:
                  chunk_size: 200
                  chunk_overlap: 50
              html:
                method: HTMLSplitter
                params:
                  chunk_size: 2048
                  chunk_overlap: 800
                  tags_to_extract: ["p", "h1", "h2", "h3", "li"]
              markdown:
                method: MarkdownSplitter
                params:
                  chunk_size: 2048
                  chunk_overlap: 800
                  headers_to_split_on: ["#", "##", "###", "####", "#####", "######"]
                  strip_headers: false
              csv:
                method: CSVSplitter
                params:
                  chunk_size: 2048 # chunk size in number of rows
                  include_header: false
                # Add Xml, Odt, Xlsx, and other formats as needed
            # Embedding configuration
          
          embedding:
            embedder_type: "openai"
            embedder_params:
              model: "${OPENAI_EMBEDDING_MODEL}"
              api_key: "${OPENAI_API_KEY}"
              api_base: "${OPENAI_API_ENDPOINT}"
              batch_size: 32
            normalize_embeddings: true
          
          vector_db:
            db_type: "qdrant"
            db_params:
              url: "${QDRANT_URL}"
              api_key: "${QDRANT_API_KEY}"
              collection_name: "${QDRANT_COLLECTION}"
              embedding_dimension: ${QDRANT_EMBEDDING_DIMENSION}
          
          llm:
            load_balancer:
              - model_name: "gpt-4o"
                litellm_params:
                  model: openai/${OPENAI_MODEL_NAME}
                  api_key: ${OPENAI_API_KEY}
                  api_base: ${OPENAI_API_ENDPOINT}
                  temperature: 0.01
          
          retrieval:
            top_k: 5

      agent_cleanup_function:
        module: "sam_rag.lifecycle"
        name: "cleanup_rag_agent_resources"

      # --- ADK Tools Configuration ---
      tools:
        - tool_type: python
          component_module: "sam_rag.tools"
          function_name: "ingest_document"
          required_scopes: ["rag:ingest:write"]
        
        - tool_type: python
          component_module: "sam_rag.tools"
          function_name: "search_documents"
          required_scopes: ["rag:search:read"]

      session_service: 
        type: "sql"
        database_url: "${ACME_KNOWLEDGE_DATABASE_URL, sqlite:///acme_knowledge.db}"
        default_behavior: "PERSISTENT"
      artifact_service: *default_artifact_service

      # Enable built-in artifact tools for the LLM to use
      enable_builtin_artifact_tools:
        enabled: true

      # Agent Card, Discovery, and Inter-Agent Communication
      agent_card:
        description: "RAG Agent that can ingest documents and retrieve relevant information based on queries."
        defaultInputModes: ["text", "file"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "document_ingestion"
            name: "Document Ingestion"
            description: "Ingest documents from various sources into the RAG system."
            examples:
              - "Please ingest this document about climate change."
              - "Add this PDF to the knowledge base."
          - id: "document_retrieval"
            name: "Document Retrieval"
            description: "Search for relevant information in ingested documents."
            examples:
              - "What information do we have about renewable energy?"
              - "Find documents related to machine learning algorithms."

      agent_card_publishing:
        interval_seconds: 30

      agent_discovery:
        enabled: true

      inter_agent_communication:
        allow_list: ["*"]
        deny_list: []
        request_timeout_seconds: 60'''
    if create_file(str(agents_dir / 'acme-knowledge.yaml'), content_acme_knowledge, 'acme-knowledge.yaml'):
        created += 1

    # order_fulfillment_agent_agent.yaml
    content_order_fulfillment_agent_agent = '''# Solace Agent Mesh Agent Configuration

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: a2a_agent.log

!include ../shared_config.yaml

apps:
  - name: "OrderFulfillmentAgent__app"
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      supports_streaming: true
      agent_name: "OrderFulfillmentAgent"
      display_name: "Order Fulfillment Agent Agent"
      model: *general_model 

      instruction: |      
        You are an Order Fulfillment Agent responsible for processing customer orders, managing order lifecycles, and coordinating with inventory and logistics systems.                                                                          
                                                                                                                                                             
        Your primary responsibilities:
        1. Handle new orders by checking inventory availability and saving each order with status 'validated' if stock is sufficient, or 'blocked' if not.
        2. Track and update order status as orders progress through the fulfillment lifecycle (pending → validated → processing → shipped → delivered) — but only advance status in response to explicit lifecycle events.
        3. Handle order cancellations by updating the order status to 'cancelled', and process refunds when requested.
        4. Query orders by status, customer, date range, or other criteria.
        5. React to inventory update events to re-validate blocked orders when stock becomes available, updating their status to 'validated'.
        6. React to supply chain incidents by updating any affected order fields (e.g. estimated_delivery). Do not create incident records — the IncidentResponseAgent is solely responsible for incident creation.                                                                                                                                           
      
      tools:
        - tool_type: python
          component_module: "sam_sql_database_tool.tools"
          component_base_path: .
          class_name: "SqlDatabaseTool"
          tool_config:
            tool_name: "orders_db"
            tool_description: >
              Query and modify the Acme Retail orders database. Use this tool for orders,
              order_items, inventory, and shipments. Do not attempt to insert, update, or
              delete incident records — that is the sole responsibility of the
              IncidentResponseAgent. Supports SELECT queries and data-modifying statements
              (INSERT, UPDATE) for order lifecycle management.
            connection_string: "${ORDERS_DB_CONNECTION_STRING, postgresql://acme:acme@localhost:5432/orders}"
      
        - tool_type: builtin
          tool_name: create_chart_from_plotly_config
      
        - tool_type: builtin
          tool_name: load_artifact
        
        - tool_type: builtin
          tool_name: list_artifacts
          

      session_service: 
        type: "sql"
        default_behavior: "PERSISTENT"
        database_url: "${ORDER_FULFILLMENT_AGENT_DATABASE_URL, sqlite:///order_fulfillment_agent.db}"
      artifact_service: 
        type: "filesystem"
        base_path: "/tmp/samv2"
        artifact_scope: app
      enable_builtin_artifact_tools:
        enabled: true
      
      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true
      data_tools_config: *default_data_tools_config
      auto_summarization: *default_auto_summarization

      # Agent Card Definition
      agent_card:
        description: |
          An Agent responsible for order fulfillment that can process new orders, check order status, update order status, and cancel orders.
        defaultInputModes: [text, json] 
        defaultOutputModes: [text, file, json] 
        skills:
          - id: process_order
            name: process_order
            description: Validate and process new customer orders with inventory checks
            tags: []

          - id: check_order_status
            name: check_order_status
            description: Query current order status and fulfillment progress
            tags: []

          - id: update_order_status
            name: update_order_status
            description: Update order status and emit status change events
            tags: []

          - id: cancel_order
            name: cancel_order
            description: Process order cancellation and update inventory
            tags: []

          - id: query_orders
            name: query_orders
            description: Query and filter orders by status, customer, date range, or priority
            tags: []

          - id: handle_inventory_update
            name: handle_inventory_update
            description: React to inventory update events from Inventory Monitoring Agent
            tags: []

          - id: handle_incident
            name: handle_incident
            description: React to supply chain incidents affecting orders
            tags: []
      
      # Discovery & Communication
      agent_card_publishing: 
        interval_seconds: 10
      agent_discovery: 
        enabled: true
      inter_agent_communication:
        allow_list: [] 
        deny_list: [] 
        request_timeout_seconds: 60'''
    if create_file(str(agents_dir / 'order_fulfillment_agent_agent.yaml'), content_order_fulfillment_agent_agent, 'order_fulfillment_agent_agent.yaml'):
        created += 1

    # inventory_management_agent_agent.yaml
    content_inventory_management_agent_agent = '''# Solace Agent Mesh Agent Configuration

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: a2a_agent.log

!include ../shared_config.yaml

apps:
  - name: "InventoryManagementAgent__app"
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      supports_streaming: true
      agent_name: "InventoryManagementAgent"
      display_name: "Inventory Management Agent Agent"
      model: *general_model 

      instruction: |
        You are an Inventory Management Agent responsible for monitoring Acme Retail's
        product inventory, processing stock adjustments, and notifying other agents
        of stock level changes.

        The inventory table has these columns:
        item_id, product_name, category, stock_quantity, reserved_quantity,
        available_quantity, reorder_level, reorder_quantity, unit_cost, unit_price,
        warehouse_location, supplier_id, supplier_name, last_restocked,
        expected_restock_date, status, incident_id.

        Your primary responsibilities:
          1. Query inventory levels for individual SKUs, categories, suppliers, or warehouse locations using SELECT queries on the inventory table.
          2. Apply stock adjustments when new stock arrives or quantities change: execute a SINGLE UPDATE query that sets stock_quantity, available_quantity, last_restocked, AND status all at once — never split this into two queries. Compute status inline with a CASE expression: 'out_of_stock' when the new available_quantity = 0, 'low_stock' when new available_quantity > 0 and <= reorder_level, 'in_stock' when new available_quantity > reorder_level.
          3. Identify items needing reorder by finding rows where available_quantity <= reorder_level, and produce reorder recommendations using each item's reorder_quantity as the suggested order size.
          4. Generate inventory reports and charts on demand — by category, warehouse, supplier, or status — and save report files to /tmp/inventory-reports/.
          5. Only modify the inventory table. Never insert, update, or delete rows in any other table (orders, shipments, incidents, etc.).

        Data integrity rule: All quantities, product names, and status values in responses,
        summaries, and chart data must come directly from query results. Never estimate,
        round, paraphrase, or recall values from memory — always read them from the database first. 
        When reporting or summarizing stock levels, always use available_quantity
        (not stock_quantity) as the measure of usable stock.
      
      tools: 
        - tool_type: builtin-group
          group_name: artifact_management
        - tool_type: builtin
          tool_name: create_chart_from_plotly_config

        - tool_type: mcp
          connection_params:
            type: stdio
            command: "node"
            args:
              - "/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure/mcp_postgres_rw.js"
              - "postgresql://acme:acme@localhost:5432/orders"
            timeout: 30

        - tool_type: mcp
          connection_params:
            type: stdio
            command: "/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/infrastructure/node_modules/.bin/mcp-server-filesystem"
            args:
              - "/tmp/inventory-reports"
            timeout: 30
          allow_list:
            - "write_file"
            - "read_file"
            - "list_directory"

      session_service: 
        type: "sql"
        default_behavior: "PERSISTENT"
        database_url: "${INVENTORY_MANAGEMENT_AGENT_DATABASE_URL, sqlite:///inventory_management_agent.db}"
      artifact_service: *default_artifact_service
      
      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true
      data_tools_config: *default_data_tools_config
      auto_summarization: *default_auto_summarization

      # Agent Card Definition
      agent_card:
        description: |
          An Agent responsible for monitoring and managing Acme Retail's product inventory. This agent checks stock levels, processes adjustments, identifies reorder needs, and publishes inventory update events to the order fulfillment pipeline.  
        defaultInputModes: [text] 
        defaultOutputModes: [text, file, json] 
        skills: 
          - description: 'Query stock levels by SKU, category, supplier, or warehouse location '
            id: check_inventory
            name: Check Inventory
          - description: Apply stock adjustments and update inventory status after receipt or
              write-off
            id: adjust_stock
            name: Adjust Stock
          - description: Identify items below reorder level, forecast when items will fall below
              reorder level, and generate suggested purchase quantities
            id: reorder_recommendations
            name: Reorder Recommendations
          - description: Generate inventory reports and charts by category, warehouse, supplier,
              or status
            id: ' inventory_report '
            name: Inventory Report
      
      # Discovery & Communication
      agent_card_publishing: 
        interval_seconds: 10
      agent_discovery: 
        enabled: true
      inter_agent_communication:
        allow_list: ["*"] 
        deny_list: [] 
        request_timeout_seconds: 60'''
    if create_file(str(agents_dir / 'inventory_management_agent_agent.yaml'), content_inventory_management_agent_agent, 'inventory_management_agent_agent.yaml'):
        created += 1

    # incident_response_agent_agent.yaml
    content_incident_response_agent_agent = '''# Solace Agent Mesh Agent Configuration

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: a2a_agent.log

!include ../shared_config.yaml

apps:
  - name: "IncidentResponseAgent__app"
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      supports_streaming: true
      agent_name: "IncidentResponseAgent"
      display_name: "Incident Response Agent"
      model: *general_model 

      instruction: |
        You are the Incident Response Agent — the sole creator and manager of all incident records
        in the system. When you receive conditions from other agents via gateway handlers, you decide
        whether to create new incidents or update existing ones. All incident records flow through you.

        You receive incident-worthy conditions via event handlers (order_decision_handler, logistics_updated_handler,
        inventory_error_handler, etc.). Each handler provides specific context about what condition occurred.
        Your job is to: (1) determine if an incident should be created or updated, (2) perform the DB operation,
        (3) apply escalation logic if needed (e.g., high-severity incidents → 'investigating' status),
        and (4) report back via the gateway's output handler.

        Your primary responsibilities:
        1. Create new incidents with appropriate type, severity, status, title, and description.
           When creating incidents:
           - First generate a unique incident_id by running this SQL to find the next sequence number:
             SELECT COALESCE(MAX(CAST(SPLIT_PART(incident_id, '-', 3) AS INTEGER)), 0) + 1 AS next_num
             FROM incidents WHERE incident_id LIKE 'INC-' || to_char(NOW(), 'YYYY') || '-%'
           - Then construct the incident_id as 'INC-' || to_char(NOW(), 'YYYY') || '-' || LPAD(next_num::TEXT, 3, '0')
           - Apply escalation logic: If severity='high', set status to 'investigating'. If severity='medium' or lower, set status to 'open'.
           - Set created_date to NOW(), and last_updated to NOW().
           - Execute the INSERT immediately — do not just describe what you would do.
           - **ESCALATION RULE FOR BLOCKED ORDERS**: When creating inventory_shortage incidents with severity='high',
             always set status='investigating' in the same INSERT statement — this is required for high-severity inventory issues.
           - **DEDUPLICATION RULE FOR BLOCKED ORDERS**: When checking if an incident already exists for the same item,
             only consider incidents with status IN ('open', 'investigating'). Incidents at status='monitoring' are NOT considered open
             and should NOT prevent creation of a new incident. Use this SQL WHERE clause:
             `status IN ('open', 'investigating') AND type = 'inventory_shortage'`
           - **RESPONSE FORMAT REQUIREMENT**: After creating a new incident, you MUST return a JSON response containing
             the incident details. Format your final response as valid JSON with these fields:
             {"incident_id": "INC-YYYY-NNN", "type": "incident_type", "severity": "severity_level", 
              "status": "current_status", "title": "incident title", "description": "incident description",
              "created_date": "timestamp"}
        2. Track affected items by creating incident_items records that link incidents to specific
           inventory items (item_id, product_name, quantity_short).
        3. Query incidents by status, type, severity, supplier, date range, or affected items.
        4. Update incident details including severity, status, descriptions, and root cause analysis.
           After updating an incident, return a JSON response with the updated incident details including
           incident_id, type, severity, status, and last_updated timestamp.
        5. Resolve incidents by setting status to 'resolved', resolved_date to NOW(), and documenting
           the root cause. Return JSON with the resolved incident details.
        6. Generate incident reports and analytics showing trends, recurring issues, and supplier performance.
        
        Database schema:
        - incidents table columns: incident_id, type, severity, status, title, description, 
          created_date, last_updated, resolved_date, root_cause, supplier_id
        - incident_items table columns: id, incident_id, item_id, product_name, quantity_short
        
        When querying or updating incidents, always update the last_updated field to NOW() for any modifications.
        Use JOINs to retrieve incident data along with affected items in a single query when possible.
      
      tools:
        - tool_type: python
          component_module: "sam_sql_database_tool.tools"
          component_base_path: .
          class_name: "SqlDatabaseTool"
          tool_config:
            tool_name: "incidents_db"
            tool_description: >
              Query and manage the Acme Retail incidents database. Use this tool for ALL incident
              data operations including creating incidents, tracking affected items in incident_items,
              querying incident status, updating incident details, and resolving incidents.
              Supports both SELECT queries and data-modifying statements (INSERT, UPDATE) for 
              incident lifecycle management.
            connection_string: "postgresql://acme:acme@localhost:5432/orders"
      
        - tool_type: builtin
          tool_name: create_chart_from_plotly_config
      
        - tool_type: builtin
          tool_name: load_artifact
        
        - tool_type: builtin
          tool_name: list_artifacts
          

      session_service: 
        type: "sql"
        default_behavior: "PERSISTENT"
        database_url: "${INCIDENT_RESPONSE_AGENT_DATABASE_URL, sqlite:///incident_response_agent.db}"
      artifact_service: 
        type: "filesystem"
        base_path: "/tmp/samv2"
        artifact_scope: app
      enable_builtin_artifact_tools:
        enabled: true
      
      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true
      data_tools_config: *default_data_tools_config
      auto_summarization: *default_auto_summarization

      # Agent Card Definition
      agent_card:
        description: |
          An Agent responsible for incident management that can create incidents, track affected items, 
          query incident status, update incident details, and resolve incidents with root cause analysis.
        defaultInputModes: [text, json] 
        defaultOutputModes: [text, file, json] 
        skills:
          - id: create_incident
            name: create_incident
            description: Create new supply chain incidents with severity and affected items
            tags: []

          - id: query_incidents
            name: query_incidents
            description: Query incidents by status, type, severity, supplier, or date range
            tags: []

          - id: update_incident
            name: update_incident
            description: Update incident details, severity, or status
            tags: []

          - id: resolve_incident
            name: resolve_incident
            description: Resolve incidents with root cause documentation
            tags: []

          - id: track_affected_items
            name: track_affected_items
            description: Track and query items affected by incidents
            tags: []

          - id: generate_incident_reports
            name: generate_incident_reports
            description: Generate incident analytics and supplier performance reports
            tags: []
      
      # Discovery & Communication
      agent_card_publishing: 
        interval_seconds: 10
      agent_discovery: 
        enabled: true
      inter_agent_communication:
        allow_list: [] 
        deny_list: [] 
        request_timeout_seconds: 60'''
    if create_file(str(agents_dir / 'incident_response_agent_agent.yaml'), content_incident_response_agent_agent, 'incident_response_agent_agent.yaml'):
        created += 1

    # a2a.yaml
    content_a2a = '''log:
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
          discovery_interval_seconds: 5'''
    if create_file(str(agents_dir / 'a2a.yaml'), content_a2a, 'a2a.yaml'):
        created += 1
    return created


def create_gateways(gateways_dir: Path):
    """Create all 5 gateway YAML files. Returns count of files created."""
    created = 0
    # webui.yaml
    content_webui = '''

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: webui_app.log


!include ../shared_config.yaml

apps:
  - name: a2a_webui_app
    app_base_path: .
    app_module: solace_agent_mesh.gateway.http_sse.app

    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      session_secret_key: "${SESSION_SECRET_KEY}"

      model: *general_model
      artifact_service: *default_artifact_service
      session_service: 
        type: "sql"
        database_url: "${WEB_UI_GATEWAY_DATABASE_URL, sqlite:///webui_gateway.db}"
        default_behavior: "PERSISTENT"
      gateway_id: ${WEBUI_GATEWAY_ID}
      fastapi_host: ${FASTAPI_HOST}
      fastapi_port: ${FASTAPI_PORT, 8000}
      cors_allowed_origins:
        - "http://localhost:3000"
        - "http://127.0.0.1:3000"

      # Platform Service Configuration (runs as second app in this template)
      platform_service:
        url: "${PLATFORM_SERVICE_URL, http://localhost:8001}"

      # OAuth2 Authentication (Community: false, Enterprise: true)
      external_auth_service_url: ${EXTERNAL_AUTH_SERVICE_URL}
      external_auth_provider: ${EXTERNAL_AUTH_PROVIDER, generic}
      frontend_use_authorization: ${FRONTEND_USE_AUTHORIZATION, false}

      enable_embed_resolution: ${ENABLE_EMBED_RESOLUTION} # Enable late-stage resolution
      gateway_artifact_content_limit_bytes: ${GATEWAY_ARTIFACT_LIMIT_BYTES, 10000000} # Max size for late-stage embeds
      sse_max_queue_size: ${SSE_MAX_QUEUE_SIZE, 200} # Max size of SSE connection queues
      
      # Queue Configuration
      visualization_queue_size: ${VISUALIZATION_QUEUE_SIZE, 600}
      task_logger_queue_size: ${TASK_LOGGER_QUEUE_SIZE, 600}

      system_purpose: >
            The system is an AI Chatbot with agentic capabilities.
            It will use the agents available to provide information,
            reasoning and general assistance for the users in this system.
            **Always return useful artifacts and files that you create to the user.**
            Provide a status update before each tool call.
            Your external name is Agent Mesh.

      response_format: >
            Responses should be clear, concise, and professionally toned.
            Format responses to the user in Markdown using appropriate formatting.

      # --- Frontend Config Passthrough ---
      frontend_welcome_message: How can I assist you today?
      frontend_bot_name: Solace Agent Mesh
      frontend_collect_feedback: false
      frontend_logo_url: 

      task_logging:
        enabled: true
        hybrid_buffer:
          enabled: false   # false=events go directly to DB (default); true=buffer in RAM first, then flush to DB
          flush_threshold: 10     # Flush to DB after N events (lower for easier testing)
        log_status_updates: true
        log_artifact_events: true
        log_file_parts: true
        max_file_part_size_bytes: 10240
      
      # --- Frontend Feature Flags ---
      # Uncomment to control speech features in the UI
      frontend_feature_enablement:
        speechToText: true   # Set to false to hide Speech-to-Text settings & microphone
        textToSpeech: true   # Set to false to hide Text-to-Speech settings & speaker button
      #   projects: true
      #   promptLibrary: true
        background_tasks: true  # NOTE: task_logging must also be enabled for background tasks to work
        # Binary artifact preview (DOCX, PPTX files):
        # Requires LibreOffice to be installed (build with INSTALL_LIBREOFFICE=true)
        # Set to true only if LibreOffice is available on the server
        binaryArtifactPreview: false

      # --- Background Tasks Configuration ---
      background_tasks:
        default_timeout_ms: 3600000  # Default: 1 hour (3600000ms)

      # --- Speech Configuration (STT/TTS) ---
      speech:
        # stt:
        #   provider: openai
        #   url: "https://api.openai.com/v1/audio/transcriptions"
        #   api_key: "${OPENAI_API_KEY}"
        #   model: "whisper-1"
        stt:
          provider: azure
          azure:
            api_key: "${AZURE_SPEECH_KEY}"
            region: "${AZURE_SPEECH_REGION}"
            language: en-US
        
        # Text-to-Speech Configuration
        tts:
          provider: ${TTS_PROVIDER, gemini}  # "gemini", "azure", or "polly" (can be overridden by UI)
          
          # Azure Neural Voices Configuration
          azure:
            api_key: "${AZURE_SPEECH_KEY}"
            region: "${AZURE_SPEECH_REGION}"
            default_voice: "en-US-Andrew:DragonHDLatestNeural"
            voices:
              # DragonHD Latest Neural Voices (Highest Quality)
              - "en-US-Ava:DragonHDLatestNeural"
              - "en-US-Ava3:DragonHDLatestNeural"
              - "en-US-Adam:DragonHDLatestNeural"
              - "en-US-Alloy:DragonHDLatestNeural"
              - "en-US-Andrew:DragonHDLatestNeural"
              - "en-US-Andrew2:DragonHDLatestNeural"
              - "en-US-Andrew3:DragonHDLatestNeural"
              - "en-US-Aria:DragonHDLatestNeural"
              - "en-US-Brian:DragonHDLatestNeural"
              - "en-US-Davis:DragonHDLatestNeural"
              - "en-US-Emma:DragonHDLatestNeural"
              - "en-US-Emma2:DragonHDLatestNeural"
              - "en-US-Jenny:DragonHDLatestNeural"
              - "en-US-MultiTalker-Ava-Andrew:DragonHDLatestNeural"
              - "en-US-Nova:DragonHDLatestNeural"
              - "en-US-Phoebe:DragonHDLatestNeural"
              - "en-US-Serena:DragonHDLatestNeural"
              - "en-US-Steffan:DragonHDLatestNeural"
              # Standard Neural Voices
              - "en-US-JennyNeural"
              - "en-US-GuyNeural"
              - "en-US-AriaNeural"
              - "en-US-DavisNeural"
              - "en-US-JaneNeural"
              - "en-US-JasonNeural"
              - "en-US-NancyNeural"
              - "en-US-TonyNeural"
              - "en-GB-LibbyNeural"
              - "en-GB-RyanNeural"
              - "en-GB-SoniaNeural"
              - "en-AU-NatashaNeural"
              - "en-AU-WilliamNeural"
          
          # Google Gemini Configuration
          gemini:
            api_key: "${GEMINI_API_KEY}"
            model: "gemini-2.5-flash-preview-tts"
            default_voice: "Kore"
            language: "en-US"
            voices:
            - "Kore"
            - "Puck"
            - "Zephyr"
            - "Charon"
            - "Fenrir"
            - "Leda"
            - "Aoede"
            - "Callirhoe"
            - "Umbriel"
            - "Enceladus"
            - "Iapetus"
            - "Erinome"
            - "Algieba"
            - "Despina"
            - "Algenib"
            - "Achernar"
            - "Schedar"
            - "Gacrux"
            - "Pulcherrima"
            - "Achird"
            - "Zubenelgenubi"
            - "Vindemiatrix"
            - "Sadachbia"
            - "Sadaltager"
            - "Sulafat"
            - "Autonoe"
            - "Laomedeia"
            - "Orus"
            - "Rasalgethi"
            - "Alnilam"
        
        # Frontend Speech Tab Default Settings (optional)
        speechTab:
          advancedMode: false
          speechToText:
            speechToText: true
            engineSTT: "external"  # Use external for better quality
            languageSTT: "en-US"
          textToSpeech:
            textToSpeech: true
            engineTTS: "external"  # Use external for better quality
            voice: "Kore"
            playbackRate: 1.0
            cacheTTS: true'''
    if create_file(str(gateways_dir / 'webui.yaml'), content_webui, 'webui.yaml'):
        created += 1

    # acme-order-events.yaml
    content_acme_order_events = '''# Plugin Metadata:
# Name: sam-event-mesh-gateway
# Version: 0.1.0
# Description: Solace Agent Mesh Gateway plugin for integrating with Solace PubSub+ event brokers.
# Author: SolaceLabs <solacelabs@solace.com>
# Test:
## Sent a valid json payload to topic "abc/jira/issue/create/>" and verified it was processed by the OrchestratorAgent and response published to "event_mesh/responses/>".

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: acme-order-events.log

# To use the `shared_config.yaml` file, uncomment the following line and remove the `shared_config` section below.
!include ../shared_config.yaml

apps:
  - name: acme-order-events-app
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}" 
      gateway_id: "event-mesh-gw-01" # Unique ID for this gateway instance

      artifact_service: *default_artifact_service
      authorization_service:
        type: "none" # Or "default_rbac"
      default_user_identity: "anonymous_event_mesh_user" # If no identity from event
      
# --- Event Mesh Gateway Specific Parameters ---
      event_mesh_broker_config: # For the data plane Solace client
        broker_url: ${SOLACE_BROKER_URL}
        broker_username: ${SOLACE_BROKER_USERNAME}
        broker_password: ${SOLACE_BROKER_PASSWORD}
        broker_vpn: ${SOLACE_BROKER_VPN}

      ##############################
      # 1. UPDATE REQUIRED - START #
      ##############################
      
      event_handlers: # List of handlers for incoming Solace messages
        # ── 1. New order created ──────────────────────────────────────
        - name: "order_created_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/orders/created"
              qos: 1
          input_expression: >
            template:A new order event has been received.
            Process this order: validate inventory availability for all items and update the order status in the database accordingly (status='validated' if stock sufficient, status='blocked' if not). Do not create incident records.
            Order data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "OrderFulfillmentAgent"
          on_success: "order_decision_handler"
          on_error: "error_handler"
          forward_context:
            order_id: "input.payload:order_id"

        # ── 2. Inventory updated — re-check blocked orders ────────────
        - name: "inventory_updated_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/inventory/updated"
              qos: 1
          input_expression: >
            template:An inventory update event has been received.
            Check all currently blocked orders in the database.
            For each blocked order, query the inventory table to verify whether the required stock is now available.
            For any blocked order where stock is sufficient, update its status to 'validated'.
            If no blocked orders can be fulfilled, report that all blocked orders remain blocked.
            Inventory event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "OrderFulfillmentAgent"
          on_success: "order_decision_handler"
          on_error: "error_handler"
          forward_context:
            item_id: "input.payload:item_id"

        # ── 3. Shipment delayed — create incident ─────────────────────
        - name: "shipment_delayed_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/shipment-delayed"
              qos: 1
          input_expression: >
            template:A shipment delay event has been received.
            Tracking number {{text://input.payload:tracking_number}} is delayed by {{text://input.payload:delay_hours}} hours via carrier {{text://input.payload:carrier}}.
            Update the estimated_delivery field on the affected order to the new delivery date from the event. Do not create an incident record — the IncidentResponseAgent will handle that based on the acme/logistics/updated event.
            Shipment event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "OrderFulfillmentAgent"
          on_success: "order_decision_handler"
          on_error: "error_handler"
          forward_context:
            tracking_number: "input.payload:tracking_number"
        # ── 4. Order cancelled ────────────────────────────────────────                                                                   
        - name: "order_cancelled_handler"                                                                                                  
          default_user_identity: "anonymous_event_mesh_user"                                                                               
          subscriptions:                                                                                                                   
            - topic: "acme/orders/cancelled"                                                                                               
              qos: 1                                                                                                                       
          input_expression: >                                                                                                              
            template:An order cancellation event has been received.                                                                        
            Order {{text://input.payload:order_id}} has been cancelled.                                                                    
            Reason: {{text://input.payload:reason}}.                                                                                       
            Update the order status to 'cancelled' in the database.                                                                        
            Cancellation event data: {{text://input.payload}}                                                                              
          payload_encoding: "utf-8"                                                                                                        
          payload_format: "json"                                                                                                           
          target_agent_name: "OrderFulfillmentAgent"                                                                                       
          on_success: "order_decision_handler"                                                                                             
          on_error: "error_handler"                                                                                                        
          forward_context:                                                                                                                 
            order_id: "input.payload:order_id"  


      output_handlers: # Optional: List of handlers for publishing A2A responses
       # Publishes validated or blocked decision back to the mesh
        - name: "order_decision_handler"
          topic_expression: "static:acme/orders/decision"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"

        # Publishes incident created confirmation
        - name: "incident_created_handler"
          topic_expression: "static:acme/incidents/created"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"

        # Error handler — publishes failures for observability
        - name: "error_handler"
          topic_expression: "static:acme/orders/errors"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"
  # Example of a second output handler, commented out
  #       - name: "text_response_to_systemB"
  #         topic_expression: "template:external/systemB/responses/{{text://task_response:id}}"
  #         payload_expression: "task_response:status.message.parts.0.text" # Direct access
  #         payload_encoding: "utf-8"
  #         payload_format: "text"

      ############################
      # 1. UPDATE REQUIRED - END #
      ############################'''
    if create_file(str(gateways_dir / 'acme-order-events.yaml'), content_acme_order_events, 'acme-order-events.yaml'):
        created += 1

    # acme-inventory-events.yaml
    content_acme_inventory_events = '''# Plugin Metadata:
# Name: sam-event-mesh-gateway
# Version: 0.1.0
# Description: Solace Agent Mesh Gateway plugin for integrating with Solace PubSub+ event brokers.
# Author: SolaceLabs <solacelabs@solace.com>

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: acme-inventory-events.log

!include ../shared_config.yaml

apps:
  - name: acme-inventory-events-app
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "inventory-event-gw-01"

      artifact_service: *default_artifact_service
      authorization_service:
        type: "none"
      default_user_identity: "anonymous_event_mesh_user"

      event_mesh_broker_config:
        broker_url: ${SOLACE_BROKER_URL}
        broker_username: ${SOLACE_BROKER_USERNAME}
        broker_password: ${SOLACE_BROKER_PASSWORD}
        broker_vpn: ${SOLACE_BROKER_VPN}

      event_handlers:
        # ── 1. Supplier restock received — update inventory quantities ────────
        - name: "restock_received_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/suppliers/restock-received"
              qos: 1
          input_expression: >
            template:Supplier restock received for SKU {{text://input.payload:item_id}} (+{{text://input.payload:quantity_received}} units from {{text://input.payload:supplier_name}}).

            Execute this UPDATE statement exactly as written (do not modify, do not split into separate queries):
            UPDATE inventory
            SET stock_quantity = stock_quantity + {{text://input.payload:quantity_received}},
                available_quantity = available_quantity + {{text://input.payload:quantity_received}},
                last_restocked = NOW(),
                status = CASE
                  WHEN (available_quantity + {{text://input.payload:quantity_received}}) = 0 THEN 'out_of_stock'
                  WHEN (available_quantity + {{text://input.payload:quantity_received}}) > 0 AND (available_quantity + {{text://input.payload:quantity_received}}) <= reorder_level THEN 'low_stock'
                  ELSE 'in_stock'
                END
            WHERE item_id = '{{text://input.payload:item_id}}'

            This must be a single UPDATE with the status computed inline. Do not execute this as two separate queries.
            Full event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "InventoryManagementAgent"
          on_success: "inventory_updated_publisher"
          on_error: "error_handler"
          forward_context:
            item_id: "input.payload:item_id"

        # ── 2. Inventory adjustment — write-offs and manual corrections ───────
        - name: "inventory_adjustment_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/inventory/adjustment"
              qos: 1
          input_expression: >
            template:Inventory adjustment received for SKU {{text://input.payload:item_id}} (delta: {{text://input.payload:quantity_delta}} units, type: {{text://input.payload:adjustment_type}}, reason: {{text://input.payload:reason}}).

            Execute this UPDATE statement exactly as written (do not modify, do not split into separate queries):
            UPDATE inventory
            SET stock_quantity = stock_quantity + {{text://input.payload:quantity_delta}},
                available_quantity = available_quantity + {{text://input.payload:quantity_delta}},
                status = CASE
                  WHEN (available_quantity + {{text://input.payload:quantity_delta}}) = 0 THEN 'out_of_stock'
                  WHEN (available_quantity + {{text://input.payload:quantity_delta}}) > 0 AND (available_quantity + {{text://input.payload:quantity_delta}}) <= reorder_level THEN 'low_stock'
                  ELSE 'in_stock'
                END
            WHERE item_id = '{{text://input.payload:item_id}}'

            Do not update last_restocked. This must be a single UPDATE with status computed inline. Do not execute as two separate queries.
            Full event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "InventoryManagementAgent"
          on_success: "inventory_updated_publisher"
          on_error: "error_handler"
          forward_context:
            item_id: "input.payload:item_id"

      output_handlers:
        # Publishes inventory update event — consumed by OrderFulfillmentAgent to unblock orders
        - name: "inventory_updated_publisher"
          topic_expression: "static:acme/inventory/updated"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"

        # Error handler — publishes failures for observability
        - name: "error_handler"
      topic_expression: "static:acme/inventory/errors"
      payload_format: "json"
      payload_expression: "task_response:text"'''
    if create_file(str(gateways_dir / 'acme-inventory-events.yaml'), content_acme_inventory_events, 'acme-inventory-events.yaml'):
        created += 1

    # acme-incidents-events.yaml
    content_acme_incidents_events = '''# Plugin Metadata:
# Name: sam-event-mesh-gateway
# Version: 0.1.0
# Description: Solace Agent Mesh Gateway for incident management and monitoring
# Author: SolaceLabs <solacelabs@solace.com>

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: acme-incidents-events.log

!include ../shared_config.yaml

apps:
  - name: acme-incidents-events-app
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}" 
      gateway_id: "incident-gw-01" # Unique ID for this gateway instance

      artifact_service: *default_artifact_service
      authorization_service:
        type: "none"
      default_user_identity: "anonymous_event_mesh_user"
      
      event_mesh_broker_config:
        broker_url: ${SOLACE_BROKER_URL}
        broker_username: ${SOLACE_BROKER_USERNAME}
        broker_password: ${SOLACE_BROKER_PASSWORD}
        broker_vpn: ${SOLACE_BROKER_VPN}

      event_handlers:
        # ── 1. Order decision — create incident for blocked orders ────
        - name: "order_decision_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/orders/decision"
              qos: 1
          input_expression: >
            template:An order decision event has been received.
            Read the decision text carefully.
            If the text indicates that an order was blocked due to insufficient stock, extract the order_id mentioned in the text.
            Query the orders table to get the item details for this order (join with order_items if needed).
            Then check the incidents table for any existing incidents with type='inventory_shortage' for the same item_id(s) AND status IN ('open', 'investigating').
            Once an incident reaches 'monitoring' status, it is no longer considered "open" and a new incident should be created for new blocked orders.
            If no existing open incident is found, create a new incident with type='inventory_shortage', severity='high',
            and populate title and description with the order and item details.
            Also create corresponding incident_items records linking the incident to the affected items.
            Apply your escalation logic to determine the appropriate status based on severity.
            Return a JSON response with the incident details.
            If the decision does not indicate a blocked order, or if an open incident already exists (status='open' or 'investigating'), take no action.
            Decision data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            decision: "input.payload"

        # ── 2. Logistics updated — create shipment delay incidents ──────
        - name: "logistics_updated_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/updated"
              qos: 1
          input_expression: >
            template:A logistics status update event has been received.
            Extract the shipment tracking details from the event.
            If the event indicates a shipment delay (delay_hours > 0 or status contains 'delayed'), query the incidents table to check for any existing open 'shipment_delay' incidents for this tracking number.
            If no existing incident is found, create a new incident with type='shipment_delay', severity='medium', and populate title and description with the delay details.
            Apply your escalation logic to determine the appropriate status based on severity.
            Return a JSON response with the incident details.
            If the event does not indicate a delay, or if an open incident already exists, take no action.
            Logistics event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            tracking_number: "input.payload:tracking_number"

        # ── 4. Inventory updated — update linked incidents ────────────
        - name: "inventory_updated_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/inventory/updated"
              qos: 1
          input_expression: >
            template:An inventory update event has been received.
            The item {{text://input.payload:item_id}} has been restocked with new stock quantity {{text://input.payload:new_stock_quantity}}.
            Query the incidents table to find any open incidents (status='open' or status='investigating') that are linked 
            to this item_id via the incident_items table.
            If the new stock quantity is now sufficient (greater than 0), update those linked incidents to status='monitoring' 
            and set last_updated to NOW().
            Return a JSON response with the updated incident details.
            If no linked open incidents exist, or if stock is still insufficient, take no action.
            Inventory event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_response_handler"
          on_error: "error_handler"
          forward_context:
            item_id: "input.payload:item_id"

        # ── 5. Inventory errors — create system error incident ────────
        - name: "inventory_error_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/inventory/errors"
              qos: 1
          input_expression: >
            template:An inventory system error has been detected.
            You must immediately call the incidents_db tool and run this SQL INSERT exactly as written — do not modify the field values, do not describe it, just execute it:
            INSERT INTO incidents (incident_id, type, severity, status, title, description, created_date, last_updated)
            SELECT 'INC-' || to_char(NOW(), 'YYYY') || '-' || LPAD((COALESCE(MAX(CAST(SPLIT_PART(incident_id, '-', 3) AS INTEGER)), 0) + 1)::TEXT, 3, '0'),
            'system_error', 'high', 'investigating', 'Inventory System Error',
            'Inventory system error: {{text://input.payload:error}}',
            NOW(), NOW()
            FROM incidents WHERE incident_id LIKE 'INC-' || to_char(NOW(), 'YYYY') || '-%';
            After running the INSERT, return a JSON response with the created incident details (incident_id, type, severity, status, title, description, created_date).
            Error data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            error_source: "inventory"

        # ── 6. Order errors — create system error incident ────────────
        - name: "order_error_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/orders/errors"
              qos: 1
          input_expression: >
            template:An order system error has been detected.
            Create a new incident with type='system_error', severity='high',
            and set created_date and last_updated to NOW().
            Apply your escalation logic to determine the appropriate status based on severity.
            Populate the title with "Order System Error" and include the error details in the description.
            Return a JSON response with the created incident details.
            Error data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            error_source: "orders"

        # ── 7. Logistics errors — create system error incident ────────
        - name: "logistics_error_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/errors"
              qos: 1
          input_expression: >
            template:A logistics system error has been detected.
            You must immediately call the incidents_db tool and run this SQL INSERT exactly as written — do not modify the field values, do not describe it, just execute it:
            INSERT INTO incidents (incident_id, type, severity, status, title, description, created_date, last_updated)
            SELECT 'INC-' || to_char(NOW(), 'YYYY') || '-' || LPAD((COALESCE(MAX(CAST(SPLIT_PART(incident_id, '-', 3) AS INTEGER)), 0) + 1)::TEXT, 3, '0'),
            'system_error', 'high', 'investigating', 'Logistics System Error',
            'Logistics system error: {{text://input.payload:error}}',
            NOW(), NOW()
            FROM incidents WHERE incident_id LIKE 'INC-' || to_char(NOW(), 'YYYY') || '-%';
            After running the INSERT, return a JSON response with the created incident details (incident_id, type, severity, status, title, description, created_date).
            Error data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            error_source: "logistics"

      output_handlers:
        # Publishes incident creation events (triggered when new incidents are created)
        - name: "incident_created_handler"
          topic_expression: "static:acme/incidents/created"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"

        # Publishes incident response confirmations (for updates and final confirmations)
        - name: "incident_response_handler"
          topic_expression: "static:acme/incidents/response"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"

        # Error handler — publishes failures for observability
        - name: "error_handler"
          topic_expression: "static:acme/incidents/errors"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"'''
    if create_file(str(gateways_dir / 'acme-incidents-events.yaml'), content_acme_incidents_events, 'acme-incidents-events.yaml'):
        created += 1

    # acme-logistics-events.yaml
    content_acme_logistics_events = '''log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: acme-logistics-events.log

!include ../shared_config.yaml

apps:
  - name: acme-logistics-events-app
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "logistics-gw-01"
      artifact_service: *default_artifact_service
      authorization_service:
        type: "none"
        default_user_identity: "anonymous_event_mesh_user"
      
      event_mesh_broker_config:
        broker_url: ${SOLACE_BROKER_URL}
        broker_username: ${SOLACE_BROKER_USERNAME}
        broker_password: ${SOLACE_BROKER_PASSWORD}
        broker_vpn: ${SOLACE_BROKER_VPN}

      event_handlers:
        
        - name: "shipment_created_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/shipment-created"
              qos: 1
          input_expression: >
            template:A new shipment has been created.
            Create a shipment record in the database.
            Shipment data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "LogisticsAgent"
          on_success: "shipment_updated_handler"
          on_error: "error_handler"
          forward_context:
            shipment_id: "input.payload:shipment_id"
            order_id: "input.payload:order_id"
        
        - name: "status_changed_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/status-changed"
              qos: 1
          input_expression: >
            template:A shipment status update event has been received.
            Update the shipment record with the new status.
            Event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "LogisticsAgent"
          on_success: "shipment_updated_handler"
          on_error: "error_handler"
          forward_context:
            shipment_id: "input.payload:shipment_id"
            tracking_number: "input.payload:tracking_number"
        
        - name: "shipment_delayed_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/shipment-delayed"
              qos: 1
          input_expression: >
            template:A shipment delay event has been detected.
            Log the delay and recalculate estimated delivery.
            Event data: {{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "LogisticsAgent"
          on_success: "shipment_delayed_event_handler"
          on_error: "error_handler"
          forward_context:
            shipment_id: "input.payload:shipment_id"
            order_id: "input.payload:order_id"

      output_handlers:
        
        - name: "shipment_updated_handler"
          topic_expression: "static:acme/logistics/updated"
          payload_format: "json"
          payload_expression: "task_response:text"
        
        - name: "shipment_delayed_event_handler"
          topic_expression: "static:acme/logistics/updated"
          payload_format: "json"
          payload_expression: "task_response:text"
        
        - name: "error_handler"
          topic_expression: "static:acme/logistics/errors"
          payload_format: "json"
          payload_expression: "task_response:text"'''
    if create_file(str(gateways_dir / 'acme-logistics-events.yaml'), content_acme_logistics_events, 'acme-logistics-events.yaml'):
        created += 1
    return created


def main():
    if len(sys.argv) < 2:
        print("Usage: auto_create_agents_config.py <SAM_DIR>")
        sys.exit(1)
    
    sam_dir = Path(sys.argv[1])
    configs_dir = sam_dir / "configs"
    agents_dir = configs_dir / "agents"
    gateways_dir = configs_dir / "gateways"
    
    agents_dir.mkdir(parents=True, exist_ok=True)
    gateways_dir.mkdir(parents=True, exist_ok=True)
    
    # Count created vs skipped files
    agent_count = create_agents(agents_dir)
    gateway_count = create_gateways(gateways_dir)
    total_created = agent_count + gateway_count
    
    if total_created > 0:
        print(f"✅ Created {total_created} configuration file(s)")
    else:
        print("✅ All agent configuration complete")

if __name__ == "__main__":
    main()
