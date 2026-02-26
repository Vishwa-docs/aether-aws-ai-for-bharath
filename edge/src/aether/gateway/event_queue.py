"""
Offline Event Queue — Day 6

SQLite-backed queue that stores AetherEvent objects locally when the
cloud is unreachable. Events are synced in order when connectivity resumes.

Guarantees:
  • Events are never lost (persisted to disk immediately)
  • Ordering is preserved (sorted by timestamp)
  • Critical events are synced first
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from aether.models.schemas import AetherEvent, Severity

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    timestamp   REAL NOT NULL,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    payload     TEXT NOT NULL,
    synced      INTEGER DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_synced_ts
    ON events(synced, severity, timestamp);
"""

# Priority ordering for sync: critical first, then high, medium, low
_SEVERITY_ORDER = {
    Severity.CRITICAL.value: 0,
    Severity.HIGH.value: 1,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 3,
}


class OfflineEventQueue:
    """
    Persistent, priority-aware event queue backed by SQLite.
    """

    def __init__(self, db_path: str = "./edge/data/events.db"):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")  # better concurrent perf
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── Write ─────────────────────────────────────────────────

    def enqueue(self, event: AetherEvent) -> None:
        """Persist an event to the local queue."""
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO events
                   (event_id, timestamp, event_type, severity, payload, synced, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (
                    event.event_id,
                    event.timestamp,
                    event.event_type.value,
                    event.severity.value,
                    event.to_json(),
                    time.time(),
                ),
            )
            self._conn.commit()
            logger.debug("Enqueued event %s (%s)", event.event_id, event.event_type.value)
        except sqlite3.Error:
            logger.exception("Failed to enqueue event %s", event.event_id)
            raise

    # ── Read ──────────────────────────────────────────────────

    def get_unsynced(self, limit: int = 100) -> list[AetherEvent]:
        """
        Return unsynced events, ordered by severity (critical first) then timestamp.
        """
        cursor = self._conn.execute(
            """SELECT payload FROM events
               WHERE synced = 0
               ORDER BY
                   CASE severity
                       WHEN 'critical' THEN 0
                       WHEN 'high'     THEN 1
                       WHEN 'medium'   THEN 2
                       WHEN 'low'      THEN 3
                   END,
                   timestamp ASC
               LIMIT ?""",
            (limit,),
        )
        results: list[AetherEvent] = []
        for (payload_json,) in cursor.fetchall():
            try:
                data = json.loads(payload_json)
                results.append(AetherEvent.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                logger.exception("Corrupt event in queue")
        return results

    def mark_synced(self, event_ids: list[str]) -> int:
        """Mark events as successfully synced. Returns number of rows updated."""
        if not event_ids:
            return 0
        placeholders = ",".join("?" for _ in event_ids)
        cursor = self._conn.execute(
            f"UPDATE events SET synced = 1 WHERE event_id IN ({placeholders})",
            event_ids,
        )
        self._conn.commit()
        return cursor.rowcount

    # ── Maintenance ───────────────────────────────────────────

    def cleanup(self, max_age_days: int = 7) -> int:
        """Delete synced events older than *max_age_days*. Returns rows deleted."""
        cutoff = time.time() - (max_age_days * 86400)
        cursor = self._conn.execute(
            "DELETE FROM events WHERE synced = 1 AND created_at < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def count(self, synced: Optional[bool] = None) -> int:
        """Total events in queue, optionally filtered by sync status."""
        if synced is None:
            row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE synced = ?", (int(synced),)
            ).fetchone()
        return row[0] if row else 0

    # ── Lifecycle ─────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
