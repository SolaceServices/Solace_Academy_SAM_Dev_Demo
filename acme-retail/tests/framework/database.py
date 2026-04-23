"""
database.py — PostgreSQL assertion helpers for the tests framework.

Connects to the Acme orders database (seeded by seed_orders_db.py) and
provides helpers to assert on row state after agent actions.

Connection default: postgresql://acme:acme@localhost:5432/orders
Override via ORDERS_DB_CONNECTION_STRING env var.
"""

import os
from contextlib import contextmanager
from typing import Any, Optional

import psycopg2
import psycopg2.extras


_DEFAULT_DSN = os.environ.get(
    "ORDERS_DB_CONNECTION_STRING",
    "postgresql://acme:acme@localhost:5432/orders",
)


# ---------------------------------------------------------------------------
# Low-level connection helpers
# ---------------------------------------------------------------------------
def get_connection(dsn: Optional[str] = None):
    """Return a new psycopg2 connection (caller is responsible for closing)."""
    return psycopg2.connect(dsn or _DEFAULT_DSN)


@contextmanager
def db_cursor(dsn: Optional[str] = None):
    """
    Context manager that yields a DictCursor and auto-commits / rolls back.

    with db_cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE order_id = %s", ("ORD-001",))
        row = cur.fetchone()
    """
    conn = get_connection(dsn)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def fetch_order(order_id: str, dsn: Optional[str] = None) -> Optional[dict]:
    """Return the orders row for *order_id*, or None if not found."""
    with db_cursor(dsn) as cur:
        cur.execute(
            "SELECT * FROM orders WHERE order_id = %s",
            (order_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_order_items(order_id: str, dsn: Optional[str] = None) -> list[dict]:
    """Return all order_items rows for *order_id*."""
    with db_cursor(dsn) as cur:
        cur.execute(
            "SELECT * FROM order_items WHERE order_id = %s",
            (order_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def fetch_inventory(item_id: str, dsn: Optional[str] = None) -> Optional[dict]:
    """Return the inventory row for *item_id*, or None if not found."""
    with db_cursor(dsn) as cur:
        cur.execute(
            "SELECT * FROM inventory WHERE item_id = %s",
            (item_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_shipment(shipment_id: str, dsn: Optional[str] = None) -> Optional[dict]:
    """Return the shipments row for *shipment_id*, or None if not found."""
    with db_cursor(dsn) as cur:
        cur.execute(
            "SELECT * FROM shipments WHERE shipment_id = %s",
            (shipment_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_incident(incident_id: str, dsn: Optional[str] = None) -> Optional[dict]:
    """Return the incidents row for *incident_id*, or None if not found."""
    with db_cursor(dsn) as cur:
        cur.execute(
            "SELECT * FROM incidents WHERE incident_id = %s",
            (incident_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def row_count(table: str, where: str = "", params=(), dsn: Optional[str] = None) -> int:
    """
    Return the number of rows in *table* matching an optional WHERE clause.

    row_count("incidents", "type = %s AND status = %s", ("shipment_delay", "open"))
    """
    query = f"SELECT COUNT(*) FROM {table}"
    if where:
        query += f" WHERE {where}"
    with db_cursor(dsn) as cur:
        cur.execute(query, params)
        return cur.fetchone()["count"]


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------
class DBAssertionError(AssertionError):
    """Raised when a database assertion fails."""


def assert_order_status(
    order_id: str,
    expected_status: str,
    dsn: Optional[str] = None,
):
    """Assert that orders.status == expected_status for order_id."""
    order = fetch_order(order_id, dsn)
    if order is None:
        raise DBAssertionError(f"Order {order_id!r} not found in database")
    actual = order.get("status")
    if actual != expected_status:
        raise DBAssertionError(
            f"Order {order_id!r}: expected status {expected_status!r}, got {actual!r}"
        )


def assert_inventory_status(
    item_id: str,
    expected_status: str,
    dsn: Optional[str] = None,
):
    """Assert that inventory.status == expected_status for item_id."""
    inv = fetch_inventory(item_id, dsn)
    if inv is None:
        raise DBAssertionError(f"Inventory item {item_id!r} not found in database")
    actual = inv.get("status")
    if actual != expected_status:
        raise DBAssertionError(
            f"Inventory {item_id!r}: expected status {expected_status!r}, got {actual!r}"
        )


def assert_incident_exists(
    incident_type: str,
    related_id: str,
    id_column: str = "order_id",
    dsn: Optional[str] = None,
):
    """
    Assert that at least one incident row exists with:
      type = incident_type  AND  {id_column} = related_id

    id_column: one of 'order_id', 'shipment_id', or 'incident_id'
    """
    count = row_count(
        "incidents",
        where=f"type = %s AND {id_column} = %s",
        params=(incident_type, related_id),
        dsn=dsn,
    )
    if count == 0:
        raise DBAssertionError(
            f"Expected incident of type {incident_type!r} with "
            f"{id_column}={related_id!r} — none found"
        )


def set_inventory_quantity(
    item_id: str,
    stock_quantity: int,
    available_quantity: int,
    status: str = "in_stock",
    dsn: Optional[str] = None,
):
    """
    Directly update inventory quantities for an item.

    Used in test setup to simulate an inventory system updating the DB
    before publishing a restock event, so the agent sees consistent data
    from both the event payload and the database.
    """
    with db_cursor(dsn) as cur:
        cur.execute(
            """
            UPDATE inventory
               SET stock_quantity      = %s,
                   available_quantity  = %s,
                   status              = %s
             WHERE item_id = %s
            """,
            (stock_quantity, available_quantity, status, item_id),
        )


def assert_field_equals(
    table: str,
    pk_column: str,
    pk_value: Any,
    field: str,
    expected: Any,
    dsn: Optional[str] = None,
):
    """
    Generic field assertion.

    assert_field_equals("shipments", "shipment_id", "SHIP-001", "status", "delayed")
    """
    with db_cursor(dsn) as cur:
        cur.execute(
            f"SELECT {field} FROM {table} WHERE {pk_column} = %s",
            (pk_value,),
        )
        row = cur.fetchone()
        if row is None:
            raise DBAssertionError(
                f"No row found in {table!r} where {pk_column}={pk_value!r}"
            )
        actual = row[field]
        if actual != expected:
            raise DBAssertionError(
                f"{table}.{field} for {pk_column}={pk_value!r}: "
                f"expected {expected!r}, got {actual!r}"
            )


# ---------------------------------------------------------------------------
# Shipment-specific assertion helpers
# ---------------------------------------------------------------------------
def assert_shipment_status(
    shipment_id: str,
    expected_status: str,
    dsn: Optional[str] = None,
):
    """Assert that shipments.status == expected_status for shipment_id."""
    shipment = fetch_shipment(shipment_id, dsn)
    if shipment is None:
        raise DBAssertionError(f"Shipment {shipment_id!r} not found in database")
    actual = shipment.get("status")
    if actual != expected_status:
        raise DBAssertionError(
            f"Shipment {shipment_id!r}: expected status {expected_status!r}, got {actual!r}"
        )


def assert_shipment_delivery(
    shipment_id: str,
    expected_delivery: str,
    dsn: Optional[str] = None,
):
    """
    Assert that shipments.estimated_delivery matches expected timestamp.
    
    expected_delivery should be an ISO 8601 string (e.g., "2026-03-16T18:00:00Z")
    """
    shipment = fetch_shipment(shipment_id, dsn)
    if shipment is None:
        raise DBAssertionError(f"Shipment {shipment_id!r} not found in database")
    actual = shipment.get("estimated_delivery")
    # Convert to string for comparison (handles timezone formatting)
    actual_str = actual.isoformat() if hasattr(actual, "isoformat") else str(actual)
    
    # Normalize both strings - handle various PostgreSQL timestamp formats
    # PostgreSQL: "2026-03-16 18:00:00+00" or "2026-03-16T18:00:00+00:00"
    # Expected: "2026-03-16T18:00:00Z"
    def normalize_timestamp(ts: str) -> str:
        ts = ts.strip()
        # Replace space with T
        ts = ts.replace(" ", "T")
        # Replace +00:00 or +00 with Z
        ts = ts.replace("+00:00", "Z").replace("+00", "Z")
        # Remove microseconds if present
        ts = ts.replace(".000000Z", "Z")
        return ts
    
    actual_normalized = normalize_timestamp(actual_str)
    expected_normalized = normalize_timestamp(expected_delivery)
    
    if actual_normalized != expected_normalized:
        raise DBAssertionError(
            f"Shipment {shipment_id!r} estimated_delivery: "
            f"expected {expected_delivery!r}, got {actual_str!r}"
        )


def shipment_event_count(
    shipment_id: str,
    event_status: Optional[str] = None,
    dsn: Optional[str] = None,
) -> int:
    """
    Count shipment_events for a given shipment (optionally filtered by status).
    
    shipment_event_count("SHIP-001")                    # all events
    shipment_event_count("SHIP-001", "status_changed")  # only status_changed events
    """
    if event_status:
        return row_count(
            "shipment_events",
            where="shipment_id = %s AND status = %s",
            params=(shipment_id, event_status),
            dsn=dsn,
        )
    else:
        return row_count(
            "shipment_events",
            where="shipment_id = %s",
            params=(shipment_id,),
            dsn=dsn,
        )
