"""Type-safe models for Logistics Agent using Pydantic."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ShipmentCreateRequest(BaseModel):
    """Input: Create a new shipment."""
    order_id: str
    carrier_id: str
    tracking_number: str
    service_level: str
    origin_facility: str
    destination_city: str
    destination_state: str
    weight_lbs: float
    estimated_delivery: datetime


class ShipmentStatusUpdate(BaseModel):
    """Input: Update shipment status."""
    shipment_id: str
    new_status: str
    event_timestamp: datetime
    event_location: Optional[str] = None
    event_details: Optional[dict] = None


class ShipmentEvent(BaseModel):
    """Output: Shipment event."""
    shipment_id: str
    event_type: str
    event_timestamp: datetime
    event_location: Optional[str]
    event_details: Optional[dict]


class ShipmentResponse(BaseModel):
    """Output: Full shipment record."""
    shipment_id: str
    order_id: str
    carrier_name: str
    tracking_number: str
    current_status: str
    ship_date: datetime
    estimated_delivery: Optional[datetime]
    actual_delivery: Optional[datetime]
    events: List[ShipmentEvent]