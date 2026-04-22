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

# SAM working directory — where agent session .db files are created.
# REQUIRED: export SAM_DIR before running tests from modules 400 or 500.
# run-scenario.sh exports SAM_DIR per module. If running tests manually,
# set: export SAM_DIR=/workspaces/Solace_Academy_SAM_Dev_Demo/<module>/sam
_DEFAULT_SAM_DIR = os.environ.get(
    "SAM_DIR",
    "/workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam",
)

# Agent session SQLite files to delete on reset (both possible names)
_AGENT_SESSION_DBS = ["acme_knowledge.db", "order_fulfillment_agent.db", "inventory_management_agent.db", "incident_response_agent.db", "logistics_agent.db"]

# Pipeline output topics that may carry stale in-flight messages between test suites.
# A previous suite's async LLM pipeline can publish here after its own tests have
# completed, then race with the next suite's subscriber.
_PIPELINE_RESPONSE_TOPICS = [
    "acme/incidents/response",
    "acme/incidents/created",
    "acme/orders/decision",
    "acme/inventory/updated",
    "acme/logistics/updated",
]

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
    Re-run seed_orders_db.py with --data-only to restore seed values without
    dropping/recreating tables.  Safe to call while SAM agents are running.

    Raises RuntimeError if the seeder exits with a non-zero return code.
    """
    result = subprocess.run(
        [sys.executable, seeder_path, "--data-only"],
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


def _drain_broker_topics(topics=None, idle_s: float = 12.0, max_wait_s: float = 60.0):
    """
    Subscribe to pipeline response/output topics and discard any messages that
    arrive, consuming stale in-flight messages left over from a previous test
    suite's async pipeline.

    Subscribes to all topics simultaneously via one receiver; stops after
    idle_s seconds of silence across all topics, or max_wait_s total.
    Non-fatal if the broker is unreachable.

    Must be called BEFORE reset_to_seed() so it runs concurrently with the
    still-in-flight LLM pipeline from the previous suite.
    """
    import time as _time
    from framework.broker import BrokerClient
    try:
        with BrokerClient() as client:
            client.drain_messages(
                topics or _PIPELINE_RESPONSE_TOPICS,
                idle_s=idle_s,
                max_wait_s=max_wait_s,
            )
    except Exception:
        pass  # non-fatal — drain is best-effort


def _clear_agent_session_dbs(sam_dir: str = None):
    """
    Clear session history tables in the agent SQLite session DBs so the next
    task starts with a clean context.

    Only deletes from session/event data tables. Skips alembic_version and
    any table not in the known session-data set — preserving migration state
    so SAM's Alembic upgrade check succeeds on the next task.

    Uses a 10-second busy timeout so the operation waits briefly if SAM holds
    a write lock, instead of failing immediately. Failures are non-fatal —
    logged as a warning and the reset continues.
    """
    import sqlite3

    # Only wipe session/history data — never touch alembic_version or other
    # schema-management tables that SAM needs intact.
    SESSION_DATA_TABLES = {"sessions", "app_states", "user_states", "events"}

    base = sam_dir or _DEFAULT_SAM_DIR
    for name in _AGENT_SESSION_DBS:
        path = os.path.join(base, name)
        if not os.path.exists(path):
            continue
        try:
            conn = sqlite3.connect(path, timeout=10)
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                for table in tables:
                    if table in SESSION_DATA_TABLES:
                        cur.execute(f"DELETE FROM {table}")
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            # Non-fatal: if the DB is locked or unavailable, log and move on.
            # The PostgreSQL data reset is what matters for test correctness.
            print(f"  ⚠️  Warning: could not clear {name}: {exc}")


def _clear_email_inbox(url: str = "http://localhost:3000/clear"):
    """
    Clear all emails from the mock email service inbox.
    Non-fatal if the service is not running (email tool may not be in use).
    """
    try:
        import urllib.request
        req = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception:
        pass  # non-fatal — email service may not be running for this module


def full_reset(
    seeder_path: str = _DEFAULT_SEEDER_PATH,
    dsn: str = None,
    timeout_s: int = 30,
    sam_dir: str = None,
):
    """
    Truncate all tables, re-seed from JSON files, and delete the agent's
    SQLite session DB so the next SAM restart starts clean.

    This is the function most tests should call at the top of each test.
    full_reset()  →  clean, deterministic seed state every time.

    Process:
    1. Drain stale messages and reset database concurrently
       (drain discards in-flight pipeline messages while the DB resets)
    2. Short drain to catch any messages that arrived during the reset
    3. Clear agent session DBs
    """
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=2) as pool:
        drain_future = pool.submit(_drain_broker_topics)
        reset_future = pool.submit(
            reset_to_seed,
            seeder_path=seeder_path,
            dsn=dsn,
            timeout_s=timeout_s,
        )
        drain_future.result()
        reset_future.result()
    _drain_broker_topics(idle_s=2.0, max_wait_s=10.0)
    _clear_agent_session_dbs(sam_dir)
    _clear_email_inbox()