"""
test_email_tool_parallel.py — Module 500: Email Tool Integration

Verifies that the IncidentResponseAgent correctly uses the send_alert_email tool:
  - High-severity incidents (system_error via inventory error) trigger an alert email
  - Non-incident events (validated order) do NOT trigger an email

Follows the same parallel test pattern as test_incident_response_parallel.py.
"""

import sys
import os
import json
import time
import threading
import concurrent.futures
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.seeder import full_reset
from test_suites.test_utils import (
    _s, _bold, _dim, _cyan, _green, _yellow, _red,
    _bold_cyan, _bold_green, _bold_red,
    _visual_width, TestInfo, ProgressTable, QuietSpinner,
    _run_scenario, _text,
)


# ── Constants ──────────────────────────────────────────────────────────────
EMAIL_SERVICE_URL       = "http://localhost:3000"
TOPIC_INVENTORY_ERRORS  = "acme/inventory/errors"
TOPIC_INCIDENTS_CREATED = "acme/incidents/created"
TOPIC_ORDERS_DECISION   = "acme/orders/decision"

AGENT_TIMEOUT_S  = 45   # extra headroom for email tool round-trip
POST_MSG_SLEEP_S = 5    # allow send_alert_email tool call to complete

SAM_500_DIR = "/workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins/sam"


# ── Helpers ────────────────────────────────────────────────────────────────
def _get_email_count() -> int:
    """Return current email count from the mock email service."""
    resp = requests.get(f"{EMAIL_SERVICE_URL}/health", timeout=5)
    resp.raise_for_status()
    return resp.json().get("emailCount", 0)


# ── Test Functions ─────────────────────────────────────────────────────────
def test_1_high_severity_incident_sends_email(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    test_num = 1
    start = time.monotonic()
    progress.update_status(test_num, "🔄")

    try:
        msg = _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_INVENTORY_ERRORS,
            pub_payload={
                "error": "Connection pool exhausted - max connections reached",
                "component": "inventory_management_agent",
                "timestamp": "2026-04-02T12:00:00Z",
            },
            predicate=lambda m: "system_error" in json.dumps(m).lower(),
            timeout_s=AGENT_TIMEOUT_S,
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t1_scenario", passed=False, message=str(exc))
        return

    time.sleep(POST_MSG_SLEEP_S)

    passed = True

    incident_ok = msg is not None and "system_error" in json.dumps(msg).lower()
    with lock:
        results.record("t1_incident_created", passed=incident_ok,
                       label="Incident created with type system_error")
    if not incident_ok:
        passed = False

    try:
        email_count = _get_email_count()
        email_ok = email_count >= 1
    except Exception as exc:
        email_ok = False
        email_count = f"ERROR: {exc}"
    with lock:
        results.record("t1_email_sent", passed=email_ok,
                       label=f"Alert email sent (inbox count: {email_count})")
    if not email_ok:
        passed = False

    progress.update_status(test_num, "✅" if passed else "❌", time.monotonic() - start)


def test_2_no_email_for_non_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    test_num = 2
    start = time.monotonic()
    progress.update_status(test_num, "🔄")

    email_before = 0
    try:
        email_before = _get_email_count()
    except Exception:
        pass

    try:
        # Validated order — agent takes no action, no incident, no email
        _run_scenario(
            sub_topic=TOPIC_INCIDENTS_CREATED,
            pub_topic=TOPIC_ORDERS_DECISION,
            pub_payload={
                "order_id": "ORD-500-TEST-VALID-001",
                "item_id": "SKU-MOUSE-042",
                "product_name": "Wireless Mouse",
                "status": "validated",
                "reason": "Sufficient stock available",
                "message": (
                    "Order ORD-500-TEST-VALID-001 has been validated. "
                    "Sufficient stock is available for all items."
                ),
            },
            predicate=lambda m: "inventory_shortage" in json.dumps(m).lower(),
            timeout_s=5,  # Short timeout — no message expected
        )
    except Exception:
        pass  # Timeout is expected

    time.sleep(POST_MSG_SLEEP_S)

    passed = True

    try:
        email_after = _get_email_count()
        no_new_email = email_after <= email_before
    except Exception as exc:
        no_new_email = False
        email_after = f"ERROR: {exc}"
    with lock:
        results.record("t2_no_email", passed=no_new_email,
                       label=f"No alert email sent for validated order (inbox count: {email_after})")
    if not no_new_email:
        passed = False

    progress.update_status(test_num, "✅" if passed else "❌", time.monotonic() - start)


# ── Summary ────────────────────────────────────────────────────────────────
def print_organized_summary(results: ResultCollector):
    W = 62
    thick = "═" * W

    test_labels = {
        1: "Test 1 — Inventory error → alert email sent",
        2: "Test 2 — Validated order → no email sent",
    }
    test_prefixes = {
        1: "t1_",
        2: "t2_",
    }

    print(_bold_cyan(thick))
    print(_bold(f"  Test Results  —  {results.suite_name}"))
    print(_bold_cyan(thick))

    for test_num in range(1, 3):
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
    results = ResultCollector(suite_name="EmailToolIntegration (Parallel)")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Email Tool Integration", "1"))
    print(_s("═" * W, "1", "36"))

    try:
        with QuietSpinner("Resetting database"):
            full_reset(sam_dir=SAM_500_DIR)
    except Exception as exc:
        print(f"\r  ❌ Database reset failed: {exc}")
        results.record("db_reset", passed=False, message=str(exc))
        return results

    test_info = [
        TestInfo(1, "test_1", "Error → alert email sent"),
        TestInfo(2, "test_2", "Validated → no email"),
    ]

    progress = ProgressTable(test_info)
    progress.start()

    lock = threading.Lock()
    test_functions = [
        (test_1_high_severity_incident_sends_email, results, lock, progress),
        (test_2_no_email_for_non_incident, results, lock, progress),
    ]

    start_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
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
