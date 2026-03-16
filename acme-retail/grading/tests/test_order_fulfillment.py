"""
test_order_fulfillment.py — Grading tests for the OrderFulfillmentAgent.

Tests four event-driven scenarios:
  1. New order with in-stock item     → fulfillment-result/validated
  2. New order with out-of-stock item → fulfillment-result/blocked
  3. Inventory restocked              → blocked order becomes validated
  4. Shipment delayed                 → incident published on broker

Run directly:
  cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
  python -m tests.test_order_fulfillment
"""

import sys
import os
import time
import threading
import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.database import assert_order_status, assert_incident_exists, assert_field_equals
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

BLOCKED_ORDER_ID        = "ORD-2026-004"
DELAYED_SHIPMENT_ID     = "SHIP-2026-0048"
DELAYED_TRACKING_NUMBER = "1Z999AA10123456791"
DELAYED_ORDER_ID        = "ORD-2026-005"

TOPIC_ORDER_CREATED     = "acme/orders/created"
TOPIC_INVENTORY_UPDATED = "acme/inventory/updated"
TOPIC_SHIPMENT_DELAYED  = "acme/logistics/shipment-delayed"
TOPIC_RESULT_WILDCARD   = "acme/orders/fulfillment-result/>"
TOPIC_INCIDENT_CREATED  = "acme/incidents/created"

AGENT_TIMEOUT_S = 25
SUB_WARMUP_S    = 0.3   # seconds after subscribe before publishing (localhost sub propagates fast)


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------
class Spinner:
    """
    Prints a rotating spinner + elapsed time on a single line while waiting.

    Usage:
        with Spinner("  ⏳ Waiting for agent"):
            msg = _run_scenario(...)
    """
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
        print("\r" + " " * 60 + "\r", end="", flush=True)  # clear the spinner line


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


def _run_scenario(
    sub_topic,
    pub_topic,
    pub_payload,
    predicate=None,
    timeout_s=AGENT_TIMEOUT_S,
    warmup_s=SUB_WARMUP_S,
):
    """
    1. Start a subscriber thread (signals ready via threading.Event once connected)
    2. Sleep warmup_s (0.3s) to let the subscription propagate to the broker
    3. Publish the event on a separate short-lived connection
    4. Wait for the subscriber to receive a matching message
    5. Return the message dict, or None on timeout
    Any exception in the subscriber is re-raised in the caller.
    """
    result_q = queue.Queue()
    error_q  = queue.Queue()
    ready    = threading.Event()

    def _subscriber():
        try:
            with BrokerClient() as sub:
                ready.set()
                msg = sub.wait_for_message(sub_topic, timeout_s=timeout_s, predicate=predicate)
                result_q.put(msg)
        except Exception as exc:
            error_q.put(exc)
            ready.set()

    t = threading.Thread(target=_subscriber, daemon=True)
    t.start()

    ready.wait(timeout=10)
    if not error_q.empty():
        raise error_q.get()

    time.sleep(warmup_s)  # let subscription propagate before publishing

    with BrokerClient() as pub:
        pub.publish(pub_topic, pub_payload)

    t.join(timeout=timeout_s + warmup_s + 5)

    if not error_q.empty():
        raise error_q.get()

    return result_q.get() if not result_q.empty() else None


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------
def run_tests(student_email="student@example.com"):
    results = ResultCollector(suite_name="OrderFulfillmentAgent")

    # ── Banner ────────────────────────────────────────────────────────────────
    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Order Fulfillment Agent  —  Grading Suite", "1"))
    print(_s("  Publishes events to the broker and checks agent responses.", "2"))
    print(_s("═" * W, "1", "36"))

    # ── DB reset ──────────────────────────────────────────────────────────────
    print(f"\n  🔄  Resetting database to seed state...")
    try:
        full_reset()
        print(f"  ✅  Database reset complete.")
    except Exception as exc:
        print(f"  ❌  Database reset failed: {exc}")
        results.record("db_reset", passed=False, message=str(exc))
        return results

    # ── Test 1 — In-stock order → validated ───────────────────────────────────
    print(_s(f"\n  ── Test 1 ─{'─' * (W - 12)}", "2"))
    print(_s("  New order (in stock)  →  fulfillment-result/validated", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDER_CREATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_RESULT_WILDCARD}", "2"))
    order_id_1 = "ORD-GRADE-VALID-001"
    msg1 = None
    results.section(f"Test 1 — New order for {IN_STOCK_SKU} ({IN_STOCK_NAME}, in stock)")
    try:
        with Spinner("Waiting for agent response"):
            msg1 = _run_scenario(
                sub_topic=TOPIC_RESULT_WILDCARD,
                pub_topic=TOPIC_ORDER_CREATED,
                pub_payload=_new_order_payload(order_id_1, IN_STOCK_SKU, IN_STOCK_NAME, IN_STOCK_PRICE),
                predicate=lambda m: m.get("order_id") == order_id_1,
            )
    except Exception as exc:
        results.record("t1_validated_message_received", False, str(exc),
                       label="Response received on fulfillment-result/> within 25s")

    with results.test("t1_validated_message_received",
                      label="Response received on fulfillment-result/> within 25s"):
        assert msg1 is not None, f"No message on {TOPIC_RESULT_WILDCARD} within {AGENT_TIMEOUT_S}s"
    with results.test("t1_decision_is_validated",
                      label='Response JSON contains decision = "validated"'):
        assert msg1 is not None, "No message (prerequisite failed)"
        assert msg1.get("decision") == "validated", f"Got decision={msg1.get('decision')!r}"
    with results.test("t1_order_id_echoed",
                      label=f"Response JSON echoes order_id = {order_id_1!r}"):
        assert msg1 is not None, "No message (prerequisite failed)"
        assert msg1.get("order_id") == order_id_1, f"Got order_id={msg1.get('order_id')!r}"
    with results.test("t1_topic_is_validated",
                      label="Response published to topic ending in /validated"):
        assert msg1 is not None, "No message (prerequisite failed)"
        assert msg1.get("_topic", "").endswith("/validated"), f"Got topic={msg1.get('_topic')!r}"

    # ── Test 2 — Out-of-stock order → blocked ─────────────────────────────────
    print(_s(f"\n  ── Test 2 ─{'─' * (W - 12)}", "2"))
    print(_s("  New order (out of stock)  →  fulfillment-result/blocked", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDER_CREATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_RESULT_WILDCARD}", "2"))
    order_id_2 = "ORD-GRADE-BLOCKED-001"
    msg2 = None
    results.section(f"Test 2 — New order for {OOS_SKU} ({OOS_NAME}, out of stock)")
    try:
        with Spinner("Waiting for agent response"):
            msg2 = _run_scenario(
                sub_topic=TOPIC_RESULT_WILDCARD,
                pub_topic=TOPIC_ORDER_CREATED,
                pub_payload=_new_order_payload(order_id_2, OOS_SKU, OOS_NAME, OOS_PRICE),
                predicate=lambda m: m.get("order_id") == order_id_2,
            )
    except Exception as exc:
        results.record("t2_blocked_message_received", False, str(exc),
                       label="Response received on fulfillment-result/> within 25s")

    with results.test("t2_blocked_message_received",
                      label="Response received on fulfillment-result/> within 25s"):
        assert msg2 is not None, f"No message on {TOPIC_RESULT_WILDCARD} within {AGENT_TIMEOUT_S}s"
    with results.test("t2_decision_is_blocked",
                      label='Response JSON contains decision = "blocked"'):
        assert msg2 is not None, "No message (prerequisite failed)"
        assert msg2.get("decision") == "blocked", f"Got decision={msg2.get('decision')!r}"
    with results.test("t2_topic_is_blocked",
                      label="Response published to topic ending in /blocked"):
        assert msg2 is not None, "No message (prerequisite failed)"
        assert msg2.get("_topic", "").endswith("/blocked"), f"Got topic={msg2.get('_topic')!r}"

    # ── Test 3 — Inventory restock → re-validate blocked order ────────────────
    print(_s(f"\n  ── Test 3 ─{'─' * (W - 12)}", "2"))
    print(_s("  Inventory restocked  →  blocked order re-validated", "1"))
    print(_s(f"  Published to:  {TOPIC_INVENTORY_UPDATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_RESULT_WILDCARD}", "2"))
    msg3 = None
    results.section(
        f"Test 3 — Inventory restocked for {OOS_SKU} (qty +30) → re-validate blocked order {BLOCKED_ORDER_ID}"
    )
    try:
        with Spinner("Waiting for agent response"):
            msg3 = _run_scenario(
                sub_topic=TOPIC_RESULT_WILDCARD,
                pub_topic=TOPIC_INVENTORY_UPDATED,
                pub_payload={
                    "item_id": OOS_SKU,
                    "product_name": OOS_NAME,
                    "quantity_added": 30,
                    "new_stock_quantity": 30,
                    "new_status": "in_stock",
                },
                predicate=lambda m: m.get("order_id") == BLOCKED_ORDER_ID,
            )
    except Exception as exc:
        results.record("t3_restock_triggers_revalidation", False, str(exc),
                       label=f"Re-validation response for {BLOCKED_ORDER_ID} received within 25s")

    with results.test("t3_restock_triggers_revalidation",
                      label=f"Re-validation response for {BLOCKED_ORDER_ID} received within 25s"):
        assert msg3 is not None, f"No fulfillment-result for {BLOCKED_ORDER_ID} within {AGENT_TIMEOUT_S}s"
    with results.test("t3_blocked_order_now_validated",
                      label='Response JSON contains decision = "validated"'):
        assert msg3 is not None, "No message (prerequisite failed)"
        assert msg3.get("decision") == "validated", f"Got decision={msg3.get('decision')!r}"

    # ── Test 4 — Shipment delay → incident published ───────────────────────────
    print(_s(f"\n  ── Test 4 ─{'─' * (W - 12)}", "2"))
    print(_s("  Shipment delayed (+30h)  →  incident created", "1"))
    print(_s(f"  Published to:  {TOPIC_SHIPMENT_DELAYED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INCIDENT_CREATED}", "2"))
    msg4 = None
    results.section(
        f"Test 4 — Shipment {DELAYED_SHIPMENT_ID} delayed +30h → incident on acme/incidents/created"
    )
    try:
        with Spinner("Waiting for agent response"):
            msg4 = _run_scenario(
                sub_topic=TOPIC_INCIDENT_CREATED,
                pub_topic=TOPIC_SHIPMENT_DELAYED,
                pub_payload={
                    "shipment_id": DELAYED_SHIPMENT_ID,
                    "tracking_number": DELAYED_TRACKING_NUMBER,
                    "order_id": DELAYED_ORDER_ID,
                    "carrier": "ExpressAir Priority",
                    "reason": "Severe weather — Chicago O'Hare hub",
                    "original_estimated_delivery": "2026-03-11T12:00:00Z",
                    "new_estimated_delivery": "2026-03-12T18:00:00Z",
                    "delay_hours": 30,
                },
                predicate=lambda m: (
                    m.get("tracking_number") == DELAYED_TRACKING_NUMBER
                    or m.get("shipment_id") == DELAYED_SHIPMENT_ID
                ),
            )
    except Exception as exc:
        results.record("t4_incident_message_published", False, str(exc),
                       label="Incident message received on acme/incidents/created within 25s")

    with results.test("t4_incident_message_published",
                      label="Incident message received on acme/incidents/created within 25s"):
        assert msg4 is not None, f"No message on {TOPIC_INCIDENT_CREATED} within {AGENT_TIMEOUT_S}s"
    with results.test("t4_incident_has_incident_id",
                      label="Response JSON contains a non-empty incident_id"):
        assert msg4 is not None, "No message (prerequisite failed)"
        assert "incident_id" in msg4 and msg4["incident_id"], f"Missing incident_id: {msg4}"

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + results.summary())
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)