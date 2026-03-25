"""
test_order_fulfillment.py — Grading tests for the OrderFulfillmentAgent.

Tests five event-driven scenarios covering the agent's primary responsibilities:
  1. New order with in-stock item     → agent responds with "validated" + order saved to DB
  2. New order with out-of-stock item → agent responds with "blocked" + order saved to DB
  3. Inventory restocked              → blocked order status updated to "validated" in DB
  4. Shipment delayed                 → order estimated_delivery updated in DB 
  5. Order cancelled                  → order status set to "cancelled" in DB

Run directly:
  cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
  python -m tests.test_order_fulfillment
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
from framework.database import assert_order_status, assert_field_equals, row_count, set_inventory_quantity
from framework.seeder import full_reset


# ── Minimal ANSI helper (progress output only) ────────────────────────────────
def _s(text: str, *codes: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{';'.join(codes)}m{text}\033[0m"
    return text

# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------
IN_STOCK_SKU   = "SKU-MOUSE-042"
IN_STOCK_NAME  = "Wireless Mouse Elite"
IN_STOCK_PRICE = 49.99

OOS_SKU        = "SKU-TABLET-055"
OOS_NAME       = "Pro Tablet 12"
OOS_PRICE      = 399.99

BLOCKED_ORDER_ID            = "ORD-2026-004"
DELAYED_SHIPMENT_ID         = "SHIP-2026-0048"
DELAYED_TRACKING_NUMBER     = "1Z999AA10123456791"
DELAYED_ORDER_ID            = "ORD-2026-005"
DELAYED_NEW_DELIVERY        = "2026-03-12T18:00:00Z"
CANCEL_ORDER_ID             = "ORD-2026-003"

TOPIC_ORDER_CREATED     = "acme/orders/created"
TOPIC_INVENTORY_UPDATED = "acme/inventory/updated"
TOPIC_SHIPMENT_DELAYED  = "acme/logistics/shipment-delayed"
TOPIC_ORDER_CANCELLED   = "acme/orders/cancelled"
TOPIC_ORDER_RESULT      = "acme/orders/decision"
TOPIC_INCIDENT_CREATED  = "acme/incidents/created"

AGENT_TIMEOUT_S  = 25
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
def _new_order_payload(order_id, sku, name, price):
    return {
        "order_id": order_id,
        "customer_id": "CUST-TEST-001",
        "customer_name": "Test Student",
        "customer_email": "test@example.com",
        "items": [{"item_id": sku, "product_name": name, "quantity": 1, "unit_price": price}],
        "total_amount": price,
        "priority": "standard",
        "shipping_address": {
            "street": "1 Test Lane", "city": "Toronto",
            "state": "ON", "zip": "M5V 0A1", "country": "Canada",
        },
    }


def _text(msg: dict) -> str:
    """Return the message content as a lowercase string for keyword checks."""
    if not msg:
        return ""
    if "_raw" in msg:
        return msg["_raw"].lower()
    return json.dumps(msg).lower()


def _run_scenario(
    sub_topic,
    pub_topic,
    pub_payload,
    predicate=None,
    timeout_s=AGENT_TIMEOUT_S,
):
    result_q = queue.Queue()
    error_q  = queue.Queue()
    ready    = threading.Event()

    def _subscriber():
        try:
            with BrokerClient() as sub:
                msg = sub.wait_for_message(
                    sub_topic, timeout_s=timeout_s, predicate=predicate,
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
    results = ResultCollector(suite_name="OrderFulfillmentAgent")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Order Fulfillment Agent  —  Grading Suite", "1"))
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

    # ── Test 1 — In-stock order → agent responds with "validated" ─────────────
    print(_s(f"\n  ── Test 1 ─{'─' * (W - 12)}", "2"))
    print(_s("  New order (in stock)  →  agent responds on acme/orders/decision", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDER_CREATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_ORDER_RESULT}", "2"))
    order_id_1 = "ORD-GRADE-VALID-001"
    msg1 = None
    results.section(f"Test 1 — New order for {IN_STOCK_SKU} ({IN_STOCK_NAME}, in stock)")
    try:
        with Spinner("Waiting for agent response"):
            msg1 = _run_scenario(
                sub_topic=TOPIC_ORDER_RESULT,
                pub_topic=TOPIC_ORDER_CREATED,
                pub_payload=_new_order_payload(order_id_1, IN_STOCK_SKU, IN_STOCK_NAME, IN_STOCK_PRICE),
            )
    except Exception as exc:
        results.record("t1_response_received", False, str(exc),
                       label="Listening on acme/orders/decision — message received within 25s")

    with results.test("t1_response_received",
                      label="Listening on acme/orders/decision — message received within 25s"):
        assert msg1 is not None, f"No message on {TOPIC_ORDER_RESULT} within {AGENT_TIMEOUT_S}s"
    with results.test("t1_decision_is_validated",
                      label='Response indicates order is validated (inventory sufficient)'):
        assert msg1 is not None, "No message (prerequisite failed)"
        assert "validated" in _text(msg1) or "valid" in _text(msg1), \
            f"Response does not indicate validation: {_text(msg1)[:200]}"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t1_order_saved_in_db",
                      label=f"Order {order_id_1} saved to database with status 'validated'"):
        try:
            assert_order_status(order_id_1, "validated")
        except Exception as exc:
            assert False, str(exc)

    # ── Test 2 — Out-of-stock order → agent responds with "blocked" ───────────
    print(_s(f"\n  ── Test 2 ─{'─' * (W - 12)}", "2"))
    print(_s("  New order (out of stock)  →  agent responds with blocked decision", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDER_CREATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_ORDER_RESULT}", "2"))
    order_id_2 = "ORD-GRADE-BLOCKED-001"
    msg2 = None
    results.section(f"Test 2 — New order for {OOS_SKU} ({OOS_NAME}, out of stock)")
    try:
        with Spinner("Waiting for agent response"):
            msg2 = _run_scenario(
                sub_topic=TOPIC_ORDER_RESULT,
                pub_topic=TOPIC_ORDER_CREATED,
                pub_payload=_new_order_payload(order_id_2, OOS_SKU, OOS_NAME, OOS_PRICE),
            )
    except Exception as exc:
        results.record("t2_response_received", False, str(exc),
                       label="Listening on acme/orders/decision — message received within 25s")

    with results.test("t2_response_received",
                      label="Listening on acme/orders/decision — message received within 25s"):
        assert msg2 is not None, f"No message on {TOPIC_ORDER_RESULT} within {AGENT_TIMEOUT_S}s"
    with results.test("t2_decision_is_blocked",
                      label='Response indicates order is blocked (insufficient inventory)'):
        assert msg2 is not None, "No message (prerequisite failed)"
        assert ("blocked" in _text(msg2) or "out of stock" in _text(msg2)
                or "insufficient" in _text(msg2) or "cannot" in _text(msg2)), \
            f"Response does not indicate blocked: {_text(msg2)[:200]}"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t2_order_saved_in_db",
                      label=f"Order {order_id_2} saved to database with status 'blocked'"):
        try:
            assert_order_status(order_id_2, "blocked")
        except Exception as exc:
            assert False, str(exc)

    # ── Test 3 — Inventory restock → re-validate blocked order in DB ──────────
    print(_s(f"\n  ── Test 3 ─{'─' * (W - 12)}", "2"))
    print(_s("  Inventory restocked  →  blocked order updated to validated in DB", "1"))
    print(_s(f"  Published to:  {TOPIC_INVENTORY_UPDATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_ORDER_RESULT}", "2"))
    msg3 = None
    results.section(
        f"Test 3 — Inventory restocked for {OOS_SKU} (qty +30) → re-validate {BLOCKED_ORDER_ID}"
    )
    set_inventory_quantity(OOS_SKU, stock_quantity=30, available_quantity=30, status="in_stock")
    try:
        with Spinner("Waiting for agent response"):
            msg3 = _run_scenario(
                sub_topic=TOPIC_ORDER_RESULT,
                pub_topic=TOPIC_INVENTORY_UPDATED,
                pub_payload={
                    "item_id": OOS_SKU,
                    "product_name": OOS_NAME,
                    "quantity_added": 30,
                    "new_stock_quantity": 30,
                    "new_status": "in_stock",
                },
            )
    except Exception as exc:
        results.record("t3_response_received", False, str(exc),
                       label="Listening on acme/orders/decision — message received within 25s")

    with results.test("t3_response_received",
                      label="Listening on acme/orders/decision — message received within 25s"):
        assert msg3 is not None, f"No message on {TOPIC_ORDER_RESULT} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t3_blocked_order_validated_in_db",
                      label=f"Order {BLOCKED_ORDER_ID} status updated to 'validated' in database"):
        try:
            assert_order_status(BLOCKED_ORDER_ID, "validated")
        except Exception as exc:
            assert False, str(exc)

    # ── Test 4 — Shipment delay → order delivery updated (incident creation is IncidentResponseAgent's job) ────
    print(_s(f"\n  ── Test 4 ─{'─' * (W - 12)}", "2"))
    print(_s("  Shipment delayed (+30h)  →  order delivery updated in database", "1"))
    print(_s(f"  Published to:  {TOPIC_SHIPMENT_DELAYED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_ORDER_RESULT}", "2"))
    msg4 = None
    results.section(
        f"Test 4 — Shipment {DELAYED_SHIPMENT_ID} delayed +30h → order estimated_delivery updated"
    )
    try:
        with Spinner("Waiting for agent response"):
            msg4 = _run_scenario(
                sub_topic=TOPIC_ORDER_RESULT,
                pub_topic=TOPIC_SHIPMENT_DELAYED,
                pub_payload={
                    "shipment_id": DELAYED_SHIPMENT_ID,
                    "tracking_number": DELAYED_TRACKING_NUMBER,
                    "order_id": DELAYED_ORDER_ID,
                    "carrier": "ExpressAir Priority",
                    "reason": "Severe weather — Chicago O'Hare hub",
                    "original_estimated_delivery": "2026-03-11T12:00:00Z",
                    "new_estimated_delivery": DELAYED_NEW_DELIVERY,
                    "delay_hours": 30,
                },
            )
    except Exception as exc:
        results.record("t4_response_received", False, str(exc),
                       label="Listening on acme/orders/decision — message received within 25s")

    with results.test("t4_response_received",
                      label="Listening on acme/orders/decision — message received within 25s"):
        assert msg4 is not None, f"No message on {TOPIC_ORDER_RESULT} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t4_order_delivery_updated",
                      label=f"Order {DELAYED_ORDER_ID} estimated_delivery updated to {DELAYED_NEW_DELIVERY}"):
        try:
            assert_field_equals(
                "orders", "order_id", DELAYED_ORDER_ID,
                "estimated_delivery", DELAYED_NEW_DELIVERY,
            )
        except Exception as exc:
            assert False, str(exc)

    # ── Test 5 — Order cancelled → order status set to 'cancelled' in DB ──────
    print(_s(f"\n  ── Test 5 ─{'─' * (W - 12)}", "2"))
    print(_s("  Order cancelled  →  order status set to cancelled in DB", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDER_CANCELLED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_ORDER_RESULT}", "2"))
    msg5 = None
    results.section(f"Test 5 — Order {CANCEL_ORDER_ID} cancelled → status 'cancelled' in DB")
    try:
        with Spinner("Waiting for agent response"):
            msg5 = _run_scenario(
                sub_topic=TOPIC_ORDER_RESULT,
                pub_topic=TOPIC_ORDER_CANCELLED,
                pub_payload={
                    "order_id": CANCEL_ORDER_ID,
                    "reason": "Customer requested cancellation",
                    "cancelled_by": "customer",
                },
            )
    except Exception as exc:
        results.record("t5_response_received", False, str(exc),
                       label="Listening on acme/orders/decision — message received within 25s")

    with results.test("t5_response_received",
                      label="Listening on acme/orders/decision — message received within 25s"):
        assert msg5 is not None, f"No message on {TOPIC_ORDER_RESULT} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t5_order_cancelled_in_db",
                      label=f"Order {CANCEL_ORDER_ID} status set to 'cancelled' in database"):
        try:
            assert_order_status(CANCEL_ORDER_ID, "cancelled")
        except Exception as exc:
            assert False, str(exc)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + results.summary())
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)
