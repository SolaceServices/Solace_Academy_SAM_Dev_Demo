"""FastAPI HTTP server for Strands Logistics Agent."""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from logistics_agent.agent import logistics_agent
import uvicorn
import uuid
import json

# Configure LiteLLM endpoint for Strands agent
# Strands expects OPENAI_* env vars when using openai/ model prefix
# Try multiple possible env var names for flexibility
api_base = os.getenv("LLM_SERVICE_ENDPOINT") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_ENDPOINT") or "https://lite-llm.mymaas.net"
api_key = os.getenv("LLM_SERVICE_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

# Set the variables that Strands/LiteLLM will actually use
os.environ["OPENAI_API_BASE"] = api_base
os.environ["OPENAI_BASE_URL"] = api_base
os.environ["OPENAI_API_KEY"] = api_key

print(f"[LogisticsAgent] Configured LLM endpoint: {api_base[:30]}...")
print(f"[LogisticsAgent] API Key configured: {'Yes' if api_key else 'No'}")

app = FastAPI(title="LogisticsAgent", version="1.0.0")


AGENT_CARD = {
    "name": "LogisticsAgent",
    "displayName": "Logistics Agent",
    "description": (
        "Strands-powered Logistics Agent responsible for shipment tracking, "
        "carrier coordination, delivery status updates, and logistics analytics."
    ),
    "version": "1.0.0",
    "capabilities": {
        "text": True,
        "json": True
    },
    "defaultInputModes": ["text", "json"],
    "defaultOutputModes": ["text", "json"],
    "skills": [
        {
            "id": "track_shipment",
            "name": "Track Shipment",
            "description": "Look up current status, location, and event history of a shipment",
            "tags": ["tracking", "shipment"]
        },
        {
            "id": "get_shipments_for_order",
            "name": "Get Shipments for Order",
            "description": "Retrieve all shipments associated with a specific order ID",
            "tags": ["order", "shipment"]
        },
        {
            "id": "get_status_report",
            "name": "Get Status Report",
            "description": "Get all shipments with a specific status",
            "tags": ["status", "report"]
        },
        {
            "id": "detect_delays",
            "name": "Detect Delays",
            "description": "Identify all shipments that are delayed",
            "tags": ["delay", "detection"]
        },
        {
            "id": "update_status_with_event",
            "name": "Update Status",
            "description": "Update a shipment's status and record an event",
            "tags": ["update", "status", "event"]
        },
        {
            "id": "log_shipment_delay",
            "name": "Log Delay",
            "description": "Log a delay event and recalculate estimated delivery",
            "tags": ["delay", "logging"]
        },
    ],
    "url": "http://localhost:8100",
}


@app.get("/.well-known/agent.json")
async def agent_card():
    """A2A Discovery Endpoint."""
    return JSONResponse(AGENT_CARD)


@app.get("/.well-known/agent-card.json")
async def agent_card_alt():
    """A2A Discovery Endpoint (alternate name for SAM compatibility)."""
    return JSONResponse(AGENT_CARD)


@app.post("/")
async def handle_task(request: Request):
    """Handle task requests from SAM (A2A protocol endpoint)."""
    body = await request.json()
    
    # Extract user message from various possible formats
    user_message = None
    
    # Try SAM A2A format: {"input": {"text": "..."}}
    if "input" in body:
        if isinstance(body["input"], dict):
            user_message = body["input"].get("text")
        elif isinstance(body["input"], str):
            user_message = body["input"]
    
    # Try message.parts format: {"message": {"parts": [{"type": "text", "text": "..."}]}}
    if not user_message and "message" in body:
        parts = body.get("message", {}).get("parts", [])
        user_message = next(
            (p.get("text", "") for p in parts if p.get("type") == "text"),
            None
        )
    
    # Fallback: try direct text field
    if not user_message:
        user_message = body.get("text")
    
    # Last resort: stringify the body
    if not user_message:
        user_message = json.dumps(body)
    
    task_id = body.get("id", str(uuid.uuid4()))
    
    print(f"[LogisticsAgent] Received task {task_id}: {user_message[:100]}...")
    
    try:
        if not user_message or not user_message.strip():
            raise ValueError("Empty message received")
        
        result = logistics_agent(user_message)
        response_text = str(result)
        
        print(f"[LogisticsAgent] Task {task_id} completed successfully")
        
        # A2A protocol success format - full Task response
        artifact_id = f"artifact-{task_id}"
        return {
            "id": task_id,
            "result": {
                "id": task_id,
                "contextId": f"context-{task_id}",
                "status": {
                    "state": "completed"
                },
                "artifacts": [{
                    "artifactId": artifact_id,
                    "parts": [{"type": "text", "text": response_text}]
                }]
            }
        }
    except Exception as e:
        print(f"[LogisticsAgent] Task {task_id} failed: {str(e)}")
        # A2A protocol error format (JSONRPC-style)
        return {
            "id": task_id,
            "error": {
                "code": -32000,
                "message": str(e)
            }
        }

@app.post("/a2a")
async def handle_a2a_task(request: Request):
    """Handle A2A protocol task requests from SAM (primary A2A endpoint)."""
    return await handle_task(request)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "LogisticsAgent", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)