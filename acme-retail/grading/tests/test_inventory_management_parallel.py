"""
test_inventory_management_parallel.py — PARALLEL version with beautiful UI.

Runs all 3 tests concurrently with a live progress table and clean output.
"""

import sys
import os
import json
import time
import threading
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.database import assert_inventory_status, assert_field_equals
from framework.seeder import full_reset
from tests.test_utils import (
    _s, _bold, _dim, _cyan, _green, _yellow, _red,
    _bold_cyan, _bold_green, _bold_red,
    _visual_width, TestInfo, ProgressTable, QuietSpinner,
    _run_scenario, _text,
)


# ── Constants ──────────────────────────────────────────────────────────────
OOS_SKU         = "SKU-PHONE-099"
OOS_NAME        = "Premium Smartphone X"
OOS_SUPPLIER_ID = "SUP-001"
OOS_SUPPLIER    = "TechSupply Global"
RESTOCK_QTY_1   = 50

OOS_SKU_2       = "SKU-DOCKSTATION-007"
OOS_NAME_2      = "USB-C Docking Station Pro"
RESTOCK_QTY_2   = 20

LOW_SKU         = "SKU-LAPTOP-002"
LOW_NAME        = "Gaming Laptop Xtreme"
WRITE_OFF_DELTA = -3

TOPIC_RESTOCK_RECEIVED     = "acme/suppliers/restock-received"
TOPIC_INVENTORY_ADJUSTMENT = "acme/inventory/adjustment"
TOPIC_INVENTORY_UPDATED    = "acme/inventory/updated"

AGENT_TIMEOUT_S  = 30
POST_MSG_SLEEP_S = 3


# ── Test Functions ─────────────────────────────────────────────────────────
def test_1_restock_oos_to_instock(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 1 — Restock out-of-stock item → in_stock"""
    test_num = 1
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INVENTORY_UPDATED,
            pub_topic=TOPIC_RESTOCK_RECEIVED,
            pub_payload={
                "item_id": OOS_SKU,
                "quantity_received": RESTOCK_QTY_1,
                "supplier_id": OOS_SUPPLIER_ID,
                "supplier_name": OOS_SUPPLIER,
            },
            predicate=lambda m: OOS_SKU in json.dumps(m),
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
        with results.test("t1_available_qty_updated", label=f"{OOS_SKU} available_quantity updated to {RESTOCK_QTY_1}"):
            try:
                assert_field_equals("inventory", "item_id", OOS_SKU, "available_quantity", RESTOCK_QTY_1)
            except Exception as exc:
                assert False, str(exc)
        with results.test("t1_status_in_stock", label=f"{OOS_SKU} status updated to 'in_stock'"):
            try:
                assert_inventory_status(OOS_SKU, "in_stock")
            except Exception as exc:
                assert False, str(exc)

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 3, 3)


def test_2_writeoff_low_to_oos(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 2 — Write-off reduces low-stock item to out-of-stock"""
    test_num = 2
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INVENTORY_UPDATED,
            pub_topic=TOPIC_INVENTORY_ADJUSTMENT,
            pub_payload={
                "item_id": LOW_SKU,
                "adjustment_type": "write_off",
                "quantity_delta": WRITE_OFF_DELTA,
                "reason": "Damaged during warehouse inspection",
            },
            predicate=lambda m: LOW_SKU in json.dumps(m),
            timeout_s=AGENT_TIMEOUT_S,
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t2_response_received", False, str(exc))
        return

    with lock:
        with results.test("t2_response_received", label="Message received on broker"):
            assert msg is not None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t2_available_qty_zeroed", label=f"{LOW_SKU} available_quantity reduced to 0"):
            try:
                assert_field_equals("inventory", "item_id", LOW_SKU, "available_quantity", 0)
            except Exception as exc:
                assert False, str(exc)
        with results.test("t2_status_out_of_stock", label=f"{LOW_SKU} status updated to 'out_of_stock'"):
            try:
                assert_inventory_status(LOW_SKU, "out_of_stock")
            except Exception as exc:
                assert False, str(exc)

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 3, 3)


def test_3_restock_after_writeoff(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 3 — Restock after write-off → in_stock"""
    test_num = 3
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INVENTORY_UPDATED,
            pub_topic=TOPIC_RESTOCK_RECEIVED,
            pub_payload={
                "item_id": OOS_SKU_2,
                "quantity_received": RESTOCK_QTY_2,
                "supplier_id": "SUP-007",
                "supplier_name": "Cable Connections Inc",
            },
            predicate=lambda m: OOS_SKU_2 in json.dumps(m),
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
        with results.test("t3_available_qty_updated", label=f"{OOS_SKU_2} available_quantity updated to {RESTOCK_QTY_2}"):
            try:
                assert_field_equals("inventory", "item_id", OOS_SKU_2, "available_quantity", RESTOCK_QTY_2)
            except Exception as exc:
                assert False, str(exc)
        with results.test("t3_status_in_stock", label=f"{OOS_SKU_2} status restored to 'in_stock'"):
            try:
                assert_inventory_status(OOS_SKU_2, "in_stock")
            except Exception as exc:
                assert False, str(exc)

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 3, 3)


# ── Custom Summary ─────────────────────────────────────────────────────────
def print_organized_summary(results: ResultCollector):
    """Print results organized by test number (not completion order)."""
    W = 62
    thick = "═" * W

    # Test metadata (in order)
    test_labels = {
        1: "Test 1 — Restock out-of-stock item → in_stock",
        2: "Test 2 — Write-off reduces low-stock → out_of_stock",
        3: "Test 3 — Restock after write-off → in_stock",
    }

    # Test name prefixes (how they're recorded)
    test_prefixes = {
        1: "t1_",
        2: "t2_",
        3: "t3_",
    }

    # Header
    print(_bold_cyan(thick))
    print(_bold(f"  Test Results  —  {results.suite_name}"))
    print(_bold_cyan(thick))

    # Group results by test number
    for test_num in range(1, 4):
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
    results = ResultCollector(suite_name="InventoryManagementAgent (Parallel)")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Inventory Management Agent", "1"))
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
        TestInfo(1, "test_1", "Restock OOS → in_stock"),
        TestInfo(2, "test_2", "Write-off low → OOS"),
        TestInfo(3, "test_3", "Restock after write-off"),
    ]

    progress = ProgressTable(test_info)
    progress.start()

    # Run tests in parallel
    lock = threading.Lock()
    test_functions = [
        (test_1_restock_oos_to_instock, results, lock, progress),
        (test_2_writeoff_low_to_oos, results, lock, progress),
        (test_3_restock_after_writeoff, results, lock, progress),
    ]

    start_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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
