"""
test_incident_response_parallel.py — PARALLEL version with beautiful UI.

Runs all 5 tests concurrently with a live progress table and clean output.
"""

import sys
import os
import json
import time
import threading
import concurrent.futures
import psycopg2
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.database import assert_field_equals, row_count
from framework.seeder import full_reset
from tests.test_utils import (
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

TEST5_SHIPMENT_ID = "SHIP-2026-0051"
TEST5_TRACKING_NUMBER = "1Z999AA10123456795"

TOPIC_ORDERS_DECISION     = "acme/orders/decision"
TOPIC_INCIDENTS_CREATED   = "acme/incidents/created"
TOPIC_INVENTORY_UPDATED   = "acme/inventory/updated"
TOPIC_INVENTORY_ERRORS    = "acme/inventory/errors"
TOPIC_INCIDENTS_RESPONSE  = "acme/incidents/response"
TOPIC_LOGISTICS_UPDATED   = "acme/logistics/updated"
TOPIC_LOGISTICS_DELAYED   = "acme/logistics/shipment-delayed"

AGENT_TIMEOUT_S  = 90
POST_MSG_SLEEP_S = 3


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
            try:
                # Check for incident linked to SKU-KEYBOARD-101 (not count-based to avoid parallel conflicts)
                # The incident might be linked via incident_items table
                max_retries = 3
                incident_found = False
                for attempt in range(max_retries):
                    # Check if there's an incident_items entry for SKU-KEYBOARD-101
                    incident_items_count = row_count(
                        "incident_items", "item_id = %s", (sku_to_check,)
                    )
                    if incident_items_count > 0:
                        incident_found = True
                        break
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait 2s before retry

                assert incident_found, (
                    f"No incident was created for {sku_to_check}. "
                    f"Expected to find an entry in incident_items table."
                )
            except Exception as exc:
                assert False, str(exc)

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_2_validated_order_no_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 2 — Validated order does NOT create incident"""
    test_num = 2
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    inventory_shortage_count_before = row_count(
        "incidents", "type = %s", ("inventory_shortage",)
    )

    try:
        msg = _run_scenario(
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
            predicate=lambda msg: "inventory_shortage" in json.dumps(msg).lower(),
            timeout_s=5,  # Short timeout since we expect no message
        )
    except Exception:
        # Expected to timeout since no incident should be created
        msg = None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t2_no_incident_created", label="No inventory_shortage incident created for validated order"):
            inventory_shortage_count_after = row_count(
                "incidents", "type = %s", ("inventory_shortage",)
            )
            assert inventory_shortage_count_after == inventory_shortage_count_before, (
                f"Unexpected inventory_shortage incident created for validated order "
                f"(before={inventory_shortage_count_before}, after={inventory_shortage_count_after})"
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
            try:
                assert_field_equals("incidents", "incident_id", HIGH_SEV_INCIDENT_ID, "status", "monitoring")
            except Exception as exc:
                assert False, str(exc)

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_4_inventory_error_creates_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 4 — Inventory error creates system_error incident"""
    test_num = 4
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    system_error_count_before = row_count(
        "incidents", "type = %s", ("system_error",)
    )

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_INVENTORY_ERRORS,
            pub_payload={
                "error": "Database connection timeout",
                "component": "inventory_management_agent",
                "timestamp": "2026-04-02T12:00:00Z",
            },
            predicate=lambda msg: "system_error" in json.dumps(msg).lower(),
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
            system_error_count_after = row_count(
                "incidents", "type = %s", ("system_error",)
            )
            assert system_error_count_after > system_error_count_before, (
                f"No new system_error incident was created "
                f"(before={system_error_count_before}, after={system_error_count_after})"
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

    # Capture count before — resilient to LLM-generated title format variations
    shipment_delay_count_before = row_count("incidents", "type = %s", ("shipment_delay",))

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
            },
            predicate=lambda msg: TEST5_SHIPMENT_ID in json.dumps(msg),
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
            # Count-based check — resilient to LLM-generated title format
            # (agent may title the incident "Weather Delay" instead of including SHIP-XXXX literally)
            shipment_delay_count_after = row_count("incidents", "type = %s", ("shipment_delay",))
            assert shipment_delay_count_after > shipment_delay_count_before, (
                f"No new shipment_delay incident was created for shipment {TEST5_SHIPMENT_ID}"
            )

            # Verify the severity of the most recently created shipment_delay incident
            conn = psycopg2.connect('postgresql://acme:acme@localhost:5432/orders')
            cur = conn.cursor()
            cur.execute(
                "SELECT incident_id, severity FROM incidents WHERE type = %s ORDER BY created_date DESC LIMIT 1",
                ("shipment_delay",)
            )
            row = cur.fetchone()
            conn.close()

            assert row is not None and row[1] == 'medium', (
                f"Shipment delay incident has severity='{row[1] if row else None}', expected 'medium'"
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


# ── Custom Summary ─────────────────────────────────────────────────────────
def print_organized_summary(results: ResultCollector):
    """Print results organized by test number (not completion order)."""
    W = 62
    thick = "═" * W

    # Test metadata (in order)
    test_labels = {
        1: "Test 1 — Blocked order → inventory_shortage incident",
        2: "Test 2 — Validated order → no incident created",
        3: "Test 3 — Inventory restock → incident monitoring",
        4: "Test 4 — Inventory error → system_error incident",
        5: "Test 5 — Shipment delay → shipment_delay incident",
    }

    # Test name prefixes (how they're recorded)
    test_prefixes = {
        1: "t1_",
        2: "t2_",
        3: "t3_",
        4: "t4_",
        5: "t5_",
    }

    # Header
    print(_bold_cyan(thick))
    print(_bold(f"  Test Results  —  {results.suite_name}"))
    print(_bold_cyan(thick))

    # Group results by test number
    for test_num in range(1, 6):
        print()
        print(_bold(f"  {test_labels[test_num]}"))

        # Find all results for this test
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

    # Footer
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

    # Set up progress tracker
    test_info = [
        TestInfo(1, "test_1", "Blocked → shortage incident"),
        TestInfo(2, "test_2", "Validated → no incident"),
        TestInfo(3, "test_3", "Restock → monitoring"),
        TestInfo(4, "test_4", "Error → system incident"),
        TestInfo(5, "test_5", "Delay → shipment incident"),
    ]

    progress = ProgressTable(test_info)
    progress.start()

    # Run tests in parallel
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

    # Print beautiful summary (organized by test number)
    print()
    print_organized_summary(results)
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)
