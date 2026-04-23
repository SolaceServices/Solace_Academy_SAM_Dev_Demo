"""
result.py — Test result collection, pretty printing, and HMAC-signed payload
            generation for submission to the grading backend.

Usage:
    results = ResultCollector()

    with results.test("order_validated_topic"):
        assert msg is not None, "No message received on validated topic"

    with results.test("order_status_in_db"):
        assert_order_status("ORD-NEW-001", "validated")

    print(results.summary())
    payload = results.signed_payload(student_email="alice@example.com")
"""

import hashlib
import hmac
import json
import os
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional


# ── ANSI colour helpers ──────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    """Wrap text in ANSI escape codes when stdout is a tty."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

_bold       = lambda t: _c("1",    t)
_dim        = lambda t: _c("2",    t)
_red        = lambda t: _c("31",   t)
_cyan       = lambda t: _c("36",   t)
_bold_green = lambda t: _c("1;32", t)
_bold_red   = lambda t: _c("1;31", t)
_bold_cyan  = lambda t: _c("1;36", t)


# ---------------------------------------------------------------------------
# Individual test result
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    duration_ms: float = 0.0
    label: str = ""        # human-readable display name (falls back to name)
    is_section: bool = False  # True for group-header entries, not real tests


# ---------------------------------------------------------------------------
# ResultCollector
# ---------------------------------------------------------------------------
class ResultCollector:
    """
    Collects pass/fail results for a suite of named tests.

    Each test is a context manager block; any exception = fail.
    """

    def __init__(self, suite_name: str = ""):
        self.suite_name = suite_name
        self._results: list[TestResult] = []

    # ------------------------------------------------------------------
    # Context-manager test runner
    # ------------------------------------------------------------------
    def section(self, title: str):
        """Add a named section header to group related tests in the summary."""
        self._results.append(
            TestResult(name="__section__", passed=True, label=title, is_section=True)
        )

    @contextmanager
    def test(self, name: str, label: str = ""):
        """
        Run a named test. Catches all exceptions and records pass/fail.

        with results.test("my_check", label="Human-readable description"):
            assert something == expected
        """
        start = time.monotonic()
        try:
            yield
            duration_ms = (time.monotonic() - start) * 1000
            self._results.append(
                TestResult(name=name, passed=True, duration_ms=duration_ms, label=label)
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            msg = f"{type(exc).__name__}: {exc}"
            self._results.append(
                TestResult(
                    name=name, passed=False, message=msg, duration_ms=duration_ms, label=label
                )
            )

    # ------------------------------------------------------------------
    # Manual record (useful when you handle exceptions yourself)
    # ------------------------------------------------------------------
    def record(self, name: str, passed: bool, message: str = "", label: str = ""):
        self._results.append(TestResult(name=name, passed=passed, message=message, label=label))

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def _real_results(self):
        return [r for r in self._results if not r.is_section]

    @property
    def passed(self) -> int:
        return sum(1 for r in self._real_results() if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self._real_results() if not r.passed)

    @property
    def total(self) -> int:
        return len(self._real_results())

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.failed == 0

    def summary(self) -> str:
        """Return a human-readable test summary."""
        W     = 62
        bar   = "─" * W
        thick = "═" * W
        lines = []

        # ── Header ──────────────────────────────────────────────────────────
        suite_label = f"  —  {self.suite_name}" if self.suite_name else ""
        lines.append(_bold_cyan(thick))
        lines.append(_bold(f"  Test Results{suite_label}"))
        lines.append(_bold_cyan(thick))

        # ── Per-test results ─────────────────────────────────────────────────
        for r in self._results:
            if r.is_section:
                lines.append("")
                lines.append(_bold(f"  {r.label}"))
                continue
            display = r.label if r.label else r.name
            if r.passed:
                lines.append(f"    ✅  {display}")
            else:
                lines.append(f"    ❌  {_bold(display)}")
                if r.message:
                    for line in r.message.splitlines():
                        lines.append(_red(f"         {line}"))

        # ── Footer ───────────────────────────────────────────────────────────
        lines.append("")
        if self.all_passed:
            lines.append(_bold_green(thick))
            lines.append(_bold_green(
                f"  🎉  PASSED  —  {self.passed}/{self.total} checks passed"
            ))
            lines.append(_bold_green(thick))
        else:
            lines.append(_bold_red(bar))
            lines.append(_bold_red(
                f"  ✗   FAILED  —  {self.passed}/{self.total} checks passed"
                f"  ({self.failed} failed)"
            ))
            lines.append(_bold_red(bar))

        return "\n".join(lines)

    def as_dict(self) -> dict:
        """Return results as a plain dict (JSON-serialisable)."""
        return {
            "suite": self.suite_name,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "all_passed": self.all_passed,
            "tests": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "duration_ms": round(r.duration_ms, 1),
                }
                for r in self._real_results()
            ],
        }

    # ------------------------------------------------------------------
    # HMAC-signed payload for grading backend submission
    # ------------------------------------------------------------------
    def signed_payload(
        self,
        student_email: str,
        course_id: str = "",
        secret_key: Optional[str] = None,
    ) -> dict:
        """
        Return a dict containing the results and an HMAC-SHA256 signature.

        The grading backend verifies the signature using the same shared secret
        to confirm the payload was produced by the legitimate test harness and
        not tampered with.

        secret_key defaults to the GRADING_HMAC_SECRET env var.
        The signature covers: email + course_id + timestamp + results JSON.
        """
        key = secret_key or os.environ.get("GRADING_HMAC_SECRET", "dev-secret")
        timestamp = int(time.time())
        results_json = json.dumps(self.as_dict(), sort_keys=True)

        message = f"{student_email}|{course_id}|{timestamp}|{results_json}"
        sig = hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "student_email": student_email,
            "course_id": course_id,
            "timestamp": timestamp,
            "results": self.as_dict(),
            "signature": sig,
        }
