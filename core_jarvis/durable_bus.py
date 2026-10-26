"""Local durable at-least-once events with per-consumer acknowledgement.

SQLite is the paper deployment backend. This is not Redis/NATS or a claim
of exactly-once delivery: consumers must use the proposal id for idempotency.
"""
import json
import sqlite3
import time
import uuid
from pathlib import Path


class DurableEventBus:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY, topic TEXT NOT NULL, timestamp REAL NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS acknowledgements (
              event_id TEXT NOT NULL, consumer TEXT NOT NULL, PRIMARY KEY(event_id, consumer));
        """)
        self.subscribers = {}
        self._recovering = False

    def subscribe(self, topic, handler, consumer=None):
        name = consumer or f"{handler.__module__}.{handler.__qualname__}"
        key = (topic, name)
        if key in self.subscribers:
            raise ValueError("Duplicate durable consumer")
        self.subscribers[key] = handler

    async def publish(self, topic, payload):
        event = {"id": uuid.uuid4().hex, "topic": topic, "timestamp": time.time(), "payload": payload}
        encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
        with self.conn:
            self.conn.execute("INSERT INTO events VALUES (?,?,?,?)",
                              (event["id"], topic, event["timestamp"], encoded))
        await self.recover()
        return event

    async def recover(self):
        if self._recovering:
            return
        self._recovering = True
        try:
            await self._recover_pending()
        finally:
            self._recovering = False

    async def _recover_pending(self):
        # Snapshot prevents nested publications from invalidating the iterator.
        rows = self.conn.execute("SELECT * FROM events ORDER BY timestamp, id").fetchall()
        for event_id, topic, _, payload in rows:
            for (subscription, consumer), handler in list(self.subscribers.items()):
                if subscription not in (topic, "*"):
                    continue
                if self.conn.execute("SELECT 1 FROM acknowledgements WHERE event_id=? AND consumer=?",
                                     (event_id, consumer)).fetchone():
                    continue
                await handler(topic, json.loads(payload))
                with self.conn:
                    self.conn.execute("INSERT OR IGNORE INTO acknowledgements VALUES (?,?)", (event_id, consumer))

    def get_history(self, topic=None, limit=50):
        if topic:
            rows = self.conn.execute("SELECT * FROM events WHERE topic=? ORDER BY timestamp DESC LIMIT ?", (topic, limit))
        else:
            rows = self.conn.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [{"id": r[0], "topic": r[1], "timestamp": r[2], "payload": json.loads(r[3])} for r in reversed(rows.fetchall())]
