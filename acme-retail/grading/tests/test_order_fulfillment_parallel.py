"""
test_order_fulfillment_parallel.py — PARALLEL version with beautiful UI.

Runs all 5 tests concurrently with a live progress table and clean output.
"""

import sys
import os
import json
import time
import threading
import concurrent.futures
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.database import assert_order_status, assert_field_equals, set_inventory_quantity
from framework.seeder import full_reset
from tests.test_utils import (
    _s, _bold, _dim, _cyan, _green, _yellow, _red,
    _bold_cyan, _bold_green, _bold_red,
    _visual_width, TestInfo, ProgressTable, QuietSpinner,
    _run_scenario, _text,
)


# ── Constants ──────────────────────────────────────────────────────────────
IN_STOCK_SKU   = "SKU-MOUSE-042"
IN_STOCK_NAME  = "Wireless Mouse Elite"
IN_STOCK_PRICE = 49.99

OOS_SKU        = "SKU-PHONE-099"
OOS_NAME       = "Premium Smartphone X"
OOS_PRICE      = 899.99

TEST3_RESTOCK_SKU  = "SKU-TABLET-055"
TEST3_RESTOCK_NAME = "Pro Tablet 12"

BLOCKED_ORDER_ID     = "ORD-2026-004"
DELAYED_SHIPMENT_ID  = "SHIP-2026-0048"
DELAYED_ORDER_ID     = "ORD-2026-005"
DELAYED_NEW_DELIVERY = "2026-03-12T18:00:00Z"
CANCEL_ORDER_ID      = "ORD-2026-003"

TOPIC_ORDER_CREATED     = "acme/orders/created"
TOPIC_INVENTORY_UPDATED = "acme/inventory/updated"
TOPIC_SHIPMENT_DELAYED  = "acme/logistics/shipment-delayed"
TOPIC_ORDER_CANCELLED   = "acme/orders/cancelled"
TOPIC_ORDER_RESULT      = "acme/orders/decision"

AGENT_TIMEOUT_S  = 30
POST_MSG_SLEEP_S = 3


# ── Helpers ────────────────────────────────────────────────────────────────
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


# ── Test Functions ─────────────────────────────────────────────────────────
def test_1_in_stock_order(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 1 — In-stock order → validated"""
    test_num = 1
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    order_id = "ORD-GRADE-VALID-001"
    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_ORDER_RESULT,
            pub_topic=TOPIC_ORDER_CREATED,
            pub_payload=_new_order_payload(order_id, IN_STOCK_SKU, IN_STOCK_NAME, IN_STOCK_PRICE),
            predicate=lambda m: order_id in json.dumps(m),
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t1_response_received", False, str(exc))
        return

    with lock:
        with results.test("t1_response_received", label="Message received on broker"):
            assert msg is not None
        with results.test("t1_decision_validated", label='Response indicates "validated"'):
            assert "validated" in _text(msg) or "valid" in _text(msg)

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t1_db_status", label="Database status: 'validated'"):
            assert_order_status(order_id, "validated")

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 3, 3)


def test_2_out_of_stock_order(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 2 — Out-of-stock order → blocked"""
    test_num = 2
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    order_id = "ORD-GRADE-BLOCKED-001"
    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_ORDER_RESULT,
            pub_topic=TOPIC_ORDER_CREATED,
            pub_payload=_new_order_payload(order_id, OOS_SKU, OOS_NAME, OOS_PRICE),
            predicate=lambda m: order_id in json.dumps(m),
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t2_response_received", False, str(exc))
        return

    with lock:
        with results.test("t2_response_received", label="Message received on broker"):
            assert msg is not None
        with results.test("t2_decision_blocked", label='Response indicates "blocked"'):
            assert ("blocked" in _text(msg) or "out of stock" in _text(msg) or
                    "insufficient" in _text(msg) or "cannot" in _text(msg))

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t2_db_status", label="Database status: 'blocked'"):
            assert_order_status(order_id, "blocked")

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 3, 3)


def test_3_inventory_restock(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 3 — Inventory restock → re-validate"""
    test_num = 3
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    set_inventory_quantity(TEST3_RESTOCK_SKU, stock_quantity=30, available_quantity=30, status="in_stock")

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_ORDER_RESULT,
            pub_topic=TOPIC_INVENTORY_UPDATED,
            pub_payload={
                "item_id": TEST3_RESTOCK_SKU,
                "product_name": TEST3_RESTOCK_NAME,
                "quantity_added": 30,
                "new_stock_quantity": 30,
                "new_status": "in_stock",
            },
            predicate=lambda m: BLOCKED_ORDER_ID in json.dumps(m),
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
        with results.test("t3_order_revalidated", label=f"Order {BLOCKED_ORDER_ID} re-validated"):
            assert_order_status(BLOCKED_ORDER_ID, "validated")

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_4_shipment_delay(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 4 — Shipment delay → update ETA"""
    test_num = 4
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_ORDER_RESULT,
            pub_topic=TOPIC_SHIPMENT_DELAYED,
            pub_payload={
                "shipment_id": DELAYED_SHIPMENT_ID,
                "tracking_number": "1Z999AA10123456791",
                "order_id": DELAYED_ORDER_ID,
                "carrier": "ExpressAir Priority",
                "reason": "Severe weather",
                "original_estimated_delivery": "2026-03-11T12:00:00Z",
                "new_estimated_delivery": DELAYED_NEW_DELIVERY,
                "delay_hours": 30,
            },
            predicate=lambda m: DELAYED_ORDER_ID in json.dumps(m) or DELAYED_SHIPMENT_ID in json.dumps(m),
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
        with results.test("t4_delivery_updated", label="Delivery date updated in DB"):
            assert_field_equals("orders", "order_id", DELAYED_ORDER_ID,
                              "estimated_delivery", DELAYED_NEW_DELIVERY)

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_5_order_cancelled(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 5 — Order cancelled → status"""
    test_num = 5
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_ORDER_RESULT,
            pub_topic=TOPIC_ORDER_CANCELLED,
            pub_payload={
                "order_id": CANCEL_ORDER_ID,
                "reason": "Customer requested cancellation",
                "cancelled_by": "customer",
            },
            predicate=lambda m: CANCEL_ORDER_ID in json.dumps(m),
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
        with results.test("t5_db_status", label="Database status: 'cancelled'"):
            assert_order_status(CANCEL_ORDER_ID, "cancelled")

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
        1: "Test 1 — In-stock order validated",
        2: "Test 2 — Out-of-stock order blocked",
        3: "Test 3 — Inventory restock",
        4: "Test 4 — Shipment delay",
        5: "Test 5 — Order cancellation",
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
    results = ResultCollector(suite_name="OrderFulfillmentAgent (Parallel)")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Order Fulfillment Agent", "1"))
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
        TestInfo(1, "test_1", "In-stock order → validated"),
        TestInfo(2, "test_2", "Out-of-stock → blocked"),
        TestInfo(3, "test_3", "Restock → re-validate"),
        TestInfo(4, "test_4", "Shipment delay → update ETA"),
        TestInfo(5, "test_5", "Order cancelled → status"),
    ]

    progress = ProgressTable(test_info)
    progress.start()

    # Run tests in parallel
    lock = threading.Lock()
    test_functions = [
        (test_1_in_stock_order, results, lock, progress),
        (test_2_out_of_stock_order, results, lock, progress),
        (test_3_inventory_restock, results, lock, progress),
        (test_4_shipment_delay, results, lock, progress),
        (test_5_order_cancelled, results, lock, progress),
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
