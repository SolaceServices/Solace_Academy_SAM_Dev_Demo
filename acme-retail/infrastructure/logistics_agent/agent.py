"""Strands-powered Logistics Agent for Acme Retail."""

from strands import Agent, tool
from strands.models import OpenAIModel
from strands_tools import calculator, current_time
from logistics_agent.database import (
    get_shipment_by_tracking,
    get_shipment_by_order,
    get_shipments_by_status,
    get_delayed_shipments,
    log_delay
)
import json
import os


@tool
def track_shipment(tracking_number: str) -> str:
    """
    Track a shipment by tracking number.
    Returns: Current status, location, estimated delivery, and event history.
    """
    try:
        shipment = get_shipment_by_tracking(tracking_number)
        if not shipment:
            return json.dumps({
                "status": "not_found",
                "message": f"No shipment found with tracking number {tracking_number}"
            })
        
        return json.dumps({
            "status": "found",
            "shipment": shipment
        }, default=str)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def get_shipments_for_order(order_id: str) -> str:
    """
    Get all shipments for an order.
    Useful for order status queries and customer service.
    """
    try:
        shipments = get_shipment_by_order(order_id)
        return json.dumps({
            "status": "success",
            "order_id": order_id,
            "shipment_count": len(shipments),
            "shipments": shipments
        }, default=str)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def get_status_report(status: str) -> str:
    """
    Get all shipments with a specific status.
    Statuses: created, processing, shipped, in_transit, out_for_delivery, delivered, cancelled
    """
    valid_statuses = [
        'created', 'processing', 'shipped', 'in_transit',
        'out_for_delivery', 'delivered', 'cancelled'
    ]
    
    if status not in valid_statuses:
        return json.dumps({
            "status": "error",
            "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        })
    
    try:
        shipments = get_shipments_by_status(status)
        return json.dumps({
            "status": "success",
            "filter_status": status,
            "shipment_count": len(shipments),
            "shipments": shipments
        }, default=str)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def detect_delays() -> str:
    """
    Detect all delayed shipments (estimated delivery has passed).
    Returns list of delayed shipments with delay duration.
    """
    try:
        delayed = get_delayed_shipments()
        return json.dumps({
            "status": "success",
            "delayed_count": len(delayed),
            "delayed_shipments": delayed
        }, default=str)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def update_status_with_event(
    shipment_id: str,
    new_status: str,
    event_location: str = None,
    event_details: dict = None
) -> str:
    """
    Update shipment status and record an event.
    Valid statuses: created, processing, shipped, in_transit, out_for_delivery, delivered, cancelled
    """
    try:
        from datetime import datetime
        from logistics_agent.database import update_shipment_status
        
        update_shipment_status(
            shipment_id,
            new_status,
            datetime.now(),
            event_location,
            event_details
        )
        return json.dumps({
            "status": "success",
            "shipment_id": shipment_id,
            "new_status": new_status,
            "message": f"Shipment {shipment_id} status updated to {new_status}"
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


@tool
def log_shipment_delay(
    shipment_id: str,
    delay_hours: float,
    reason: str
) -> str:
    """
    Log a delay event for a shipment.
    Calculates new estimated delivery based on delay_hours.
    """
    try:
        from datetime import datetime, timedelta
        
        # Get current shipment to find estimated delivery
        shipment = get_shipment_by_tracking(shipment_id)
        if not shipment:
            return json.dumps({
                "status": "error",
                "message": f"Shipment {shipment_id} not found"
            })
        
        current_est = shipment.get('estimated_delivery')
        if not current_est:
            return json.dumps({
                "status": "error",
                "message": "Shipment has no estimated delivery date"
            })
        
        # Parse if string
        if isinstance(current_est, str):
            current_est = datetime.fromisoformat(current_est)
        
        new_est = current_est + timedelta(hours=delay_hours)
        
        log_delay(
            shipment_id,
            delay_hours,
            new_est,
            reason
        )
        
        return json.dumps({
            "status": "success",
            "shipment_id": shipment_id,
            "delay_hours": delay_hours,
            "reason": reason,
            "previous_estimated_delivery": current_est.isoformat(),
            "new_estimated_delivery": new_est.isoformat(),
            "message": f"Delay logged: {delay_hours} hours for reason: {reason}"
        }, default=str)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })


# Auto-detect LLM provider and configure appropriate Strands model
# This supports multiple providers through OpenAI-compatible interfaces

def detect_and_configure_model():
    """
    Detect the LLM provider from environment variables and configure the appropriate Strands model.
    
    Supports:
    - OpenAI (direct)
    - Anthropic Claude (via OpenAI-compatible proxies like LiteLLM)
    - Google Gemini (via OpenAI-compatible proxies)
    - AWS Bedrock (native support)
    - Azure OpenAI
    - Any OpenAI-compatible endpoint (LiteLLM, vLLM, Ollama, etc.)
    
    Note: For direct Anthropic API, use LiteLLM proxy or configure via OpenAI-compatible format.
    """
    from strands.models import OpenAIModel, BedrockModel
    
    # Get environment variables
    endpoint = os.getenv("LLM_SERVICE_ENDPOINT", "")
    model_name = os.getenv("LLM_SERVICE_GENERAL_MODEL_NAME", "")
    api_key = os.getenv("LLM_SERVICE_API_KEY", "")
    
    # Fallback to OPENAI_* variables if LLM_SERVICE_* not set
    if not endpoint:
        endpoint = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL", "")
    if not model_name:
        model_name = os.getenv("OPENAI_MODEL_NAME", "")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
    
    # Store original model name before processing
    original_model = model_name
    endpoint_lower = endpoint.lower() if endpoint else ""
    
    print(f"[LogisticsAgent] Detected endpoint: {endpoint[:60] if endpoint else 'default'}...")
    print(f"[LogisticsAgent] Detected model: {model_name}")
    
    # AWS Bedrock (native support)
    if "bedrock" in endpoint_lower or (model_name and "bedrock" in model_name.lower()):
        print("[LogisticsAgent] Using AWS Bedrock model")
        # Bedrock uses AWS credentials from environment (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # Strip any 'bedrock/' prefix from model name
        bedrock_model = model_name.replace("bedrock/", "") if model_name else "anthropic.claude-3-5-sonnet-20241022-v2:0"
        return BedrockModel(model_id=bedrock_model)
    
    # OpenAI or OpenAI-compatible (handles everything else)
    else:
        print("[LogisticsAgent] Using OpenAI-compatible model")
        
        # Default endpoint if none specified
        if not endpoint:
            endpoint = "https://api.openai.com/v1"
            print("[LogisticsAgent] No endpoint specified, defaulting to OpenAI")
        
        # Handle LiteLLM format (openai/model-name or anthropic/model-name)
        # LiteLLM needs the prefix stripped because it routes based on endpoint, not model prefix
        if original_model and "/" in original_model:
            # Strip the provider prefix (e.g., "openai/vertex-claude-4-5-sonnet" → "vertex-claude-4-5-sonnet")
            final_model = original_model.split("/", 1)[1]
            print(f"[LogisticsAgent] Stripped provider prefix from model name")
        else:
            # No prefix
            final_model = original_model if original_model else "gpt-4"
        
        print(f"[LogisticsAgent] Final model identifier: {final_model}")
        
        return OpenAIModel(
            client_args={
                "api_key": api_key,
                "base_url": endpoint,
            },
            model_id=final_model
        )

# Configure the model
configured_model = detect_and_configure_model()

logistics_agent = Agent(
    tools=[
        track_shipment,
        get_shipments_for_order,
        get_status_report,
        detect_delays,
        update_status_with_event,
        log_shipment_delay,
        calculator,
        current_time
    ],
    model=configured_model,
    system_prompt="""
You are the Logistics Agent for Acme Retail. You are responsible for all shipment 
tracking, carrier coordination, and delivery status management.

Your core responsibilities:
1. Track shipments by tracking number or order ID
2. Update shipment status as parcels progress through delivery
3. Log delays and recalculate estimated delivery dates
4. Detect and report delayed shipments
5. Provide status reports by shipment status or order

Data Integrity Rules:
- Always query the database for shipment data
- Log every status change as an immutable event
- Never modify orders, inventory, or incidents tables

Status Lifecycle:
created → processing → shipped → in_transit → out_for_delivery → delivered
                   └────────────────────────────────────────→ cancelled

When a delay is detected (current_time > estimated_delivery):
1. Log a 'delayed' event with delay duration
2. Recalculate estimated delivery
3. This automatically triggers incident detection in IncidentResponseAgent
""",
    callback_handler=None,
)