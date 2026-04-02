"""Strands-powered Logistics Agent for Acme Retail."""

from strands import Agent, tool
from strands.models import OpenAIModel
from strands_tools import calculator, current_time
from logistics_agent.database import (
    get_shipment_by_id,
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
        
        # Fetch the updated shipment to return complete details
        shipment = get_shipment_by_id(shipment_id)
        if shipment:
            return json.dumps({
                "status": "success",
                "shipment_id": shipment_id,
                "tracking_number": shipment.get("tracking_number"),
                "new_status": new_status,
                "carrier": shipment.get("carrier"),
                "estimated_delivery": str(shipment.get("estimated_delivery")),
                "action_performed": f"updated status to {new_status}",
                "message": f"Shipment {shipment_id} status updated to {new_status}"
            }, default=str)
        else:
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
    new_estimated_delivery: str,
    reason: str
) -> str:
    """
    Log a delay event for a shipment and update the estimated delivery.
    
    Args:
        shipment_id: The shipment ID (e.g., SHIP-2026-0050)
        delay_hours: Number of hours delayed
        new_estimated_delivery: The new estimated delivery timestamp (ISO format)
        reason: Reason for the delay
    """
    try:
        from datetime import datetime
        
        # Parse the new estimated delivery
        if isinstance(new_estimated_delivery, str):
            new_est = datetime.fromisoformat(new_estimated_delivery.replace('Z', '+00:00'))
        else:
            new_est = new_estimated_delivery
        
        # Call the database function to log the delay
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
You are the Logistics Agent for Acme Retail shipment tracking system.

YOU DO NOT HAVE DIRECT ACCESS TO THE DATABASE. You can ONLY interact with the database through the tools provided to you.

YOU MUST USE TOOLS FOR EVERY REQUEST. Do not make up responses or pretend to update data.

YOUR AVAILABLE TOOLS:
- update_status_with_event: Updates shipment status in database and logs event
- log_shipment_delay: Updates delivery time and logs delay event  
- track_shipment: Retrieves shipment details by tracking number
- get_shipments_for_order: Retrieves shipments by order ID
- detect_delays: Finds shipments past their estimated delivery
- get_status_report: Lists shipments by status

WHEN YOU RECEIVE A STATUS UPDATE EVENT:
1. Parse the event data to extract: shipment_id, new_status, location
2. YOU MUST call update_status_with_event(shipment_id, new_status, location)
3. Return the tool result as JSON

WHEN YOU RECEIVE A DELAY EVENT:
1. Parse the event data to extract: shipment_id, delay_hours, new_estimated_delivery, reason
2. YOU MUST call log_shipment_delay(shipment_id, delay_hours, new_estimated_delivery, reason)
3. Return the tool result as JSON

WHEN YOU RECEIVE A TRACKING REQUEST:
1. Extract the tracking_number
2. Call track_shipment(tracking_number)
3. Return the tool result

DO NOT fabricate shipment data. DO NOT describe what you would do. DO NOT return mock data.
You MUST call the appropriate tool for every request.

After calling a tool, format its result as clean JSON (remove any markdown code blocks).
""",
    callback_handler=None,
)