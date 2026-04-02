"""Database connection and query helpers."""

import psycopg2
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_CONN = os.getenv(
    "ORDERS_DB_CONNECTION_STRING",
    "postgresql://acme:acme@localhost:5432/orders"
)


def get_db_connection():
    """Get a new database connection."""
    return psycopg2.connect(DB_CONN)


def execute_query(sql: str, params: tuple = ()) -> List[Dict]:
    """Execute a SELECT query and return results as list of dicts."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise Exception(f"Query error: {str(e)}")


def execute_update(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return rows affected."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows_affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return rows_affected
    except Exception as e:
        conn.rollback()
        raise Exception(f"Update error: {str(e)}")


def get_shipment_by_id(shipment_id: str) -> Optional[Dict]:
    """Get full shipment record (with events) by shipment ID."""
    sql = """
    SELECT 
        s.shipment_id,
        s.order_id,
        s.carrier,
        s.tracking_number,
        s.service_level,
        s.status,
        s.ship_date,
        s.estimated_delivery,
        s.actual_delivery,
        s.cost
    FROM shipments s
    WHERE s.shipment_id = %s
    """
    results = execute_query(sql, (shipment_id,))
    
    if not results:
        return None
    
    shipment = results[0]
    
    # Get events for this shipment
    events_sql = """
    SELECT 
        timestamp,
        location,
        status,
        description
    FROM shipment_events
    WHERE shipment_id = %s
    ORDER BY timestamp ASC
    """
    events = execute_query(events_sql, (shipment['shipment_id'],))
    shipment['events'] = events
    
    return shipment


def get_shipment_by_tracking(tracking_number: str) -> Optional[Dict]:
    """Get full shipment record (with events) by tracking number."""
    sql = """
    SELECT 
        s.shipment_id,
        s.order_id,
        s.carrier,
        s.tracking_number,
        s.service_level,
        s.status,
        s.ship_date,
        s.estimated_delivery,
        s.actual_delivery,
        s.cost
    FROM shipments s
    WHERE s.tracking_number = %s
    """
    results = execute_query(sql, (tracking_number,))
    
    if not results:
        return None
    
    shipment = results[0]
    
    # Get events for this shipment
    events_sql = """
    SELECT 
        timestamp,
        location,
        status,
        description
    FROM shipment_events
    WHERE shipment_id = %s
    ORDER BY timestamp ASC
    """
    events = execute_query(events_sql, (shipment['shipment_id'],))
    shipment['events'] = events
    
    return shipment


def get_shipment_by_order(order_id: str) -> Optional[Dict]:
    """Get shipment(s) for an order."""
    sql = """
    SELECT 
        shipment_id,
        order_id,
        carrier,
        tracking_number,
        status,
        ship_date,
        estimated_delivery,
        actual_delivery
    FROM shipments
    WHERE order_id = %s
    ORDER BY shipment_id DESC
    """
    return execute_query(sql, (order_id,))


def get_shipments_by_status(status: str, limit: int = 100) -> List[Dict]:
    """Get all shipments with a specific status."""
    sql = """
    SELECT 
        shipment_id,
        order_id,
        carrier,
        tracking_number,
        status,
        estimated_delivery,
        ship_date
    FROM shipments
    WHERE status = %s
    ORDER BY ship_date DESC
    LIMIT %s
    """
    return execute_query(sql, (status, limit))


def get_delayed_shipments() -> List[Dict]:
    """Get shipments that are delayed (estimated_delivery < now)."""
    sql = """
    SELECT 
        shipment_id,
        order_id,
        carrier,
        tracking_number,
        estimated_delivery,
        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - estimated_delivery::timestamp)) / 3600 as delay_hours
    FROM shipments
    WHERE status NOT IN ('delivered', 'cancelled')
    AND estimated_delivery::timestamp < CURRENT_TIMESTAMP
    ORDER BY delay_hours DESC
    """
    return execute_query(sql)


def create_shipment(
    shipment_id: str,
    order_id: str,
    carrier_id: str,
    carrier_name: str,
    tracking_number: str,
    service_level: str,
    origin_facility: str,
    destination_city: str,
    destination_state: str,
    weight_lbs: float,
    estimated_delivery: datetime
) -> bool:
    """Create a new shipment and log initial event."""
    sql = """
    INSERT INTO shipments (
        shipment_id, order_id, carrier_id, carrier_name, tracking_number,
        service_level, origin_facility, destination_city, destination_state,
        weight_lbs, ship_date, estimated_delivery, current_status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    execute_update(sql, (
        shipment_id, order_id, carrier_id, carrier_name, tracking_number,
        service_level, origin_facility, destination_city, destination_state,
        weight_lbs, datetime.now(), estimated_delivery, 'created'
    ))
    
    log_shipment_event(
        shipment_id,
        event_type='created',
        event_timestamp=datetime.now(),
        event_details={'message': 'Shipment created and ready for pickup'}
    )
    
    return True


def update_shipment_status(
    shipment_id: str,
    new_status: str,
    event_timestamp: datetime,
    event_location: Optional[str] = None,
    event_details: Optional[dict] = None
) -> bool:
    """Update shipment status and log an event."""
    sql = """
    UPDATE shipments
    SET status = %s
    WHERE shipment_id = %s
    """
    
    execute_update(sql, (new_status, shipment_id))
    
    log_shipment_event(
        shipment_id,
        event_type='status_changed',
        event_timestamp=event_timestamp,
        event_location=event_location,
        event_details={
            'new_status': new_status,
            **(event_details or {})
        }
    )
    
    return True


def log_shipment_event(
    shipment_id: str,
    event_type: str,
    event_timestamp: datetime,
    event_location: Optional[str] = None,
    event_details: Optional[dict] = None
) -> int:
    """Log a shipment event (immutable)."""
    # Map to actual schema: timestamp, location, status, description
    sql = """
    INSERT INTO shipment_events (
        shipment_id, timestamp, location, status, description
    ) VALUES (%s, %s, %s, %s, %s)
    RETURNING id
    """
    
    # Use event_type as status, and event_details as description
    description = json.dumps(event_details) if event_details else event_type
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, (
            shipment_id,
            event_timestamp.isoformat() if isinstance(event_timestamp, datetime) else event_timestamp,
            event_location or '',
            event_type,
            description
        ))
        event_id = cur.fetchone()[0] if cur.description else None
        conn.commit()
        cur.close()
        conn.close()
        return event_id
    except Exception as e:
        if conn:
            conn.rollback()
        raise Exception(f"Event logging error: {str(e)}")


def log_delay(
    shipment_id: str,
    delay_hours: float,
    new_estimated_delivery: datetime,
    reason: str
) -> bool:
    """Log a delay event and update estimated delivery."""
    sql_update = """
    UPDATE shipments
    SET estimated_delivery = %s
    WHERE shipment_id = %s
    """
    
    execute_update(sql_update, (new_estimated_delivery, shipment_id))
    
    log_shipment_event(
        shipment_id,
        event_type='delayed',
        event_timestamp=datetime.now(),
        event_details={
            'delay_hours': delay_hours,
            'new_estimated_delivery': new_estimated_delivery.isoformat(),
            'reason': reason
        }
    )
    
    return True