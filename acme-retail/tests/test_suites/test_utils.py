"""
test_utils.py — Shared utilities for parallel tests test suites.

Imported by all 5 *_parallel.py test files.

Provides:
  ANSI helpers: _s (base), _bold, _dim, _cyan, _green, _yellow, _red,
                _bold_cyan, _bold_green, _bold_red
  _visual_width()
  TestInfo (dataclass)
  ProgressTable (parameterized by n_tests, derived from the tests list)
  QuietSpinner
  _run_scenario()
  _text()
"""

import json
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import List

# Ensure tests/ is on sys.path so framework.* imports resolve regardless of
# how this module is loaded (e.g. directly or via the parallel test files).
_tests_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from framework.broker import BrokerClient


# ── ANSI helpers ───────────────────────────────────────────────────────────
def _s(text: str, *codes: str) -> str:
    """Style text with ANSI codes if stdout is a TTY."""
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
    """Calculate visual width accounting for wide emoji characters."""
    width = 0
    for char in s:
        if ord(char) > 0x1F000:
            width += 2
        else:
            width += 1
    return width


# ── Test metadata dataclass ────────────────────────────────────────────────
@dataclass
class TestInfo:
    num: int
    name: str
    description: str
    status: str = "⏳"  # ⏳ Pending, 🔄 Running, ✅ Done, ❌ Failed
    elapsed: float = 0.0
    checks_passed: int = 0
    checks_total: int = 0


# ── Progress Table ─────────────────────────────────────────────────────────
class ProgressTable:
    """Live updating progress table for parallel test execution."""

    def __init__(self, tests: List[TestInfo]):
        self.tests = {t.num: t for t in tests}
        self.n_tests = max(t.num for t in tests)
        self.lock = threading.Lock()
        self.update_thread = None
        self.stop_event = threading.Event()
        self.start_time = time.monotonic()
        self._first_print = True

    def start(self):
        """Start the live display."""
        self._print_header()
        self._print_table()
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def stop(self):
        """Stop the live display and print final table with bottom border."""
        self.stop_event.set()
        if self.update_thread:
            self.update_thread.join()

        if sys.stdout.isatty():
            sys.stdout.write(f"\033[{self.n_tests}A")
            sys.stdout.flush()

        with self.lock:
            for i in range(1, self.n_tests + 1):
                t = self.tests[i]
                time_str = f"{int(t.elapsed):5d}s" if t.elapsed > 0 else "  -   "
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
        """Update test status."""
        with self.lock:
            self.tests[test_num].status = status
            if elapsed is not None:
                self.tests[test_num].elapsed = elapsed

    def update_checks(self, test_num: int, passed: int, total: int):
        """Update check counts."""
        with self.lock:
            self.tests[test_num].checks_passed = passed
            self.tests[test_num].checks_total = total

    def _update_loop(self):
        """Update the table every 1s."""
        while not self.stop_event.is_set():
            time.sleep(1.0)
            with self.lock:
                for t in self.tests.values():
                    if t.status == "🔄":
                        t.elapsed = time.monotonic() - self.start_time
            self._print_table()

    def _print_header(self):
        """Print the table header once."""
        print()
        print(_cyan("┌───────────────────────────────────────────────────────────┐"))
        print(_cyan("│") + _bold(f"  Running {self.n_tests} Tests in Parallel") + " " * 27 + _cyan("   │"))
        print(_cyan("├──────┬────────────────────────────────┬─────────┬─────────┤"))
        print(_cyan("│") + _bold(" Test │ Scenario                       │ Status  │ Time    ") + _cyan("│"))
        print(_cyan("├──────┼────────────────────────────────┼─────────┼─────────┤"))

    def _print_table(self):
        """Print or update the table rows."""
        with self.lock:
            if not self._first_print and sys.stdout.isatty():
                sys.stdout.write(f"\033[{self.n_tests}A")
                sys.stdout.flush()

            for i in range(1, self.n_tests + 1):
                t = self.tests[i]

                time_str = f"{int(t.elapsed):5d}s" if t.elapsed > 0 else "  -   "
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


# ── QuietSpinner ───────────────────────────────────────────────────────────
class QuietSpinner:
    """Simple inline spinner for the database reset step."""

    def __init__(self, label):
        self.label = label
        self.start_time = time.monotonic()

    def __enter__(self):
        print(f"  ⏳ {self.label}...", end="", flush=True)
        return self

    def __exit__(self, *_):
        elapsed = time.monotonic() - self.start_time
        print(f"\r  ✅ {self.label} ({elapsed:.1f}s)")


# ── Shared scenario runner ─────────────────────────────────────────────────
def _run_scenario(sub_topic, pub_topic, pub_payload, predicate=None, timeout_s=30):
    """Publish an event and wait for a response on the broker."""
    result_q = queue.Queue()
    error_q = queue.Queue()
    ready = threading.Event()

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


# ── Text helper ────────────────────────────────────────────────────────────
def _text(msg: dict) -> str:
    """Extract lowercase text from a broker message dict."""
    if not msg:
        return ""
    if "_raw" in msg:
        return msg["_raw"].lower()
    return json.dumps(msg).lower()
