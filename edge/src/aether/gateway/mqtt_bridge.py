"""
MQTT Bridge — Day 6

Manages local MQTT communication (sensor mesh) and upstream IoT Core publishing.
Uses paho-mqtt for both local broker interaction and AWS IoT Core connectivity.

Topic scheme:
  Local:    aether/local/{sensor_type}/{sensor_id}
  Upstream: aether/{home_id}/events
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from aether.models.schemas import AetherEvent, SensorReading

logger = logging.getLogger(__name__)


class MQTTBridge:
    """
    Two-sided bridge:
      • Subscribes to the local broker for sensor readings
      • Publishes processed events to the upstream broker (AWS IoT Core or local)
    """

    def __init__(
        self,
        home_id: str = "home-001",
        local_host: str = "localhost",
        local_port: int = 1883,
        upstream_host: str | None = None,
        upstream_port: int = 8883,
        tls_cert_path: str | None = None,
        tls_key_path: str | None = None,
        tls_ca_path: str | None = None,
    ):
        self.home_id = home_id
        self._on_sensor_reading: Optional[Callable[[SensorReading], None]] = None

        # ── Local broker client ───────────────────────────────
        self._local = mqtt.Client(
            client_id=f"gateway-{home_id}-local",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._local_host = local_host
        self._local_port = local_port
        self._local.on_connect = self._on_local_connect
        self._local.on_message = self._on_local_message

        # ── Upstream (IoT Core) client ────────────────────────
        self._upstream: Optional[mqtt.Client] = None
        self._upstream_connected = False
        if upstream_host:
            self._upstream = mqtt.Client(
                client_id=f"gateway-{home_id}-upstream",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )
            if tls_cert_path and tls_key_path and tls_ca_path:
                self._upstream.tls_set(
                    ca_certs=tls_ca_path,
                    certfile=tls_cert_path,
                    keyfile=tls_key_path,
                )
            self._upstream.on_connect = self._on_upstream_connect
            self._upstream.on_disconnect = self._on_upstream_disconnect
            self._upstream_host = upstream_host
            self._upstream_port = upstream_port

    # ── Callbacks ─────────────────────────────────────────────

    def _on_local_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info("Connected to local MQTT broker")
        client.subscribe("aether/local/#")

    def _on_local_message(self, client, userdata, msg):
        """Forward raw MQTT payloads to the registered handler."""
        if self._on_sensor_reading:
            try:
                payload = json.loads(msg.payload.decode())
                # The handler is responsible for parsing into SensorReading
                self._on_sensor_reading(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning("Invalid MQTT payload on %s", msg.topic)

    def _on_upstream_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info("Connected to upstream MQTT broker (IoT Core)")
        self._upstream_connected = True

    def _on_upstream_disconnect(self, client, userdata, flags, reason_code, properties=None):
        logger.warning("Disconnected from upstream MQTT broker")
        self._upstream_connected = False

    # ── Public API ────────────────────────────────────────────

    def on_sensor_reading(self, callback: Callable) -> None:
        """Register handler for incoming sensor readings."""
        self._on_sensor_reading = callback

    def start(self) -> None:
        """Connect to local (and optionally upstream) broker. Non-blocking."""
        try:
            self._local.connect(self._local_host, self._local_port)
            self._local.loop_start()
            logger.info("Local MQTT loop started on %s:%d", self._local_host, self._local_port)
        except ConnectionRefusedError:
            logger.warning(
                "Local MQTT broker not available at %s:%d — running in offline mode",
                self._local_host,
                self._local_port,
            )

        if self._upstream:
            try:
                self._upstream.connect(self._upstream_host, self._upstream_port)
                self._upstream.loop_start()
            except Exception:
                logger.warning("Upstream MQTT broker not reachable — events will queue locally")

    def publish_event(self, event: AetherEvent) -> bool:
        """
        Publish a processed event to the upstream broker.
        Returns True if published, False if offline (event should be queued).
        """
        if not self._upstream or not self._upstream_connected:
            return False

        topic = f"aether/{self.home_id}/events"
        try:
            info = self._upstream.publish(
                topic, event.to_json(), qos=1,
            )
            info.wait_for_publish(timeout=5)
            logger.debug("Published event %s to %s", event.event_id, topic)
            return True
        except Exception:
            logger.exception("Failed to publish event %s", event.event_id)
            return False

    def publish_local(self, topic: str, payload: dict) -> None:
        """Publish to the local sensor mesh (e.g. commands to sentinels)."""
        self._local.publish(topic, json.dumps(payload), qos=0)

    @property
    def is_upstream_connected(self) -> bool:
        return self._upstream_connected

    def stop(self) -> None:
        self._local.loop_stop()
        self._local.disconnect()
        if self._upstream:
            self._upstream.loop_stop()
            self._upstream.disconnect()
