"""
models.py — Database schema and helpers for the PNT-Guard engine.

Defines two tables:
  - readings: raw positioning data from all sources
  - events:   flag/fusion history log for auditing and history queries

Uses SQLite via Python's built-in sqlite3 module. No ORM needed.
"""

import sqlite3
import os
import threading

DB_PATH = os.environ.get("PNT_GUARD_DB", "pnt_guard.db")

_local = threading.local()


def get_db():
    """
    Return a thread-local SQLite connection.

    Flask can serve requests concurrently in dev mode, so each thread
    gets its own connection to avoid 'database is locked' errors.
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db():
    """
    Create tables if they don't exist.

    Called once at app startup. Idempotent — safe to call repeatedly.
    """
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id   TEXT    NOT NULL,
            lat         REAL    NOT NULL,
            lon         REAL    NOT NULL,
            timestamp   REAL    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'ok'
        );

        CREATE INDEX IF NOT EXISTS idx_readings_source_ts
            ON readings(source_id, timestamp DESC);

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL    NOT NULL,
            event_type  TEXT    NOT NULL,
            details     TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_ts
            ON events(timestamp DESC);
    """)
    conn.commit()


def insert_reading(source_id, lat, lon, timestamp, status="ok"):
    """
    Insert a raw positioning reading into the readings table.

    Args:
        source_id:  Name/identifier of the signal source.
        lat:        Latitude in decimal degrees.
        lon:        Longitude in decimal degrees.
        timestamp:  Unix epoch timestamp (float).
        status:     One of 'ok', 'anomalous', or 'superseded'.

    Returns:
        The auto-generated row ID.
    """
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO readings (source_id, lat, lon, timestamp, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, lat, lon, timestamp, status),
    )
    conn.commit()
    return cur.lastrowid


def mark_reading_anomalous(reading_id):
    """Mark a reading as anomalous by its row ID."""
    conn = get_db()
    conn.execute("UPDATE readings SET status = 'anomalous' WHERE id = ?", (reading_id,))
    conn.commit()


def get_latest_readings():
    """
    Return the most recent reading from each source.

    Uses a window function to avoid N+1 queries. Returns a list of dicts
    with keys: id, source_id, lat, lon, timestamp, status.
    """
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, source_id, lat, lon, timestamp, status
        FROM readings
        WHERE id IN (
            SELECT MAX(id) FROM readings GROUP BY source_id
        )
        ORDER BY timestamp DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_previous_reading(source_id, before_timestamp):
    """
    Return the most recent reading for a source that occurred before a given timestamp.

    Used by the velocity check in anomaly detection to compare consecutive readings.
    Returns a dict or None if no prior reading exists.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id, source_id, lat, lon, timestamp, status "
        "FROM readings "
        "WHERE source_id = ? AND timestamp < ? "
        "ORDER BY timestamp DESC LIMIT 1",
        (source_id, before_timestamp),
    ).fetchone()
    return dict(row) if row else None


def insert_event(event_type, details, timestamp=None):
    """
    Log an event (flag or fusion result) to the events table.

    Args:
        event_type: Category string, e.g. 'distance_flag', 'fusion_result'.
        details:    JSON-serializable dict with event-specific info.
        timestamp:  Unix epoch. Defaults to current time if not provided.
    """
    import time
    import json

    if timestamp is None:
        timestamp = time.time()
    conn = get_db()
    conn.execute(
        "INSERT INTO events (timestamp, event_type, details) VALUES (?, ?, ?)",
        (timestamp, event_type, json.dumps(details)),
    )
    conn.commit()


def get_recent_events(minutes=5):
    """
    Return events from the last N minutes, newest first.

    Args:
        minutes: How many minutes of history to retrieve.

    Returns:
        List of dicts with keys: id, timestamp, event_type, details (parsed JSON).
    """
    import json
    import time

    conn = get_db()
    cutoff = time.time() - (minutes * 60)
    rows = conn.execute(
        "SELECT id, timestamp, event_type, details FROM events "
        "WHERE timestamp >= ? ORDER BY timestamp DESC",
        (cutoff,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["details"] = json.loads(d["details"])
        results.append(d)
    return results
