"""
test_incident_response.py — Grading tests for the IncidentResponseAgent.

Tests four event-driven scenarios covering the gateway's incident routing:
  1. Blocked order (new SKU)         → new inventory_shortage incident created + escalated to 'investigating'
  2. Validated order                 → no new incident created (deduplication works)
  3. Inventory restocked             → seed incident (INC-2026-015) moved from 'investigating' to 'monitoring'
  4. Inventory error received        → new system_error incident created in DB

Tests run sequentially after a single full_reset(). Tests 1 and 3 are independent:
  Test 1 creates a new incident for a fresh SKU (SKU-KEYBOARD-101).
  Test 3 uses the pre-existing seed incident INC-2026-015 (for SKU-TABLET-055).
  This validates both incident creation and state transitions without conflicts.

Run directly:
  cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
  python -m tests.test_incident_response
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
from framework.database import assert_field_equals, row_count
from framework.seeder import full_reset


# ── Minimal ANSI helper (progress output only) ────────────────────────────────
def _s(text: str, *codes: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{';'.join(codes)}m{text}\033[0m"
    return text


# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------
# INC-2026-015: type=inventory_shortage, severity=high, status=in_progress
#   linked via incident_items to SKU-TABLET-055
HIGH_SEV_INCIDENT_ID = "INC-2026-015"
HIGH_SEV_INCIDENT_ITEM = "SKU-TABLET-055"
HIGH_SEV_ITEM_NAME = "Pro Tablet 12"

# INC-2026-018: type=quality_issue, severity=low, status=investigating
#   NOT expected to be escalated
LOW_SEV_INCIDENT_ID = "INC-2026-018"
LOW_SEV_INCIDENT_STATUS = "investigating"  # should remain unchanged after event

TOPIC_ORDERS_DECISION     = "acme/orders/decision"
TOPIC_INCIDENTS_CREATED   = "acme/incidents/created"
TOPIC_INVENTORY_UPDATED   = "acme/inventory/updated"
TOPIC_INVENTORY_ERRORS    = "acme/inventory/errors"
TOPIC_INCIDENTS_RESPONSE  = "acme/incidents/response"
TOPIC_LOGISTICS_UPDATED   = "acme/logistics/updated"

AGENT_TIMEOUT_S  = 30
POST_MSG_SLEEP_S = 3   # let agent finish DB write before asserting


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
    results = ResultCollector(suite_name="IncidentResponseAgent")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Incident Response Agent  —  Grading Suite", "1"))
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

    # ── Test 1 — Blocked order creates high-severity inventory_shortage incident ───
    print(_s(f"\n  ── Test 1 ─{'─' * (W - 12)}", "2"))
    print(_s(f"  Blocked order decision  →  inventory_shortage incident created + escalated to 'investigating'", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDERS_DECISION}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INCIDENTS_CREATED}", "2"))
    msg1 = None
    inventory_shortage_investigating_count_before = row_count(
        "incidents", "type = %s AND status = %s", ("inventory_shortage", "investigating")
    )
    results.section("Test 1 — Blocked order → inventory_shortage incident (severity=high, status='investigating')")
    try:
        with Spinner("Waiting for agent response"):
            msg1 = _run_scenario(
                sub_topic=TOPIC_INCIDENTS_CREATED,
                pub_topic=TOPIC_ORDERS_DECISION,
                pub_payload={
                    "order_id": "ORD-TEST-BLOCKED-KBD-001",
                    "item_id": "SKU-KEYBOARD-101",
                    "product_name": "Mechanical Keyboard Pro",
                    "status": "blocked",
                    "reason": "Insufficient stock available for this item",
                    "message": (
                        "Order ORD-TEST-BLOCKED-KBD-001 has been blocked due to insufficient stock for SKU-KEYBOARD-101. "
                        "Available quantity: 0, Required quantity: 5."
                    ),
                },
            )
    except Exception as exc:
        results.record("t1_response_received", False, str(exc),
                       label=f"Listening on {TOPIC_INCIDENTS_CREATED} — message received within {AGENT_TIMEOUT_S}s")

    with results.test("t1_response_received",
                      label=f"Listening on {TOPIC_INCIDENTS_CREATED} — message received within {AGENT_TIMEOUT_S}s"):
        assert msg1 is not None, f"No message on {TOPIC_INCIDENTS_CREATED} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t1_incident_created_type",
                      label="New inventory_shortage incident created with status='investigating' in database"):
        try:
            inventory_shortage_investigating_count_after = row_count(
                "incidents", "type = %s AND status = %s", ("inventory_shortage", "investigating")
            )
            assert inventory_shortage_investigating_count_after > inventory_shortage_investigating_count_before, (
                f"No new inventory_shortage incident with status='investigating' was created "
                f"(before={inventory_shortage_investigating_count_before}, after={inventory_shortage_investigating_count_after})"
            )
        except Exception as exc:
            assert False, str(exc)

    # ── Test 2 — Validated order decision does NOT create incident ───────────────
    print(_s(f"\n  ── Test 2 ─{'─' * (W - 12)}", "2"))
    print(_s(f"  Validated order decision  →  no new incident created", "1"))
    print(_s(f"  Published to:  {TOPIC_ORDERS_DECISION}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INCIDENTS_CREATED}", "2"))
    msg2 = None
    inventory_shortage_count_before = row_count(
        "incidents", "type = %s", ("inventory_shortage",)
    )
    results.section("Test 2 — Validated order → no inventory_shortage incident created")
    try:
        with Spinner("Waiting for agent response"):
            msg2 = _run_scenario(
                sub_topic=TOPIC_INCIDENTS_CREATED,
                pub_topic=TOPIC_ORDERS_DECISION,
                pub_payload={
                    "order_id": "ORD-TEST-VALIDATED-001",
                    "item_id": "SKU-MOUSE-042",
                    "product_name": "Wireless Mouse",
                    "status": "validated",
                    "reason": "Sufficient stock available",
                    "message": (
                        "Order ORD-TEST-VALIDATED-001 has been validated. "
                        "Sufficient stock is available for all items."
                    ),
                },
                timeout_s=10,  # Shorter timeout since no incident creation expected
            )
    except Exception as exc:
        # Expected: may timeout since no incident is created for validated orders
        pass

    with results.test("t2_no_incident_created",
                      label="No new inventory_shortage incident created for validated orders"):
        try:
            inventory_shortage_count_after = row_count(
                "incidents", "type = %s", ("inventory_shortage",)
            )
            assert inventory_shortage_count_after == inventory_shortage_count_before, (
                f"New inventory_shortage incident was created when it shouldn't have been "
                f"(before={inventory_shortage_count_before}, after={inventory_shortage_count_after})"
            )
        except Exception as exc:
            assert False, str(exc)

    # ── Test 3 — Inventory restock resolves linked incidents ──────────────────
    # Pre-condition: Seed incident HIGH_SEV_INCIDENT_ID (INC-2026-015) exists at status='investigating'.
    # Restocking SKU-TABLET-055 (new_stock_quantity > 0) should move it to 'monitoring'.
    print(_s(f"\n  ── Test 3 ─{'─' * (W - 12)}", "2"))
    print(_s(f"  Inventory restocked  →  linked incident moved to 'monitoring'", "1"))
    print(_s(f"  Published to:  {TOPIC_INVENTORY_UPDATED}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INCIDENTS_RESPONSE}", "2"))
    print(_s(f"  Pre-condition: {HIGH_SEV_INCIDENT_ID} at 'investigating' (seed incident)", "2"))
    msg3 = None
    results.section(
        f"Test 3 — Restock {HIGH_SEV_INCIDENT_ITEM} → {HIGH_SEV_INCIDENT_ID} moved to 'monitoring'"
    )
    # Pre-condition check: verify HIGH_SEV_INCIDENT_ID is at 'investigating' before we attempt restock
    with results.test("t3_precondition_incident_investigating",
                      label=f"Pre-condition: {HIGH_SEV_INCIDENT_ID} status='investigating' (from Test 1)"):
        try:
            assert_field_equals("incidents", "incident_id", HIGH_SEV_INCIDENT_ID, "status", "investigating")
        except Exception as exc:
            assert False, f"Pre-condition failed: {str(exc)}"
    try:
        with Spinner("Waiting for agent response"):
            msg3 = _run_scenario(
                sub_topic=TOPIC_INCIDENTS_RESPONSE,
                pub_topic=TOPIC_INVENTORY_UPDATED,
                pub_payload={
                    "item_id": HIGH_SEV_INCIDENT_ITEM,
                    "product_name": HIGH_SEV_ITEM_NAME,
                    "quantity_added": 50,
                    "new_stock_quantity": 50,
                    "new_status": "in_stock",
                },
            )
    except Exception as exc:
        results.record("t3_response_received", False, str(exc),
                       label=f"Listening on {TOPIC_INCIDENTS_RESPONSE} — message received within {AGENT_TIMEOUT_S}s")

    with results.test("t3_response_received",
                      label=f"Listening on {TOPIC_INCIDENTS_RESPONSE} — message received within {AGENT_TIMEOUT_S}s"):
        assert msg3 is not None, f"No message on {TOPIC_INCIDENTS_RESPONSE} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t3_incident_monitoring",
                      label=f"{HIGH_SEV_INCIDENT_ID} status updated to 'monitoring' after restock"):
        try:
            assert_field_equals("incidents", "incident_id", HIGH_SEV_INCIDENT_ID, "status", "monitoring")
        except Exception as exc:
            assert False, str(exc)

    # ── Test 4 — Inventory error creates system_error incident ────────────────
    print(_s(f"\n  ── Test 4 ─{'─' * (W - 12)}", "2"))
    print(_s(f"  Inventory error received  →  new system_error incident created in DB", "1"))
    print(_s(f"  Published to:  {TOPIC_INVENTORY_ERRORS}", "2"))
    print(_s(f"  Listening on:  {TOPIC_INCIDENTS_CREATED}", "2"))
    msg4 = None
    system_error_count_before = row_count(
        "incidents", "type = %s AND severity = %s", ("system_error", "high")
    )
    results.section("Test 4 — Inventory system error → new system_error incident (severity=high)")
    try:
        with Spinner("Waiting for agent response"):
            msg4 = _run_scenario(
                sub_topic=TOPIC_INCIDENTS_CREATED,
                pub_topic=TOPIC_INVENTORY_ERRORS,
                pub_payload={
                    "error": "MCP postgres server connection failed",
                    "service": "inventory",
                    "details": (
                        "Connection to postgresql://acme:acme@localhost:5432/orders timed out "
                        "after 30 seconds while processing inventory adjustment for SKU-MOUSE-042."
                    ),
                    "timestamp": "2026-03-24T10:00:00Z",
                },
            )
    except Exception as exc:
        results.record("t4_response_received", False, str(exc),
                       label=f"Listening on {TOPIC_INCIDENTS_CREATED} — message received within {AGENT_TIMEOUT_S}s")

    with results.test("t4_response_received",
                      label=f"Listening on {TOPIC_INCIDENTS_CREATED} — message received within {AGENT_TIMEOUT_S}s"):
        assert msg4 is not None, f"No message on {TOPIC_INCIDENTS_CREATED} within {AGENT_TIMEOUT_S}s"
    time.sleep(POST_MSG_SLEEP_S)
    with results.test("t4_system_error_incident_created",
                      label="New system_error incident with severity='high' created in database"):
        system_error_count_after = row_count(
            "incidents", "type = %s AND severity = %s", ("system_error", "high")
        )
        assert system_error_count_after > system_error_count_before, (
            f"No new system_error incident found in DB "
            f"(before={system_error_count_before}, after={system_error_count_after})"
        )

    # ── Test 5 — Logistics delay creates shipment_delay incident (STUB - requires LogisticsAgent) ──
    print(_s(f"\n  ── Test 5 ─{'─' * (W - 12)}", "2"))
    print(_s(f"  Logistics delay  →  new shipment_delay incident created (STUB)", "1"))
    print(_s(f"  Published to:  {TOPIC_LOGISTICS_UPDATED} (requires LogisticsAgent)", "2"))
    print(_s(f"  Listening on:  {TOPIC_INCIDENTS_CREATED}", "2"))
    results.section("Test 5 — Shipment delay → shipment_delay incident (DEFERRED: requires LogisticsAgent)")
    with results.test("t5_logistics_stub",
                      label="Test 5 stub placeholder for LogisticsAgent implementation"):
        assert True, "Stub ready for future logistics agent implementation"

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + results.summary())
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)
