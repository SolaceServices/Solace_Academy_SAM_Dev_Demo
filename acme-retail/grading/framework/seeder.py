"""
seeder.py — Reset the Acme orders database to the JSON seed state.

Calls seed_orders_db.py (which uses upsert, so it is safe to re-run at any
point) to restore all tables to the values in the seed JSON files.

This is called at the start of every test that mutates database state, so
each test starts from a clean, known baseline.
"""

import os
import subprocess
import sys

# Path to the seeder script — adjust if your repo root differs
_DEFAULT_SEEDER_PATH = os.environ.get(
    "ACME_SEEDER_PATH",
    "/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts/seed_orders_db.py",
)

# SAM working directory — where agent session .db files are created
_DEFAULT_SAM_DIR = os.environ.get(
    "SAM_DIR",
    "/workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam",
)

# Agent session SQLite files to delete on reset (both possible names)
_AGENT_SESSION_DBS = ["order_fulfillment_agent.db"]

_DEFAULT_DSN = os.environ.get(
    "ORDERS_DB_CONNECTION_STRING",
    "postgresql://acme:acme@localhost:5432/orders",
)

# Tables in safe deletion order (children before parents)
_TRUNCATE_ORDER = [
    "incident_items",
    "incidents",
    "shipment_events",
    "shipments",
    "order_items",
    "orders",
    "inventory",
]


def _truncate_all(dsn: str = None):
    """
    Truncate all seed tables in FK-safe order so the seeder script can
    re-insert cleanly without hitting foreign key violations.
    """
    import psycopg2
    conn = psycopg2.connect(dsn or _DEFAULT_DSN)
    try:
        with conn:
            with conn.cursor() as cur:
                for table in _TRUNCATE_ORDER:
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE")
    finally:
        conn.close()


def reset_to_seed(seeder_path: str = _DEFAULT_SEEDER_PATH, timeout_s: int = 30, dsn: str = None):
    """
    Truncate all tables then re-run seed_orders_db.py to restore seed values.

    Raises RuntimeError if the seeder exits with a non-zero return code.
    """
    _truncate_all(dsn=dsn)

    result = subprocess.run(
        [sys.executable, seeder_path],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"seed_orders_db.py failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


def reset_extra_rows(dsn: str = None):
    """
    Remove rows from agent-writable tables that are NOT part of the seed data.

    Tables cleaned:
      - incidents: keep only INC-2026-010, 012, 015, 018, 020
      - incident_items: cascades from incidents (FK)
    """
    import psycopg2
    conn = psycopg2.connect(dsn or _DEFAULT_DSN)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM incidents
                    WHERE incident_id NOT IN (
                        'INC-2026-010',
                        'INC-2026-012',
                        'INC-2026-015',
                        'INC-2026-018',
                        'INC-2026-020'
                    )
                    """
                )
    finally:
        conn.close()


def _clear_agent_session_dbs(sam_dir: str = None):
    """
    Truncate all tables in the OrderFulfillmentAgent's SQLite session DB,
    resetting it to the same empty state it was in when first created.

    Keeps the file and schema intact so the running SAM process is not
    disrupted — only the session history is wiped.
    """
    import sqlite3
    base = sam_dir or _DEFAULT_SAM_DIR
    for name in _AGENT_SESSION_DBS:
        path = os.path.join(base, name)
        if not os.path.exists(path):
            continue
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for (table,) in cur.fetchall():
                cur.execute(f"DELETE FROM {table}")
            conn.commit()
        finally:
            conn.close()


def full_reset(
    seeder_path: str = _DEFAULT_SEEDER_PATH,
    dsn: str = None,
    timeout_s: int = 30,
):
    """
    Truncate all tables, re-seed from JSON files, and delete the agent's
    SQLite session DB so the next SAM restart starts clean.

    This is the function most tests should call at the top of each test.
    full_reset()  →  clean, deterministic seed state every time.
    """
    reset_to_seed(seeder_path=seeder_path, dsn=dsn, timeout_s=timeout_s)
    _clear_agent_session_dbs()