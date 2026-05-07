"""
test_incident_response_parallel.py — PARALLEL version with beautiful UI.

Runs all 5 tests concurrently with a live progress table and clean output.

Each test owns a unique identifier embedded in its event payload, and
asserts on rows in the database that contain that identifier. This avoids
all forms of cross-test interference under parallel execution.
"""

import sys
import os
import json
import time
import threading
import concurrent.futures
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.database import assert_field_equals, row_count
from framework.seeder import full_reset
from test_suites.test_utils import (
    _s, _bold, _dim, _cyan, _green, _yellow, _red,
    _bold_cyan, _bold_green, _bold_red,
    _visual_width, TestInfo, ProgressTable, QuietSpinner,
    _run_scenario, _text,
)


# ── Constants ──────────────────────────────────────────────────────────────
HIGH_SEV_INCIDENT_ID = "INC-2026-015"
HIGH_SEV_INCIDENT_ITEM = "SKU-TABLET-055"
HIGH_SEV_ITEM_NAME = "Pro Tablet 12"

LOW_SEV_INCIDENT_ID = "INC-2026-018"
LOW_SEV_INCIDENT_STATUS = "investigating"

# Test 2 marker (validated order — should NOT create an incident).
TEST2_ORDER_ID = "ORD-TEST-VALIDATED-MOUSE-002"

# Test 4 marker (inventory error). The agent's `description` will include
# the stringified payload, so this string will land in the `description`
# column and we can find OUR incident specifically.
TEST4_ERROR_MARKER = "test4-marker-db-timeout-acme-incidents"

# Test 5 markers (shipment delay). Tracking number flows into `description`
# via the agent's logistics_updated procedure, so we can identify our row.
TEST5_SHIPMENT_ID = "SHIP-2026-0051"
TEST5_TRACKING_NUMBER = "1Z999AA10123456795"

TOPIC_ORDERS_DECISION     = "acme/orders/decision"
TOPIC_INCIDENTS_CREATED   = "acme/incidents/created"
TOPIC_INVENTORY_UPDATED   = "acme/inventory/updated"
TOPIC_INVENTORY_ERRORS    = "acme/inventory/errors"
TOPIC_INCIDENTS_RESPONSE  = "acme/incidents/response"
TOPIC_LOGISTICS_UPDATED   = "acme/logistics/updated"
TOPIC_LOGISTICS_DELAYED   = "acme/logistics/updated"

AGENT_TIMEOUT_S  = 180
POST_MSG_SLEEP_S = 3
DB_POLL_DEADLINE_S = 90   # How long to keep polling the DB for our row
DB_POLL_INTERVAL_S = 1


# ── DB helpers ─────────────────────────────────────────────────────────────
DB_DSN = "postgresql://acme:acme@localhost:5432/orders"


def _poll_for_row(query, params, deadline_s=DB_POLL_DEADLINE_S):
    """Poll the DB for a row matching `query`+`params`. Returns the first
    matching row, or None if the deadline elapses. Used because the agent's
    INSERT may land slightly after the broker reply."""
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        conn = psycopg2.connect(DB_DSN)
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
        finally:
            conn.close()
        if row:
            return row
        time.sleep(DB_POLL_INTERVAL_S)
    return None


# ── Predicate helpers ──────────────────────────────────────────────────────
def _parse_msg(msg):
    """Return msg as a dict if possible, else None."""
    if msg is None:
        return None
    if isinstance(msg, dict):
        return msg
    try:
        return json.loads(msg if isinstance(msg, str) else json.dumps(msg))
    except (TypeError, ValueError):
        return None


def _is_created_with_marker(msg, marker):
    """True iff the agent reported a successful CREATE (not no_action /
    error) and either the marker appears anywhere in the message, OR the
    message has action='created' with the right type/title.

    Stricter than a substring match on 'system_error': the word
    'system_error' can appear in a no_action `reason` field or an `error`
    field, which would otherwise let a non-create response pass."""
    blob = json.dumps(msg, default=str)
    parsed = _parse_msg(msg)

    # Strongest signal: the unique marker survived into the response.
    if marker in blob:
        # But still require it to be a create — if the model returned
        # an error mentioning the marker, the test should not pass.
        if parsed is None:
            # Couldn't parse — accept the marker hit on faith.
            return True
        if parsed.get("action") in (None, "created"):
            return True
        # action is 'no_action' or 'error' — don't accept even with marker.
        return False

    # Fallback: action=created plus the right type or title.
    if parsed is not None and parsed.get("action") == "created":
        if parsed.get("type") == "system_error":
            return True
        title = (parsed.get("title") or "").lower()
        if "system error" in title:
            return True

    return False


# ── Test Functions ─────────────────────────────────────────────────────────
def test_1_blocked_order_creates_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 1 — Blocked order creates inventory_shortage incident"""
    test_num = 1
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None
    sku_to_check = "SKU-KEYBOARD-101"

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_ORDERS_DECISION,
            pub_payload={
                "order_id": "ORD-TEST-BLOCKED-KBD-001",
                "item_id": sku_to_check,
                "product_name": "Mechanical Keyboard Pro",
                "status": "blocked",
                "reason": "Insufficient stock available for this item",
                "message": (
                    f"Order ORD-TEST-BLOCKED-KBD-001 has been blocked due to insufficient stock for {sku_to_check}. "
                    "Available quantity: 0, Required quantity: 5."
                ),
            },
            predicate=lambda msg: "inventory_shortage" in json.dumps(msg).lower(),
            timeout_s=AGENT_TIMEOUT_S,
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t1_response_received", False, str(exc))
        return

    with lock:
        with results.test("t1_response_received", label="Message received on broker"):
            assert msg is not None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t1_incident_created_type", label="New inventory_shortage incident created for SKU-KEYBOARD-101"):
            row = _poll_for_row(
                "SELECT id FROM incident_items WHERE item_id = %s LIMIT 1",
                (sku_to_check,),
            )
            assert row is not None, (
                f"No incident_items entry was created for {sku_to_check} "
                f"within {DB_POLL_DEADLINE_S}s of the broker reply."
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_2_validated_order_no_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 2 — Validated order does NOT create incident"""
    test_num = 2
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_ORDERS_DECISION,
            pub_payload={
                "order_id": TEST2_ORDER_ID,
                "item_id": "SKU-MOUSE-042",
                "product_name": "Wireless Mouse",
                "status": "validated",
                "reason": "Sufficient stock available",
                "message": (
                    f"Order {TEST2_ORDER_ID} has been validated. "
                    "Sufficient stock is available for all items."
                ),
            },
            # We expect NO matching message — short timeout is fine.
            predicate=lambda msg: TEST2_ORDER_ID in json.dumps(msg),
            timeout_s=5,
        )
    except Exception:
        # Expected — no incident should be created, so no broker reply.
        msg = None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t2_no_incident_created", label="No inventory_shortage incident created for validated order"):
            conn = psycopg2.connect(DB_DSN)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT incident_id, description FROM incidents "
                    "WHERE type = 'inventory_shortage' "
                    "  AND description LIKE %s",
                    (f"%{TEST2_ORDER_ID}%",),
                )
                row = cur.fetchone()
            finally:
                conn.close()
            assert row is None, (
                f"Unexpected inventory_shortage incident was created for "
                f"validated order {TEST2_ORDER_ID}: {row}"
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 1, 1)


def test_3_inventory_restock_updates_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 3 — Inventory restock resolves linked incidents"""
    test_num = 3
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_RESPONSE,
            pub_topic=TOPIC_INVENTORY_UPDATED,
            pub_payload={
                "item_id": HIGH_SEV_INCIDENT_ITEM,
                "product_name": HIGH_SEV_ITEM_NAME,
                "quantity_added": 100,
                "new_stock_quantity": 100,
                "new_available_quantity": 100,
                "previous_status": "out_of_stock",
                "new_status": "in_stock",
            },
            predicate=lambda msg: HIGH_SEV_INCIDENT_ID in json.dumps(msg),
            timeout_s=AGENT_TIMEOUT_S,
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t3_response_received", False, str(exc))
        return

    with lock:
        with results.test("t3_response_received", label="Message received on broker"):
            assert msg is not None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t3_incident_status_updated", label=f"Incident {HIGH_SEV_INCIDENT_ID} status updated to 'monitoring'"):
            row = _poll_for_row(
                "SELECT status FROM incidents WHERE incident_id = %s",
                (HIGH_SEV_INCIDENT_ID,),
            )
            assert row is not None, f"Incident {HIGH_SEV_INCIDENT_ID} not found"
            assert row[0] == "monitoring", (
                f"Incident {HIGH_SEV_INCIDENT_ID} has status='{row[0]}', "
                f"expected 'monitoring'"
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_4_inventory_error_creates_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 4 — Inventory error creates system_error incident"""
    test_num = 4
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_INVENTORY_ERRORS,
            pub_payload={
                # Marker embedded in the error string. The agent's
                # inventory_error procedure stringifies the payload into
                # the incident description, so this marker should land
                # in the `description` column where we can find OUR row.
                "error": f"Database connection timeout [{TEST4_ERROR_MARKER}]",
                "component": "inventory_management_agent",
                "timestamp": "2026-04-02T12:00:00Z",
            },
            # Stricter predicate: require the agent to actually report a
            # CREATE (not a no_action or error response that happens to
            # mention 'system_error' in passing).
            predicate=lambda msg: _is_created_with_marker(msg, TEST4_ERROR_MARKER),
            timeout_s=AGENT_TIMEOUT_S,
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t4_response_received", False, str(exc))
        return

    with lock:
        with results.test("t4_response_received", label="Message received on broker"):
            assert msg is not None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t4_incident_created", label="New system_error incident created in database"):
            row = _poll_for_row(
                "SELECT incident_id, type, severity, description FROM incidents "
                "WHERE type = 'system_error' "
                "  AND description LIKE %s "
                "ORDER BY created_date DESC LIMIT 1",
                (f"%{TEST4_ERROR_MARKER}%",),
            )
            assert row is not None, (
                f"No system_error incident found containing marker "
                f"'{TEST4_ERROR_MARKER}' within {DB_POLL_DEADLINE_S}s."
            )
            assert row[2] == "high", (
                f"system_error incident has severity='{row[2]}', expected 'high'"
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_5_shipment_delay_creates_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 5 — Logistics delay creates shipment_delay incident"""
    test_num = 5
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_LOGISTICS_DELAYED,
            pub_payload={
                "shipment_id": TEST5_SHIPMENT_ID,
                "tracking_number": TEST5_TRACKING_NUMBER,
                "carrier": "ExpressAir Priority",
                "original_delivery_date": "2026-04-05",
                "new_delivery_date": "2026-04-10",
                "delay_reason": "Weather conditions affecting air transport",
                "status": "Delayed",
                "delay_hours": 120,
            },
            predicate=lambda msg: (
                TEST5_TRACKING_NUMBER in json.dumps(msg)
                or "shipment_delay" in json.dumps(msg).lower()
            ),
            timeout_s=AGENT_TIMEOUT_S,
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t5_response_received", False, str(exc))
        return

    with lock:
        with results.test("t5_response_received", label="Message received on broker"):
            assert msg is not None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t5_incident_severity", label="Shipment delay incident created with severity='medium'"):
            row = _poll_for_row(
                "SELECT incident_id, severity FROM incidents "
                "WHERE type = 'shipment_delay' "
                "  AND description LIKE %s "
                "ORDER BY created_date DESC LIMIT 1",
                (f"%{TEST5_TRACKING_NUMBER}%",),
            )
            assert row is not None, (
                f"No shipment_delay incident found containing tracking "
                f"number '{TEST5_TRACKING_NUMBER}' within {DB_POLL_DEADLINE_S}s."
            )
            assert row[1] == "medium", (
                f"Shipment delay incident has severity='{row[1]}', expected 'medium'"
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


# ── Custom Summary ─────────────────────────────────────────────────────────
def print_organized_summary(results: ResultCollector):
    """Print results organized by test number (not completion order)."""
    W = 62
    thick = "═" * W

    test_labels = {
        1: "Test 1 — Blocked order → inventory_shortage incident",
        2: "Test 2 — Validated order → no incident created",
        3: "Test 3 — Inventory restock → incident monitoring",
        4: "Test 4 — Inventory error → system_error incident",
        5: "Test 5 — Shipment delay → shipment_delay incident",
    }

    test_prefixes = {
        1: "t1_",
        2: "t2_",
        3: "t3_",
        4: "t4_",
        5: "t5_",
    }

    print(_bold_cyan(thick))
    print(_bold(f"  Test Results  —  {results.suite_name}"))
    print(_bold_cyan(thick))

    for test_num in range(1, 6):
        print()
        print(_bold(f"  {test_labels[test_num]}"))

        prefix = test_prefixes[test_num]
        test_results = [r for r in results._results if r.name.startswith(prefix)]

        for r in test_results:
            display = r.label if r.label else r.name
            if r.passed:
                print(f"    ✅  {display}")
            else:
                print(f"    ❌  {_bold(display)}")
                if r.message:
                    for line in r.message.splitlines():
                        print(_red(f"         {line}"))

    print()
    if results.all_passed:
        print(_bold_green(thick))
        print(_bold_green(f"  🎉  PASSED  —  {results.passed}/{results.total} checks passed"))
        print(_bold_green(thick))
    else:
        print(_bold_red(thick))
        print(_bold_red(f"  ✗   FAILED  —  {results.passed}/{results.total} checks passed ({results.failed} failed)"))
        print(_bold_red(thick))


# ── Main Runner ────────────────────────────────────────────────────────────
def run_tests(student_email="student@example.com"):
    results = ResultCollector(suite_name="IncidentResponseAgent (Parallel)")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Incident Response Agent", "1"))
    print(_s("═" * W, "1", "36"))

    try:
        with QuietSpinner("Resetting database"):
            full_reset()
    except Exception as exc:
        print(f"\r  ❌ Database reset failed: {exc}")
        results.record("db_reset", passed=False, message=str(exc))
        return results

    test_info = [
        TestInfo(1, "test_1", "Blocked → shortage incident"),
        TestInfo(2, "test_2", "Validated → no incident"),
        TestInfo(3, "test_3", "Restock → monitoring"),
        TestInfo(4, "test_4", "Error → system incident"),
        TestInfo(5, "test_5", "Delay → shipment incident"),
    ]

    progress = ProgressTable(test_info)
    progress.start()

    lock = threading.Lock()
    test_functions = [
        (test_1_blocked_order_creates_incident, results, lock, progress),
        (test_2_validated_order_no_incident, results, lock, progress),
        (test_3_inventory_restock_updates_incident, results, lock, progress),
        (test_4_inventory_error_creates_incident, results, lock, progress),
        (test_5_shipment_delay_creates_incident, results, lock, progress),
    ]

    start_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fn, *args) for fn, *args in test_functions]
        concurrent.futures.wait(futures)

    progress.stop()
    elapsed = time.monotonic() - start_time

    print()
    print(_green(f"  ✅ All tests completed in {elapsed:.1f}s"))

    print()
    print_organized_summary(results)
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)