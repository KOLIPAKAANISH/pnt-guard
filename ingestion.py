"""
ingestion.py — Signal ingestion module for PNT-Guard.

Handles accepting positioning readings from multiple named sources,
validating them, and storing them in the database.

This module knows nothing about whether the data is real or simulated —
it just validates the format and persists it.
"""

import time

from models import insert_reading, get_db


def ingest_reading(source_id, lat, lon, timestamp=None):
    """
    Ingest a single positioning reading from a named source.

    Args:
        source_id:  String identifier for the signal source (e.g. 'gps_a').
        lat:        Latitude in decimal degrees (-90 to 90).
        lon:        Longitude in decimal degrees (-180 to 180).
        timestamp:  Unix epoch timestamp. Defaults to current time.

    Returns:
        A dict with the stored reading details and its database ID.

    Raises:
        ValueError: If any input is malformed or out of range.
    """
    # --- Input validation ---
    if not source_id or not isinstance(source_id, str):
        raise ValueError("source_id must be a non-empty string")

    if not isinstance(lat, (int, float)):
        raise ValueError(f"lat must be numeric, got {type(lat).__name__}")
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"lat out of range: {lat}")

    if not isinstance(lon, (int, float)):
        raise ValueError(f"lon must be numeric, got {type(lon).__name__}")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"lon out of range: {lon}")

    if timestamp is None:
        timestamp = time.time()
    elif not isinstance(timestamp, (int, float)):
        raise ValueError(f"timestamp must be numeric, got {type(timestamp).__name__}")

    # --- Persist ---
    reading_id = insert_reading(
        source_id=source_id.strip().lower(),
        lat=lat,
        lon=lon,
        timestamp=timestamp,
        status="ok",
    )

    return {
        "id": reading_id,
        "source_id": source_id.strip().lower(),
        "lat": lat,
        "lon": lon,
        "timestamp": timestamp,
        "status": "ok",
    }


def get_source_count():
    """
    Return the number of distinct sources that have sent at least one reading.

    Useful to determine when enough sources are active for fusion.
    """
    conn = get_db()
    row = conn.execute("SELECT COUNT(DISTINCT source_id) as cnt FROM readings").fetchone()
    return row["cnt"]
