"""
broker.py — Solace PubSub+ publish/subscribe helpers for the tests framework.

Wraps the solace-pubsubplus Python SDK to provide:
  - BrokerClient: a context-manager-friendly connection to the local SAM broker
  - publish(topic, payload):  fire-and-forget direct publish
  - wait_for_message(topic, timeout_s): blocking subscribe-and-wait

Connection defaults match the SAM devcontainer broker (localhost:8008 SMF /
ws://localhost:8008) — override via env vars or by passing broker_props directly.

Environment variables (all optional, defaults shown):
  SOLACE_BROKER_URL       tcp://localhost:55555   (SMF TCP)
  SOLACE_BROKER_VPN       default
  SOLACE_BROKER_USERNAME  default
  SOLACE_BROKER_PASSWORD  default
"""

import json
import os
import time
from contextlib import contextmanager
from typing import Any, Optional

from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.topic import Topic
from solace.messaging.resources.topic_subscription import TopicSubscription
from solace.messaging.errors.pubsubplus_client_error import PubSubPlusClientError


# ---------------------------------------------------------------------------
# Default connection properties — match the SAM devcontainer broker
# ---------------------------------------------------------------------------
def _default_props() -> dict:
    return {
        "solace.messaging.transport.host": os.environ.get(
            "SOLACE_BROKER_URL", "ws://localhost:8008"
        ),
        "solace.messaging.service.vpn-name": os.environ.get(
            "SOLACE_BROKER_VPN", "default"
        ),
        "solace.messaging.authentication.scheme.basic.username": os.environ.get(
            "SOLACE_BROKER_USERNAME", "default"
        ),
        "solace.messaging.authentication.scheme.basic.password": os.environ.get(
            "SOLACE_BROKER_PASSWORD", "default"
        ),
    }


# ---------------------------------------------------------------------------
# BrokerClient
# ---------------------------------------------------------------------------
class BrokerClient:
    """
    A thin wrapper around MessagingService that manages a single connection.

    Usage (preferred — automatic cleanup):
        with BrokerClient() as broker:
            broker.publish("acme/orders/created", {"order_id": "ORD-001"})
            msg = broker.wait_for_message("acme/orders/fulfillment-result/>", timeout_s=15)

    Or manually:
        broker = BrokerClient()
        broker.connect()
        ...
        broker.disconnect()
    """

    def __init__(self, broker_props: Optional[dict] = None):
        self._props = broker_props or _default_props()
        self._service: Optional[MessagingService] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> "BrokerClient":
        self._service = (
            MessagingService.builder()
            .from_properties(self._props)
            .build()
            .connect()
        )
        return self

    def disconnect(self):
        if self._service and self._service.is_connected:
            self._service.disconnect()
            self._service = None

    def __enter__(self) -> "BrokerClient":
        return self.connect()

    def __exit__(self, *_):
        self.disconnect()

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------
    def publish(self, topic: str, payload: Any):
        """
        Publish a direct message to *topic*.

        payload can be:
          - a dict / list  → serialised to JSON string automatically
          - a str          → sent as-is
          - bytes          → sent as-is
        """
        self._ensure_connected()

        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)

        publisher = (
            self._service.create_direct_message_publisher_builder()
            .on_back_pressure_wait(1000)
            .build()
        )
        publisher.start()
        try:
            publisher.publish(payload, Topic.of(topic))
        finally:
            publisher.terminate()

    # ------------------------------------------------------------------
    # Subscribe / wait
    # ------------------------------------------------------------------
    def wait_for_message(
        self,
        topic_expression: str,
        timeout_s: float = 15.0,
        predicate=None,
        on_ready=None,
    ) -> Optional[dict]:
        """
        Subscribe to *topic_expression* and block until a matching message
        arrives or *timeout_s* elapses.

        topic_expression supports Solace wildcards:
          >   matches one or more levels   (e.g. "acme/orders/>")
          *   matches exactly one level    (e.g. "acme/orders/fulfillment-result/*")

        predicate: optional callable(dict) -> bool
            If supplied, messages that don't satisfy the predicate are skipped
            (the function keeps waiting until timeout).

        Returns:
            Parsed JSON dict of the message payload, or None on timeout.

        Raises:
            PubSubPlusClientError on broker errors.
        """
        self._ensure_connected()

        subscription = TopicSubscription.of(topic_expression)
        receiver = (
            self._service.create_direct_message_receiver_builder()
            .with_subscriptions([subscription])
            .on_back_pressure_drop_oldest(100)
            .build()
        )
        receiver.start()
        if on_ready:
            on_ready()

        deadline = time.monotonic() + timeout_s
        result = None

        try:
            while time.monotonic() < deadline:
                remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                if remaining_ms == 0:
                    break

                inbound = receiver.receive_message(timeout=remaining_ms)
                if inbound is None:
                    break  # timed out

                raw = inbound.get_payload_as_string()
                if raw is None:
                    # Try bytes
                    raw_bytes = inbound.get_payload_as_bytes()
                    if raw_bytes:
                        raw = raw_bytes.decode("utf-8", errors="replace")

                if raw is None:
                    continue

                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {"_raw": raw}

                # json.loads can return str/int/list for valid JSON scalars —
                # we need a dict so we can attach _topic below.
                if not isinstance(parsed, dict):
                    parsed = {"_raw": raw}

                # Attach the actual topic so tests can inspect it
                parsed["_topic"] = inbound.get_destination_name()

                if predicate is None or predicate(parsed):
                    result = parsed
                    break
                # else: skip this message and keep waiting

        finally:
            receiver.terminate()

        return result

    # ------------------------------------------------------------------
    # Drain
    # ------------------------------------------------------------------
    def drain_messages(
        self,
        topic_expressions: list,
        idle_s: float = 3.0,
        max_wait_s: float = 30.0,
    ) -> int:
        """
        Subscribe to all *topic_expressions* simultaneously and discard every
        message that arrives until *idle_s* seconds pass with no new message
        or *max_wait_s* elapses.  Returns the number of messages drained.

        Used by full_reset() to consume stale in-flight pipeline messages
        left over from a previous test suite before the next one starts.
        """
        self._ensure_connected()

        subscriptions = [TopicSubscription.of(t) for t in topic_expressions]
        receiver = (
            self._service.create_direct_message_receiver_builder()
            .with_subscriptions(subscriptions)
            .on_back_pressure_drop_oldest(100)
            .build()
        )
        receiver.start()
        drained = 0
        try:
            deadline = time.monotonic() + max_wait_s
            while time.monotonic() < deadline:
                remaining_ms = int(min(idle_s, deadline - time.monotonic()) * 1000)
                if remaining_ms <= 0:
                    break
                inbound = receiver.receive_message(timeout=remaining_ms)
                if inbound is None:
                    break  # idle_s of silence — pipeline is quiet
                drained += 1
        finally:
            receiver.terminate()
        return drained

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_connected(self):
        if self._service is None or not self._service.is_connected:
            raise RuntimeError(
                "BrokerClient is not connected. "
                "Call connect() or use as a context manager."
            )


# ---------------------------------------------------------------------------
# Convenience context manager for one-shot operations
# ---------------------------------------------------------------------------
@contextmanager
def broker_session(broker_props: Optional[dict] = None):
    """
    Yields a connected BrokerClient and disconnects on exit.

    with broker_session() as broker:
        broker.publish(...)
        msg = broker.wait_for_message(...)
    """
    client = BrokerClient(broker_props)
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()