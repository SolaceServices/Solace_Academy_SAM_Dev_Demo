"""
smoke_test.py — Verify broker and database connectivity before running tests.

Run this first to confirm the environment is ready:
  python smoke_test.py

Expected output on a healthy setup:
  ✅  Broker: connected to tcp://localhost:55555 (VPN: default)
  ✅  Broker: publish/subscribe round-trip OK  (topic: acme/grading/smoke-test)
  ✅  Database: connected to postgresql://acme:acme@localhost:5432/orders
  ✅  Database: orders table has 10 rows
  ✅  Database: inventory table has 12 rows
  All systems ready. Safe to run tests.
"""

import json
import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from framework.broker import BrokerClient
from framework.database import db_cursor, row_count

SMOKE_TOPIC = "acme/grading/smoke-test"
BROKER_URL = os.environ.get("SOLACE_BROKER_URL", "ws://localhost:8008")
BROKER_VPN = os.environ.get("SOLACE_BROKER_VPN", "default")


def check_broker():
    print(f"\n🔌  Checking broker connectivity ({BROKER_URL}, VPN: {BROKER_VPN})...")

    # Connection check
    try:
        with BrokerClient() as broker:
            print(f"  ✅  Broker: connected")

            # Round-trip publish/subscribe
            received = {}

            def _listen():
                with BrokerClient() as sub:
                    msg = sub.wait_for_message(SMOKE_TOPIC, timeout_s=5)
                    received["msg"] = msg

            t = threading.Thread(target=_listen, daemon=True)
            t.start()
            time.sleep(0.3)
            broker.publish(SMOKE_TOPIC, {"ping": "smoke-test"})
            t.join(timeout=7)

            if received.get("msg"):
                print(f"  ✅  Broker: publish/subscribe round-trip OK")
            else:
                print(f"  ❌  Broker: round-trip FAILED — no message received on {SMOKE_TOPIC}")
                return False

    except Exception as exc:
        print(f"  ❌  Broker: {exc}")
        return False

    return True


def check_database():
    dsn = os.environ.get(
        "ORDERS_DB_CONNECTION_STRING",
        "postgresql://acme:acme@localhost:5432/orders",
    )
    print(f"\n🗄   Checking database connectivity ({dsn})...")

    try:
        with db_cursor() as cur:
            cur.execute("SELECT 1")
        print(f"  ✅  Database: connected")
    except Exception as exc:
        print(f"  ❌  Database: {exc}")
        return False

    try:
        orders = row_count("orders")
        print(f"  ✅  Database: orders table has {orders} rows")

        inventory = row_count("inventory")
        print(f"  ✅  Database: inventory table has {inventory} rows")

        shipments = row_count("shipments")
        print(f"  ✅  Database: shipments table has {shipments} rows")

        incidents = row_count("incidents")
        print(f"  ✅  Database: incidents table has {incidents} rows")

    except Exception as exc:
        print(f"  ❌  Database table check failed: {exc}")
        return False

    return True


if __name__ == "__main__":
    broker_ok = check_broker()
    db_ok = check_database()

    print()
    if broker_ok and db_ok:
        print("🟢  All systems ready. Safe to run tests.\n")
        sys.exit(0)
    else:
        print("🔴  One or more checks failed. Fix issues above before running tests.\n")
        sys.exit(1)