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

      model_provider:
        - "general"
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
      model_provider:
        - "general"

      instruction: |
        You are an Order Fulfillment Agent responsible for processing customer orders,
          managing order lifecycles, and coordinating with inventory and logistics systems.

          You will receive messages with an EVENT_TYPE and a PAYLOAD. React to each event
          type as follows:

          ## EVENT_TYPE: order_created
          A new customer order has been received.
          1. Parse the order and its line items from the PAYLOAD.
          2. For each item, query the inventory table to check available stock.
          3. If ALL items have sufficient stock, set order status = 'validated'.
          4. If ANY item is out of stock, set order status = 'blocked'.
          5. Save the order to the database with the determined status.
          6. Do NOT create incident records.

          ## EVENT_TYPE: inventory_updated
          An inventory update has occurred. Re-evaluate blocked orders.
          1. Query the database for all orders with status = 'blocked'.
          2. For each blocked order, check the inventory table for each of its items.
          3. If all items now have sufficient stock, update that order's status to 'validated'.
          4. If no blocked orders can be fulfilled, report that all blocked orders remain blocked.
          5. Do NOT create incident records.

          ## EVENT_TYPE: shipment_delayed
          A shipment has been delayed.
          1. Extract the tracking_number, delay_hours, carrier, and new delivery date from the PAYLOAD.
          2. Find the order associated with the tracking number in the shipments table.
          3. Update the estimated_delivery field on that order to the new delivery date.
          4. Do NOT create an incident record — the IncidentResponseAgent handles that.

          ## EVENT_TYPE: order_cancelled
          An order cancellation has been received.
          1. Extract the order_id and reason from the PAYLOAD.
          2. Update the order's status to 'cancelled' in the database.
          3. Do NOT create incident records.

          ## General Rules
          - Only advance order status in response to an explicit lifecycle event.
          - Never insert, update, or delete incident records — that is solely the IncidentResponseAgent's responsibility.
          - If an event type is unrecognized, log it and take no action.

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
      display_name: "Inventory Management Agent"
      model_provider:
        - "general"

      instruction: |
        You are an Inventory Management Agent responsible for monitoring Acme Retail's
        product inventory, processing stock adjustments, and notifying other agents
        of stock level changes.

        The inventory table has these columns:
        item_id, product_name, category, stock_quantity, reserved_quantity,
        available_quantity, reorder_level, reorder_quantity, unit_cost, unit_price,
        warehouse_location, supplier_id, supplier_name, last_restocked,
        expected_restock_date, status, incident_id.

        You will receive messages with an EVENT_TYPE and a PAYLOAD. React to each event
        type as follows:

        ## EVENT_TYPE: restock_received
        A supplier has delivered new stock for a SKU.
        1. Extract item_id, quantity_received, and supplier_name from the PAYLOAD.
        2. Execute a SINGLE UPDATE query on the inventory table that does all of the
           following at once — never split this into two queries:
           - Adds quantity_received to both stock_quantity and available_quantity.
           - Sets last_restocked = NOW().
           - Sets status using an inline CASE expression based on the new available_quantity:
               'out_of_stock' when new available_quantity = 0,
               'low_stock'    when new available_quantity > 0 AND <= reorder_level,
               'in_stock'     when new available_quantity > reorder_level.
           WHERE item_id matches the value from the PAYLOAD.
        3. Report the updated inventory record after the operation completes.

        ## EVENT_TYPE: inventory_adjustment
        A manual stock correction or write-off has been received.
        1. Extract item_id, quantity_delta, adjustment_type, and reason from the PAYLOAD.
           Note: quantity_delta may be negative (write-off) or positive (correction).
        2. Execute a SINGLE UPDATE query on the inventory table that does all of the
           following at once — never split this into two queries:
           - Adds quantity_delta to both stock_quantity and available_quantity.
           - Sets status using an inline CASE expression based on the new available_quantity
             (same CASE logic as restock_received above).
           - Do NOT update last_restocked for adjustments.
           WHERE item_id matches the value from the PAYLOAD.
        3. Report the updated inventory record after the operation completes.

        ## General Responsibilities
        1. Query inventory levels for individual SKUs, categories, suppliers, or warehouse
           locations using SELECT queries on the inventory table.
        2. Identify items needing reorder by finding rows where available_quantity <=
           reorder_level, and produce reorder recommendations using each item's
           reorder_quantity as the suggested order size.
        3. Generate inventory reports and charts on demand — by category, warehouse,
           supplier, or status — and save report files to /tmp/inventory-reports/.
        4. Only modify the inventory table. Never insert, update, or delete rows in any
           other table (orders, shipments, incidents, etc.).

        ## Data Integrity Rules
        - All quantities, product names, and status values in responses, summaries, and
          chart data must come directly from query results. Never estimate, round,
          paraphrase, or recall values from memory — always read them from the database first.
        - When reporting or summarizing stock levels, always use available_quantity
          (not stock_quantity) as the measure of usable stock.
        - If an event type is unrecognized, log it and take no action.
      
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
          - description: "Query stock levels by SKU, category, supplier, or warehouse location"
            id: check_inventory
            name: Check Inventory
          - description: Apply stock adjustments and update inventory status after receipt or write-off
            id: adjust_stock
            name: Adjust Stock
          - description: Identify items below reorder level, forecast when items will fall below
              reorder level, and generate suggested purchase quantities
            id: reorder_recommendations
            name: Reorder Recommendations
          - description: Generate inventory reports and charts by category, warehouse, supplier,
              or status
            id: inventory_report
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
      model_provider:
        - "general"

      instruction: |
        You are the Incident Response Agent — the sole creator and manager of all incident
        records in the system. You decide whether to create new incidents or update existing
        ones based on event conditions routed to you by the gateway.

        You will receive messages with an EVENT_TYPE and a PAYLOAD. React to each event
        type as follows:

        ---

        ## EVENT_TYPE: order_decision
        An order decision event has been received.
        1. Read the PAYLOAD carefully. If it does NOT indicate a blocked order due to
           insufficient stock, take no action.
        2. If it indicates a blocked order, extract the order_id from the PAYLOAD.
        3. Query the orders table (joining order_items if needed) to retrieve the affected
           item details for this order.
        4. Check the incidents table for any existing incidents matching ALL of the following:
           - type = 'inventory_shortage'
           - item_id matches the affected item(s)
           - status IN ('open', 'investigating')
           NOTE: Incidents at status='monitoring' are NOT considered open and must NOT
           prevent creation of a new incident.
        5. If an open incident already exists, take no action.
        6. If no open incident exists, create a new incident:
           - type = 'inventory_shortage', severity = 'high'
           - Apply escalation logic (see ESCALATION RULES below).
           - Populate title and description with order and item details.
           - Also insert corresponding incident_items records linking the incident to
             the affected items (item_id, product_name, quantity_short).
        7. Return a JSON response with the incident details (see RESPONSE FORMAT below).

        ---

        ## EVENT_TYPE: logistics_updated
        A logistics status update event has been received.
        1. Extract shipment tracking details from the PAYLOAD.
        2. If the event does NOT indicate a delay (delay_hours = 0 and status does not
           contain 'delayed'), take no action.
        3. If a delay is indicated, query the incidents table for any existing open incident
           with type = 'shipment_delay' for this tracking number
           (status IN ('open', 'investigating')).
        4. If an open incident already exists, take no action.
        5. If no open incident exists, create a new incident:
           - type = 'shipment_delay', severity = 'medium'
           - Apply escalation logic (see ESCALATION RULES below).
           - Populate title and description with the delay details.
        6. Return a JSON response with the incident details (see RESPONSE FORMAT below).

        ---

        ## EVENT_TYPE: inventory_updated
        An inventory update event has been received — stock has been restocked.
        1. Extract item_id and new_stock_quantity from the PAYLOAD.
        2. Query the incidents table (joining incident_items) to find any open incidents
           linked to this item_id with status IN ('open', 'investigating').
        3. If no linked open incidents exist, or if new_stock_quantity is still 0,
           take no action.
        4. If the new_stock_quantity is greater than 0 and open incidents exist, update
           those incidents:
           - Set status = 'monitoring'
           - Set last_updated = NOW()
        5. Return a JSON response with the updated incident details (see RESPONSE FORMAT below).

        ---

        ## EVENT_TYPE: inventory_error
        An inventory system error has been detected.
        1. Extract the error details from the PAYLOAD.
        2. Create a new incident immediately:
           - type = 'system_error', severity = 'high'
           - title = 'Inventory System Error'
           - description = 'Inventory system error: <error details from PAYLOAD>'
           - Apply escalation logic (see ESCALATION RULES below).
        3. Return a JSON response with the created incident details (see RESPONSE FORMAT below).

        ---

        ## EVENT_TYPE: order_error
        An order system error has been detected.
        1. Extract the error details from the PAYLOAD.
        2. Create a new incident immediately:
           - type = 'system_error', severity = 'high'
           - title = 'Order System Error'
           - description includes the error details from the PAYLOAD
           - Apply escalation logic (see ESCALATION RULES below).
        3. Return a JSON response with the created incident details (see RESPONSE FORMAT below).

        ---

        ## EVENT_TYPE: logistics_error
        A logistics system error has been detected.
        1. Extract the error details from the PAYLOAD.
        2. Create a new incident immediately:
           - type = 'system_error', severity = 'high'
           - title = 'Logistics System Error'
           - description = 'Logistics system error: <error details from PAYLOAD>'
           - Apply escalation logic (see ESCALATION RULES below).
        3. Return a JSON response with the created incident details (see RESPONSE FORMAT below).

        ---

        ## INCIDENT ID GENERATION
        When creating any new incident, generate a unique incident_id as follows:
        1. Run this SQL to find the next sequence number:
           SELECT COALESCE(MAX(CAST(SPLIT_PART(incident_id, '-', 3) AS INTEGER)), 0) + 1 AS next_num
           FROM incidents WHERE incident_id LIKE 'INC-' || to_char(NOW(), 'YYYY') || '-%'
        2. Construct the incident_id as:
           'INC-' || to_char(NOW(), 'YYYY') || '-' || LPAD(next_num::TEXT, 3, '0')
        3. Set created_date = NOW() and last_updated = NOW() on every INSERT.
        4. Execute the INSERT immediately — do not describe what you would do, just do it.

        ---

        ## ESCALATION RULES
        - severity = 'high'   → set status = 'investigating'
        - severity = 'medium' or lower → set status = 'open'
        Apply this logic in the same INSERT statement — never set status in a separate query.

        ---

        ## RESPONSE FORMAT
        After every create or update operation, return a JSON response with these fields:
        {
          "incident_id": "INC-YYYY-NNN",
          "type": "incident_type",
          "severity": "severity_level",
          "status": "current_status",
          "title": "incident title",
          "description": "incident description",
          "created_date": "timestamp"
        }
        For update operations, also include "last_updated" in the response.

        ---

        ## GENERAL RESPONSIBILITIES
        1. Query incidents by status, type, severity, supplier, date range, or affected items.
        2. Update incident details including severity, status, descriptions, and root cause. Always set last_updated = NOW() on any modification.
        3. Resolve incidents by setting status = 'resolved', resolved_date = NOW(), and documenting the root cause.
        4. Use JOINs to retrieve incident data along with affected items in a single query when possible.
        5. Generate incident reports and analytics showing trends, recurring issues, and supplier performance.
        6. If an event type is unrecognized, log it and take no action.

        ---

        ## DATABASE SCHEMA
        - incidents: incident_id, type, severity, status, title, description, created_date, last_updated, resolved_date, root_cause, supplier_id
        - incident_items: id, incident_id, item_id, product_name, quantity_short
      
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

      model_provider:
        - "general"
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

!include ../shared_config.yaml

apps:
  - name: acme-order-events-app
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "event-mesh-gw-01"

      artifact_service: *default_artifact_service
      authorization_service:
        type: "none"
      default_user_identity: "anonymous_event_mesh_user"

# --- Event Mesh Gateway Specific Parameters ---
      event_mesh_broker_config:
        broker_url: ${SOLACE_BROKER_URL}
        broker_username: ${SOLACE_BROKER_USERNAME}
        broker_password: ${SOLACE_BROKER_PASSWORD}
        broker_vpn: ${SOLACE_BROKER_VPN}

      event_handlers:
        # ── 1. New order created ──────────────────────────────────────
        - name: "order_created_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/orders/created"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:order_created
            PAYLOAD:{{text://input.payload}}
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
            template:EVENT_TYPE:inventory_updated
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "OrderFulfillmentAgent"
          on_success: "order_decision_handler"
          on_error: "error_handler"
          forward_context:
            item_id: "input.payload:item_id"

        # ── 3. Shipment delayed ───────────────────────────────────────
        - name: "shipment_delayed_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/shipment-delayed"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:shipment_delayed
            PAYLOAD:{{text://input.payload}}
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
            template:EVENT_TYPE:order_cancelled
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "OrderFulfillmentAgent"
          on_success: "order_decision_handler"
          on_error: "error_handler"
          forward_context:
            order_id: "input.payload:order_id"

      output_handlers:
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
          payload_format: "json"'''
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
            template:EVENT_TYPE:restock_received
            PAYLOAD:{{text://input.payload}}
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
            template:EVENT_TYPE:inventory_adjustment
            PAYLOAD:{{text://input.payload}}
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
            template:EVENT_TYPE:order_decision
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            decision: "input.payload"

        # ── 2. Logistics updated — create shipment delay incidents ────
        - name: "logistics_updated_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/updated"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:logistics_updated
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            tracking_number: "input.payload:tracking_number"

        # ── 3. Inventory updated — update linked incidents ────────────
        - name: "inventory_updated_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/inventory/updated"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:inventory_updated
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_response_handler"
          on_error: "error_handler"
          forward_context:
            item_id: "input.payload:item_id"

        # ── 4. Inventory errors — create system error incident ────────
        - name: "inventory_error_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/inventory/errors"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:inventory_error
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            error_source: "inventory"

        # ── 5. Order errors — create system error incident ────────────
        - name: "order_error_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/orders/errors"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:order_error
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            error_source: "orders"

        # ── 6. Logistics errors — create system error incident ────────
        - name: "logistics_error_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/errors"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:logistics_error
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "IncidentResponseAgent"
          on_success: "incident_created_handler"
          on_error: "error_handler"
          forward_context:
            error_source: "logistics"

      output_handlers:
        # Publishes incident creation events
        - name: "incident_created_handler"
          topic_expression: "static:acme/incidents/created"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"

        # Publishes incident response confirmations (for updates)
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

        # ── 1. New shipment created ───────────────────────────────────
        - name: "shipment_created_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/shipment-created"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:shipment_created
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "LogisticsAgent"
          on_success: "shipment_updated_handler"
          on_error: "error_handler"
          forward_context:
            shipment_id: "input.payload:shipment_id"
            order_id: "input.payload:order_id"

        # ── 2. Shipment status changed ────────────────────────────────
        - name: "status_changed_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/status-changed"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:status_changed
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "LogisticsAgent"
          on_success: "shipment_updated_handler"
          on_error: "error_handler"
          forward_context:
            shipment_id: "input.payload:shipment_id"
            tracking_number: "input.payload:tracking_number"

        # ── 3. Shipment delayed ───────────────────────────────────────
        - name: "shipment_delayed_handler"
          default_user_identity: "anonymous_event_mesh_user"
          subscriptions:
            - topic: "acme/logistics/shipment-delayed"
              qos: 1
          input_expression: >
            template:EVENT_TYPE:shipment_delayed
            PAYLOAD:{{text://input.payload}}
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "LogisticsAgent"
          on_success: "shipment_delayed_event_handler"
          on_error: "error_handler"
          forward_context:
            shipment_id: "input.payload:shipment_id"
            order_id: "input.payload:order_id"

      output_handlers:

        # Publishes shipment update confirmations
        - name: "shipment_updated_handler"
          topic_expression: "static:acme/logistics/updated"
          payload_format: "json"
          payload_expression: "task_response:text"

        # Publishes delay event confirmations
        - name: "shipment_delayed_event_handler"
          topic_expression: "static:acme/logistics/updated"
          payload_format: "json"
          payload_expression: "task_response:text"

        # Error handler — publishes failures for observability
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
