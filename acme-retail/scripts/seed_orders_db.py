"""
seed_orders_db.py
-----------------
Populates the Acme Retail orders PostgreSQL database from JSON seed files.

Reads from:  acme-retail/data/seed-data/*.json
Writes to:   PostgreSQL at localhost:5432/orders (via psycopg2)

Tables populated:
  orders            <- orders.json
  order_items       <- orders.json        (items[] per order)
  inventory         <- inventory.json
  shipments         <- logistics.json
  shipment_events   <- logistics.json     (events[] per shipment)  * created if missing
  incidents         <- incidents.json
  incident_items    <- incidents.json     (affected_items[] per incident)  * created if missing

Prerequisites:
  pip install psycopg2-binary

Usage:
    python scripts/seed_orders_db.py
    python scripts/seed_orders_db.py --root /workspaces/Solace_Academy_SAM_Dev_Demo
    python scripts/seed_orders_db.py --db-url postgresql://acme:acme@localhost:5432/orders

Idempotent — safe to re-run at any time. Clears and repopulates all tables so
the DB always reflects the current state of the JSON source files.
"""

import argparse
import json
import os
import sys

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

REPO_ROOT      = "/workspaces/Solace_Academy_SAM_Dev_Demo"
SEED_DATA_DIR  = "acme-retail/data/seed-data"
DEFAULT_DB_URL = "postgresql://acme:acme@localhost:5432/orders"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    if not os.path.exists(path):
        print(f"  [SKIP] Not found: {path}")
        return {}
    with open(path, "r") as f:
        return json.load(f)


def ensure_extra_tables(cur):
    """
    Create shipment_events and incident_items tables if they don't already exist.
    These store nested arrays from logistics.json and incidents.json that
    aren't covered by the original schema.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shipment_events (
            id            SERIAL PRIMARY KEY,
            shipment_id   TEXT REFERENCES shipments(shipment_id),
            timestamp     TEXT,
            location      TEXT,
            status        TEXT,
            description   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_items (
            id             SERIAL PRIMARY KEY,
            incident_id    TEXT REFERENCES incidents(incident_id),
            item_id        TEXT,
            product_name   TEXT,
            quantity_short INTEGER
        )
    """)
    print("  ✓ Extra tables verified (shipment_events, incident_items).")


# ---------------------------------------------------------------------------
# Seeders
# ---------------------------------------------------------------------------

def seed_orders(cur, data: dict):
    if not data:
        return
    orders = data.get("orders", [])
    print(f"  Seeding {len(orders)} orders...")

    cur.execute("DELETE FROM shipment_events")
    cur.execute("DELETE FROM incident_items")
    cur.execute("DELETE FROM incidents")
    cur.execute("DELETE FROM shipments")
    cur.execute("DELETE FROM order_items")
    cur.execute("DELETE FROM orders")

    for o in orders:
        addr = o.get("shipping_address", {})
        cur.execute("""
            INSERT INTO orders (
                order_id, customer_id, customer_name, customer_email,
                order_date, status, priority, total_amount, currency,
                shipping_street, shipping_city, shipping_state,
                shipping_zip, shipping_country,
                shipment_id, tracking_number,
                estimated_delivery, delivery_date,
                cancelled_date, cancellation_reason,
                incident_id, notes
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            ON CONFLICT (order_id) DO UPDATE SET
                status              = EXCLUDED.status,
                tracking_number     = EXCLUDED.tracking_number,
                estimated_delivery  = EXCLUDED.estimated_delivery,
                delivery_date       = EXCLUDED.delivery_date,
                cancelled_date      = EXCLUDED.cancelled_date,
                cancellation_reason = EXCLUDED.cancellation_reason,
                incident_id         = EXCLUDED.incident_id,
                notes               = EXCLUDED.notes
        """, (
            o.get("order_id"),        o.get("customer_id"),
            o.get("customer_name"),   o.get("customer_email"),
            o.get("order_date"),      o.get("status"),
            o.get("priority"),        o.get("total_amount"),
            o.get("currency", "USD"),
            addr.get("street"),       addr.get("city"),
            addr.get("state"),        addr.get("zip"),
            addr.get("country"),
            o.get("shipment_id"),     o.get("tracking_number"),
            o.get("estimated_delivery"), o.get("delivery_date"),
            o.get("cancelled_date"),  o.get("cancellation_reason"),
            o.get("incident_id"),     o.get("notes"),
        ))

        for item in o.get("items", []):
            cur.execute("""
                INSERT INTO order_items (
                    order_id, item_id, product_name,
                    quantity, unit_price, total_price
                ) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (
                o.get("order_id"),        item.get("item_id"),
                item.get("product_name"), item.get("quantity"),
                item.get("unit_price"),   item.get("total_price"),
            ))

    print("  ✓ orders + order_items seeded.")


def seed_inventory(cur, data: dict):
    if not data:
        return
    items = data.get("inventory", [])
    print(f"  Seeding {len(items)} inventory items...")
    cur.execute("DELETE FROM inventory")

    for item in items:
        cur.execute("""
            INSERT INTO inventory (
                item_id, product_name, category,
                stock_quantity, reserved_quantity, available_quantity,
                reorder_level, reorder_quantity,
                unit_cost, unit_price,
                warehouse_location, supplier_id, supplier_name,
                last_restocked, expected_restock_date,
                status, incident_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (item_id) DO UPDATE SET
                stock_quantity      = EXCLUDED.stock_quantity,
                reserved_quantity   = EXCLUDED.reserved_quantity,
                available_quantity  = EXCLUDED.available_quantity,
                status              = EXCLUDED.status,
                incident_id         = EXCLUDED.incident_id,
                last_restocked      = EXCLUDED.last_restocked,
                expected_restock_date = EXCLUDED.expected_restock_date
        """, (
            item.get("item_id"),            item.get("product_name"),
            item.get("category"),
            item.get("stock_quantity"),     item.get("reserved_quantity"),
            item.get("available_quantity"), item.get("reorder_level"),
            item.get("reorder_quantity"),   item.get("unit_cost"),
            item.get("unit_price"),         item.get("warehouse_location"),
            item.get("supplier_id"),        item.get("supplier_name"),
            item.get("last_restocked"),     item.get("expected_restock_date"),
            item.get("status"),             item.get("incident_id"),
        ))

    print("  ✓ inventory seeded.")


def seed_shipments(cur, data: dict):
    if not data:
        return
    shipments = data.get("shipments", [])
    if not shipments:
        print("  [SKIP] No shipments array found in logistics.json")
        return
    print(f"  Seeding {len(shipments)} shipments + tracking events...")

    cur.execute("DELETE FROM shipment_events")
    cur.execute("DELETE FROM shipments")

    for s in shipments:
        origin = s.get("origin", {})
        dest   = s.get("destination", {})

        cur.execute("""
            INSERT INTO shipments (
                shipment_id, order_id, carrier, tracking_number, service_level,
                status,
                origin_facility, origin_city, origin_state, origin_zip,
                dest_street, dest_city, dest_state, dest_zip,
                weight_lbs, ship_date, estimated_delivery, actual_delivery, cost
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (shipment_id) DO UPDATE SET
                status            = EXCLUDED.status,
                actual_delivery   = EXCLUDED.actual_delivery
        """, (
            s.get("shipment_id"),   s.get("order_id"),
            s.get("carrier"),       s.get("tracking_number"),
            s.get("service_level"), s.get("status"),
            origin.get("facility"), origin.get("city"),
            origin.get("state"),    origin.get("zip"),
            dest.get("street"),     dest.get("city"),
            dest.get("state"),      dest.get("zip"),
            s.get("weight_lbs"),    s.get("ship_date"),
            s.get("estimated_delivery"), s.get("actual_delivery"),
            s.get("cost"),
        ))

        for event in s.get("events", []):
            cur.execute("""
                INSERT INTO shipment_events (
                    shipment_id, timestamp, location, status, description
                ) VALUES (%s,%s,%s,%s,%s)
            """, (
                s.get("shipment_id"),
                event.get("timestamp"),
                event.get("location"),
                event.get("status"),
                event.get("description"),
            ))

    print("  ✓ shipments + shipment_events seeded.")


def seed_incidents(cur, data: dict):
    if not data:
        return
    incidents = data.get("incidents", [])
    print(f"  Seeding {len(incidents)} incidents...")

    cur.execute("DELETE FROM incident_items")
    cur.execute("DELETE FROM incidents")

    for inc in incidents:
        cur.execute("""
            INSERT INTO incidents (
                incident_id, type, severity, status, title, description,
                created_date, last_updated, resolved_date,
                root_cause, supplier_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (incident_id) DO UPDATE SET
                status       = EXCLUDED.status,
                last_updated = EXCLUDED.last_updated,
                resolved_date = EXCLUDED.resolved_date,
                root_cause   = EXCLUDED.root_cause
        """, (
            inc.get("incident_id"), inc.get("type"),
            inc.get("severity"),    inc.get("status"),
            inc.get("title"),       inc.get("description"),
            inc.get("created_date"), inc.get("last_updated"),
            inc.get("resolved_date"), inc.get("root_cause"),
            inc.get("supplier_id"),
        ))

        for affected in inc.get("affected_items", []):
            cur.execute("""
                INSERT INTO incident_items (
                    incident_id, item_id, product_name, quantity_short
                ) VALUES (%s,%s,%s,%s)
            """, (
                inc.get("incident_id"),
                affected.get("item_id"),
                affected.get("product_name"),
                affected.get("quantity_short"),
            ))

    print("  ✓ incidents + incident_items seeded.")


def create_schema(cur):
    """Drop and recreate all core tables to ensure schema is always up to date."""
    # Drop in child-first order to respect foreign key constraints
    for table in ("incident_items", "shipment_events", "incidents",
                  "shipments", "order_items", "inventory", "orders"):
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    cur.execute("""
        CREATE TABLE orders (
            order_id            TEXT PRIMARY KEY,
            customer_id         TEXT,
            customer_name       TEXT,
            customer_email      TEXT,
            order_date          TEXT,
            status              TEXT,
            priority            TEXT,
            total_amount        FLOAT,
            currency            TEXT,
            shipping_street     TEXT,
            shipping_city       TEXT,
            shipping_state      TEXT,
            shipping_zip        TEXT,
            shipping_country    TEXT,
            shipment_id         TEXT,
            tracking_number     TEXT,
            estimated_delivery  TEXT,
            delivery_date       TEXT,
            cancelled_date      TEXT,
            cancellation_reason TEXT,
            incident_id         TEXT,
            notes               TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE order_items (
            id           SERIAL PRIMARY KEY,
            order_id     TEXT REFERENCES orders(order_id),
            item_id      TEXT,
            product_name TEXT,
            quantity     INTEGER,
            unit_price   FLOAT,
            total_price  FLOAT
        )
    """)
    cur.execute("""
        CREATE TABLE inventory (
            item_id               TEXT PRIMARY KEY,
            product_name          TEXT,
            category              TEXT,
            stock_quantity        INTEGER,
            reserved_quantity     INTEGER,
            available_quantity    INTEGER,
            reorder_level         INTEGER,
            reorder_quantity      INTEGER,
            unit_cost             FLOAT,
            unit_price            FLOAT,
            warehouse_location    TEXT,
            supplier_id           TEXT,
            supplier_name         TEXT,
            last_restocked        TEXT,
            expected_restock_date TEXT,
            status                TEXT,
            incident_id           TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE shipments (
            shipment_id       TEXT PRIMARY KEY,
            order_id          TEXT REFERENCES orders(order_id),
            carrier           TEXT,
            tracking_number   TEXT,
            service_level     TEXT,
            status            TEXT,
            origin_facility   TEXT,
            origin_city       TEXT,
            origin_state      TEXT,
            origin_zip        TEXT,
            dest_street       TEXT,
            dest_city         TEXT,
            dest_state        TEXT,
            dest_zip          TEXT,
            weight_lbs        FLOAT,
            ship_date         TEXT,
            estimated_delivery TEXT,
            actual_delivery   TEXT,
            cost              FLOAT
        )
    """)
    cur.execute("""
        CREATE TABLE incidents (
            incident_id   TEXT PRIMARY KEY,
            type          TEXT,
            severity      TEXT,
            status        TEXT,
            title         TEXT,
            description   TEXT,
            created_date  TEXT,
            last_updated  TEXT,
            resolved_date TEXT,
            root_cause    TEXT,
            supplier_id   TEXT
        )
    """)
    print("  ✓ Core schema verified.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed Acme orders DB from JSON seed files")
    parser.add_argument(
        "--root",
        default=REPO_ROOT,
        help="Path to the repo root (default: %(default)s)"
    )
    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_URL,
        help="PostgreSQL connection URL (default: %(default)s)"
    )
    args = parser.parse_args()

    seed_dir = os.path.join(args.root, SEED_DATA_DIR)

    print(f"\n{'='*55}")
    print(f"  Acme Retail — Orders DB Seed Script (PostgreSQL)")
    print(f"{'='*55}")
    print(f"  Seed data : {seed_dir}")
    print(f"  Database  : {args.db_url}")
    print()

    if not os.path.exists(seed_dir):
        print(f"ERROR: seed-data directory not found at {seed_dir}")
        sys.exit(1)

    try:
        conn = psycopg2.connect(args.db_url)
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database: {e}")
        print("Make sure the Postgres container is running: docker-compose up -d")
        sys.exit(1)

    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Creating / verifying schema...")
        create_schema(cur)
        ensure_extra_tables(cur)

        print("\nLoading JSON files...")
        orders_data    = load_json(os.path.join(seed_dir, "orders.json"))
        inventory_data = load_json(os.path.join(seed_dir, "inventory.json"))
        logistics_data = load_json(os.path.join(seed_dir, "logistics.json"))
        incidents_data = load_json(os.path.join(seed_dir, "incidents.json"))

        print("\nSeeding tables...")
        seed_orders(cur, orders_data)
        seed_inventory(cur, inventory_data)
        seed_shipments(cur, logistics_data)
        seed_incidents(cur, incidents_data)

        conn.commit()

        print("\nRow counts after seeding:")
        tables = [
            "orders", "order_items",
            "inventory",
            "shipments", "shipment_events",
            "incidents", "incident_items",
        ]
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<25} {count:>4} rows")

        print(f"\n✓ Done. Orders database is ready.\n")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR during seeding: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()