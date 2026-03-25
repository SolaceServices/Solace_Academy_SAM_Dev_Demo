"""
test_inventory_management.py — Grading tests for the InventoryManagementAgent.

Tests three independent event-driven scenarios covering the agent's stock adjustment responsibilities:
  1. Supplier restock received  → out-of-stock item (SKU-TABLET-055) updated to in_stock in DB
  2. Write-off adjustment       → low-stock item (SKU-LAPTOP-002) reduced to out_of_stock in DB
  3. Restock after write-off    → out-of-stock item (SKU-DOCKSTATION-007) updated to in_stock in DB

All tests run sequentially after a single full_reset() and use independent SKUs. Each test
validates a distinct inventory operation with separate seed data, ensuring reliable results
regardless of execution order.

Run directly:
  cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
  python -m tests.test_inventory_management
"""

import sys
import os
import json
import time
import threading
import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.database import assert_inventory_status, assert_field_equals
from framework.seeder import full_reset


# ── Minimal ANSI helper (progress output only) ────────────────────────────────
def _s(text: str, *codes: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{';'.join(codes)}m{text}\033[0m"
    return text


# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------
OOS_SKU         = "SKU-TABLET-055"   # seed: available=0, out_of_stock
OOS_NAME        = "Pro Tablet 12"
OOS_SUPPLIER_ID = "SUP-001"
OOS_SUPPLIER    = "TechSupply Global"

OOS_SKU_2       = "SKU-DOCKSTATION-007"  # seed: available=0, out_of_stock (for Test 3)
OOS_NAME_2      = "USB-C Docking Station Pro"

LOW_SKU         = "SKU-LAPTOP-002"   # seed: available=3, reorder_level=10, low_stock
LOW_NAME        = "Gaming Laptop Xtreme"

RESTOCK_QTY_1   = 50   # Test 1: restock OOS_SKU by this amount (0 → 50, in_stock)
WRITE_OFF_DELTA = -3   # Test 2: write off all available from LOW_SKU (3 → 0, out_of_stock)
RESTOCK_QTY_2   = 20   # Test 3: restock LOW_SKU above reorder_level=10 (0 → 20, in_stock)

TOPIC_RESTOCK_RECEIVED     = "acme/suppliers/restock-received"
TOPIC_INVENTORY_ADJUSTMENT = "acme/inventory/adjustment"
TOPIC_INVENTORY_UPDATED    = "acme/inventory/updated"

AGENT_TIMEOUT_S  = 30
POST_MSG_SLEEP_S = 2   # let agent finish DB write before asserting


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------
class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str):
        self.label = label
        self._stop = threading.Event()
        self._thread = None

    def _spin(self):
        start = time.monotonic()
        i = 0
        while not self._stop.is_set():
            elapsed = time.monotonic() - start
            frame = self.FRAMES[i % len(self.FRAMES)]
            print(f"\r  {frame}  {self.label}  ({elapsed:.1f}s)", end="", flush=True)
            i += 1
            time.sleep(0.1)

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        print("\r" + " " * 60 + "\r", end="", flush=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _text(msg: dict) -> str:
    """Return message content as a lowercase string for keyword checks."""
    if not msg:
        return ""
    if "_raw" in msg:
        return msg["_raw"].lower()
    return json.dumps(msg).lower()


def _run_scenario(sub_topic, pub_topic, pub_payload, timeout_s=AGENT_TIMEOUT_S):
    result_q = queue.Queue()
    error_q  = queue.Queue()
    ready    = threading.Event()

    def _subscriber():
        try:
            with BrokerClient() as sub:
                msg = sub.wait_for_message(
                    sub_topic, timeout_s=timeout_s,
                    on_ready=ready.set,
                )
                result_q.put(msg)
        except Exception as exc:
            error_q.put(exc)
            ready.set()

    t = threading.Thread(target=_subscriber, daemon=True)
    t.start()

    ready.wait(timeout=10)
    if not error_q.empty():
        raise error_q.get()

    with BrokerClient() as pub:
        pub.publish(pub_topic, pub_payload)

    t.join(timeout=timeout_s + 5)

    if not error_q.empty():
        raise error_q.get()

    return result_q.get() if not result_q.empty() else None


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------
def run_tests(student_email="student@example.com"):
    results = ResultCollector(suite_name="InventoryManagementAgent")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Inventory Management Agent  —  Grading Suite", "1"))
    print(_s("  Publishes events to the broker and checks agent responses.", "2"))
    print(_s("═" * W, "1", "36"))

    print(f"\n  🔄  Resetting database to seed state...")
    try:
        full_reset()
        print(f"  ✅  Database reset complete.")
    except Exception as exc:
        print(f"  ❌  Database reset failed: {exc}")
        results.record("db_reset", passed=False, message=str(exc))
        return results

    # ── Test 1 — Restock out-of-stock item → in_stock ─────────────────────────
    print(_s(f"\n  ── Test 1 ─{'─' * (W - 12)}", "2"))
    print(_s("  Supplier restock received  →  out_of_stock item updated to in_stock", "1"))
    print(_s(f"  Published to:  {TOPIC_RESTOCK_RECEIVED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INVENTORY_UPDATED}", "2"))
    msg1 = None
    results.section(
        f"Test 1 — Restock {OOS_SKU} ({OOS_NAME}) +{RESTOCK_QTY_1} units (out_of_stock → in_stock)"
    )
    try:
        with Spinner("Waiting for agent response"):
            msg1 = _run_scenario(
                sub_topic=TOPIC_INVENTORY_UPDATED,
                pub_topic=TOPIC_RESTOCK_RECEIVED,
                pub_payload={
                    "item_id": OOS_SKU,
                    "quantity_received": RESTOCK_QTY_1,
                    "supplier_id": OOS_SUPPLIER_ID,
                    "supplier_name": OOS_SUPPLIER,
                },
            )
    except Exception as exc:
        results.record("t1_response_received", False, str(exc),
                       label="Listening on acme/inventory/updated — message received within 30s")

    with results.test("t1_response_received",
                      label="Listening on acme/inventory/updated — message received within 30s"):
        assert msg1 is not None, f"No message on {TOPIC_INVENTORY_UPDATED} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t1_available_qty_updated",
                      label=f"{OOS_SKU} available_quantity updated to {RESTOCK_QTY_1} in database"):
        try:
            assert_field_equals("inventory", "item_id", OOS_SKU, "available_quantity", RESTOCK_QTY_1)
        except Exception as exc:
            assert False, str(exc)
    with results.test("t1_status_in_stock",
                      label=f"{OOS_SKU} status updated to 'in_stock' in database"):
        try:
            assert_inventory_status(OOS_SKU, "in_stock")
        except Exception as exc:
            assert False, str(exc)

    # ── Test 2 — Write-off reduces low-stock item to out-of-stock ─────────────
    print(_s(f"\n  ── Test 2 ─{'─' * (W - 12)}", "2"))
    print(_s("  Write-off adjustment received  →  low_stock item reduced to out_of_stock", "1"))
    print(_s(f"  Published to:  {TOPIC_INVENTORY_ADJUSTMENT}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INVENTORY_UPDATED}", "2"))
    msg2 = None
    results.section(
        f"Test 2 — Write-off {LOW_SKU} ({LOW_NAME}) {WRITE_OFF_DELTA} units (low_stock → out_of_stock)"
    )
    try:
        with Spinner("Waiting for agent response"):
            msg2 = _run_scenario(
                sub_topic=TOPIC_INVENTORY_UPDATED,
                pub_topic=TOPIC_INVENTORY_ADJUSTMENT,
                pub_payload={
                    "item_id": LOW_SKU,
                    "adjustment_type": "write_off",
                    "quantity_delta": WRITE_OFF_DELTA,
                    "reason": "Damaged during warehouse inspection",
                },
            )
    except Exception as exc:
        results.record("t2_response_received", False, str(exc),
                       label="Listening on acme/inventory/updated — message received within 30s")

    with results.test("t2_response_received",
                      label="Listening on acme/inventory/updated — message received within 30s"):
        assert msg2 is not None, f"No message on {TOPIC_INVENTORY_UPDATED} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t2_available_qty_zeroed",
                      label=f"{LOW_SKU} available_quantity reduced to 0 in database"):
        try:
            assert_field_equals("inventory", "item_id", LOW_SKU, "available_quantity", 0)
        except Exception as exc:
            assert False, str(exc)
    with results.test("t2_status_out_of_stock",
                      label=f"{LOW_SKU} status updated to 'out_of_stock' in database"):
        try:
            assert_inventory_status(LOW_SKU, "out_of_stock")
        except Exception as exc:
            assert False, str(exc)

    # ── Test 3 — Restock out-of-stock item → in_stock ────────────────────────
    print(_s(f"\n  ── Test 3 ─{'─' * (W - 12)}", "2"))
    print(_s("  Restock after write-off  →  item status restored to in_stock", "1"))
    print(_s(f"  Published to:  {TOPIC_RESTOCK_RECEIVED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INVENTORY_UPDATED}", "2"))
    msg3 = None
    results.section(
        f"Test 3 — Restock {OOS_SKU_2} ({OOS_NAME_2}) +{RESTOCK_QTY_2} units (out_of_stock → in_stock)"
    )
    try:
        with Spinner("Waiting for agent response"):
            msg3 = _run_scenario(
                sub_topic=TOPIC_INVENTORY_UPDATED,
                pub_topic=TOPIC_RESTOCK_RECEIVED,
                pub_payload={
                    "item_id": OOS_SKU_2,
                    "quantity_received": RESTOCK_QTY_2,
                    "supplier_id": "SUP-007",
                    "supplier_name": "Cable Connections Inc",
                },
            )
    except Exception as exc:
        results.record("t3_response_received", False, str(exc),
                       label="Listening on acme/inventory/updated — message received within 30s")

    with results.test("t3_response_received",
                      label="Listening on acme/inventory/updated — message received within 30s"):
        assert msg3 is not None, f"No message on {TOPIC_INVENTORY_UPDATED} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t3_status_in_stock",
                      label=f"{OOS_SKU_2} status restored to 'in_stock' after restock (qty {RESTOCK_QTY_2} > reorder_level 8)"):
        try:
            assert_inventory_status(OOS_SKU_2, "in_stock")
        except Exception as exc:
            assert False, str(exc)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + results.summary())
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)
