"""
Edge Gateway Orchestrator — Day 6

The main runtime loop that ties together:
  • MQTT bridge (local sensor mesh + upstream IoT Core)
  • Privacy filter
  • Offline event queue
  • Fusion engine (Day 7)

Runs as a long-lived process on the Edge Gateway device.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv

from aether.models.schemas import AetherEvent
from aether.gateway.mqtt_bridge import MQTTBridge
from aether.gateway.privacy_filter import PrivacyFilter, PrivacySettings, PrivacyLevel
from aether.gateway.event_queue import OfflineEventQueue

logger = logging.getLogger(__name__)

load_dotenv()


class EdgeGateway:
    """
    Central coordinator for the edge layer.

    Lifecycle:
      gw = EdgeGateway()
      gw.start()            # connect MQTT, open queue
      gw.process_event(ev)  # called by fusion engine
      gw.stop()             # graceful shutdown
    """

    def __init__(
        self,
        home_id: str | None = None,
        mqtt_bridge: MQTTBridge | None = None,
        privacy_filter: PrivacyFilter | None = None,
        event_queue: OfflineEventQueue | None = None,
    ):
        self.home_id = home_id or os.getenv("EDGE_HOME_ID", "home-001")

        self.mqtt = mqtt_bridge or MQTTBridge(
            home_id=self.home_id,
            local_host=os.getenv("MQTT_BROKER_HOST", "localhost"),
            local_port=int(os.getenv("MQTT_BROKER_PORT", "1883")),
            upstream_host=os.getenv("IOT_ENDPOINT"),
            tls_cert_path=os.getenv("IOT_CERT_PATH"),
            tls_key_path=os.getenv("IOT_KEY_PATH"),
            tls_ca_path=os.getenv("IOT_ROOT_CA_PATH"),
        )

        self.privacy = privacy_filter or PrivacyFilter(
            PrivacySettings(level=PrivacyLevel.STANDARD)
        )

        self.queue = event_queue or OfflineEventQueue(
            db_path=os.getenv("EDGE_OFFLINE_DB_PATH", "./edge/data/events.db")
        )

        self._running = False
        self._events_processed = 0
        self._events_published = 0
        self._events_queued = 0

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Connect MQTT and begin processing."""
        logger.info("Starting Edge Gateway for home %s", self.home_id)
        self.mqtt.start()
        self._running = True

    def stop(self) -> None:
        """Graceful shutdown."""
        logger.info(
            "Stopping Edge Gateway — processed=%d published=%d queued=%d",
            self._events_processed,
            self._events_published,
            self._events_queued,
        )
        self._running = False
        self.mqtt.stop()
        self.queue.close()

    # ── Event processing ──────────────────────────────────────

    def process_event(self, event: AetherEvent) -> None:
        """
        Apply privacy filter, attempt cloud publish, fall back to local queue.
        Called by the fusion engine whenever a new event is detected.
        """
        self._events_processed += 1

        # 1. Privacy filter
        filtered = self.privacy.filter_event(event)

        # 2. Always persist locally first (crash safety)
        self.queue.enqueue(filtered)

        # 3. Attempt upstream publish
        if self.mqtt.is_upstream_connected:
            published = self.mqtt.publish_event(filtered)
            if published:
                self.queue.mark_synced([filtered.event_id])
                self._events_published += 1
                logger.info(
                    "Event %s published to cloud (%s, confidence=%.2f)",
                    filtered.event_id,
                    filtered.event_type.value,
                    filtered.confidence,
                )
                return

        # 4. Offline — event stays in queue
        self._events_queued += 1
        logger.info(
            "Event %s queued locally (offline) — queue size: %d",
            filtered.event_id,
            self.queue.count(synced=False),
        )

    # ── Sync ──────────────────────────────────────────────────

    def sync_queued_events(self, batch_size: int = 100) -> int:
        """
        Attempt to sync queued events to the cloud.
        Returns number of events successfully synced.
        """
        if not self.mqtt.is_upstream_connected:
            return 0

        unsynced = self.queue.get_unsynced(limit=batch_size)
        synced_ids: list[str] = []

        for event in unsynced:
            if self.mqtt.publish_event(event):
                synced_ids.append(event.event_id)
            else:
                break  # connection lost mid-batch

        if synced_ids:
            self.queue.mark_synced(synced_ids)
            self._events_published += len(synced_ids)
            logger.info("Synced %d queued events to cloud", len(synced_ids))

        return len(synced_ids)

    # ── Stats ─────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        return {
            "home_id": self.home_id,
            "running": self._running,
            "events_processed": self._events_processed,
            "events_published": self._events_published,
            "events_queued": self._events_queued,
            "queue_unsynced": self.queue.count(synced=False),
            "queue_total": self.queue.count(),
            "upstream_connected": self.mqtt.is_upstream_connected,
        }
