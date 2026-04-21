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
import queue
import concurrent.futures
import requests
from dataclasses import dataclass
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.broker import BrokerClient
from framework.result import ResultCollector
from framework.seeder import full_reset


# ── ANSI helpers ───────────────────────────────────────────────────────────
def _s(text: str, *codes: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{';'.join(codes)}m{text}\033[0m"
    return text

def _bold(t): return _s(t, "1")
def _dim(t): return _s(t, "2")
def _cyan(t): return _s(t, "36")
def _green(t): return _s(t, "32")
def _yellow(t): return _s(t, "33")
def _red(t): return _s(t, "31")
def _bold_cyan(t): return _s(t, "1", "36")
def _bold_green(t): return _s(t, "1", "32")
def _bold_red(t): return _s(t, "1", "31")

def _visual_width(s: str) -> int:
    width = 0
    for char in s:
        if ord(char) > 0x1F000:
            width += 2
        else:
            width += 1
    return width


# ── Constants ──────────────────────────────────────────────────────────────
EMAIL_SERVICE_URL       = "http://localhost:3000"
TOPIC_INVENTORY_ERRORS  = "acme/inventory/errors"
TOPIC_INCIDENTS_CREATED = "acme/incidents/created"
TOPIC_ORDERS_DECISION   = "acme/orders/decision"

AGENT_TIMEOUT_S  = 45   # extra headroom for email tool round-trip
POST_MSG_SLEEP_S = 5    # allow send_alert_email tool call to complete

SAM_500_DIR = "/workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins/sam"


# ── Test Info ──────────────────────────────────────────────────────────────
@dataclass
class TestInfo:
    num: int
    name: str
    description: str
    status: str = "⏳"
    elapsed: float = 0.0
    checks_passed: int = 0
    checks_total: int = 0


# ── Progress Table (2-row variant) ─────────────────────────────────────────
class ProgressTable:
    def __init__(self, tests: List[TestInfo]):
        self.tests = {t.num: t for t in tests}
        self.lock = threading.Lock()
        self.update_thread = None
        self.stop_event = threading.Event()
        self.start_time = time.monotonic()
        self._first_print = True

    def start(self):
        self._print_header()
        self._print_table()
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.update_thread:
            self.update_thread.join()

        if sys.stdout.isatty():
            sys.stdout.write("\033[2A")
            sys.stdout.flush()

        with self.lock:
            for i in range(1, 3):
                t = self.tests[i]
                time_str = f"{t.elapsed:5.1f}s" if t.elapsed > 0 else "  -   "
                if t.status == "✅":
                    time_str = _green(time_str)
                elif t.status == "❌":
                    time_str = _red(time_str)
                desc = t.description[:30].ljust(30)
                status_visual_width = _visual_width(t.status)
                status_padding = 8 - status_visual_width
                status_col = f" {t.status}{' ' * status_padding}"
                row = _cyan("│") + f"  {t.num}   │ {desc} │{status_col}│ {time_str} " + _cyan("│")
                if sys.stdout.isatty():
                    sys.stdout.write("\r\033[K" + row + "\n")
                else:
                    sys.stdout.write(row + "\n")

        sys.stdout.write(_cyan("└──────┴────────────────────────────────┴─────────┴─────────┘") + "\n")
        sys.stdout.flush()

    def update_status(self, test_num: int, status: str, elapsed: float = None):
        with self.lock:
            self.tests[test_num].status = status
            if elapsed is not None:
                self.tests[test_num].elapsed = elapsed

    def update_checks(self, test_num: int, passed: int, total: int):
        with self.lock:
            self.tests[test_num].checks_passed = passed
            self.tests[test_num].checks_total = total

    def _update_loop(self):
        while not self.stop_event.is_set():
            time.sleep(0.5)
            with self.lock:
                for t in self.tests.values():
                    if t.status == "🔄":
                        t.elapsed = time.monotonic() - self.start_time
            self._print_table()

    def _print_header(self):
        print()
        print(_cyan("┌───────────────────────────────────────────────────────────┐"))
        print(_cyan("│") + _bold("  Running 2 Tests in Parallel") + " " * 27 + _cyan("│"))
        print(_cyan("├──────┬────────────────────────────────┬─────────┬─────────┤"))
        print(_cyan("│") + _bold(" Test │ Scenario                       │ Status  │ Time    ") + _cyan("│"))
        print(_cyan("├──────┼────────────────────────────────┼─────────┼─────────┤"))

    def _print_table(self):
        with self.lock:
            if not self._first_print and sys.stdout.isatty():
                sys.stdout.write("\033[2A")
                sys.stdout.flush()

            for i in range(1, 3):
                t = self.tests[i]
                time_str = f"{t.elapsed:5.1f}s" if t.elapsed > 0 else "  -   "
                if t.status == "✅":
                    time_str = _green(time_str)
                elif t.status == "❌":
                    time_str = _red(time_str)
                elif t.status == "🔄":
                    time_str = _yellow(time_str)
                desc = t.description[:30].ljust(30)
                status_visual_width = _visual_width(t.status)
                status_padding = 8 - status_visual_width
                status_col = f" {t.status}{' ' * status_padding}"
                row = _cyan("│") + f"  {t.num}   │ {desc} │{status_col}│ {time_str} " + _cyan("│")
                if sys.stdout.isatty():
                    sys.stdout.write("\r\033[K" + row + "\n")
                else:
                    sys.stdout.write(row + "\n")

            sys.stdout.flush()
            self._first_print = False


# ── Helpers ────────────────────────────────────────────────────────────────
def _text(msg: dict) -> str:
    if not msg:
        return ""
    if "_raw" in msg:
        return msg["_raw"].lower()
    return json.dumps(msg).lower()


def _get_email_count() -> int:
    """Return current email count from the mock email service."""
    resp = requests.get(f"{EMAIL_SERVICE_URL}/health", timeout=5)
    resp.raise_for_status()
    return resp.json().get("emailCount", 0)


def _run_scenario(sub_topic, pub_topic, pub_payload, predicate=None, timeout_s=AGENT_TIMEOUT_S):
    result_q = queue.Queue()
    error_q  = queue.Queue()
    ready    = threading.Event()

    def _subscriber():
        try:
            with BrokerClient() as sub:
                msg = sub.wait_for_message(
                    sub_topic, timeout_s=timeout_s,
                    predicate=predicate,
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


# ── Test Functions ─────────────────────────────────────────────────────────
def test_1_high_severity_incident_sends_email(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 1 — Inventory error → system_error incident → alert email sent"""
    test_num = 1
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    msg = None

    try:
        email_count_before = _get_email_count()
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t1_email_service", False, f"Could not reach email service: {exc}", label="Email service reachable")
        return

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
        )
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t1_response_received", False, str(exc), label="Incident created on broker")
        return

    with lock:
        with results.test("t1_response_received", label="High-severity incident created on broker"):
            assert msg is not None

    time.sleep(POST_MSG_SLEEP_S)

    with lock:
        with results.test("t1_email_sent", label="Alert email sent to mock inbox"):
            email_count_after = _get_email_count()
            assert email_count_after > email_count_before, (
                f"No new email sent after high-severity incident "
                f"(inbox count: before={email_count_before}, after={email_count_after}). "
                f"Is send_alert_email configured in the IncidentResponseAgent?"
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 2, 2)


def test_2_no_email_for_non_incident(results: ResultCollector, lock: threading.Lock, progress: ProgressTable):
    """Test 2 — Validated order decision → no alert email sent"""
    test_num = 2
    start = time.monotonic()
    progress.update_status(test_num, "🔄", 0)

    try:
        email_count_before = _get_email_count()
    except Exception as exc:
        progress.update_status(test_num, "❌", time.monotonic() - start)
        with lock:
            results.record("t2_email_service", False, f"Could not reach email service: {exc}", label="Email service reachable")
        return

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

    with lock:
        with results.test("t2_no_email_sent", label="No alert email sent for non-incident event"):
            email_count_after = _get_email_count()
            assert email_count_after == email_count_before, (
                f"Unexpected email sent for validated order "
                f"(inbox count: before={email_count_before}, after={email_count_after}). "
                f"send_alert_email should only be called for high-severity incidents."
            )

    elapsed = time.monotonic() - start
    progress.update_status(test_num, "✅", elapsed)
    progress.update_checks(test_num, 1, 1)


# ── Custom Summary ─────────────────────────────────────────────────────────
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
    results = ResultCollector(suite_name="Email Tool Integration (Module 500)")

    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Email Tool Integration  —  Grading Suite (PARALLEL)", "1"))
    print(_s("═" * W, "1", "36"))

    class QuietSpinner:
        def __init__(self, label):
            self.label = label
            self.start_time = time.monotonic()
        def __enter__(self):
            print(f"  ⏳ {self.label}...", end="", flush=True)
            return self
        def __exit__(self, *_):
            elapsed = time.monotonic() - self.start_time
            print(f"\r  ✅ {self.label} ({elapsed:.1f}s)")

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
