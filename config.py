"""
config.py — Central configuration for the PNT-Guard engine.

All tunable thresholds and settings live here. Edit this file to adjust
engine behavior without touching core logic.

Environment variables override these defaults when set.
"""

import os

# ---------------------------------------------------------------------------
# Anomaly Detection Thresholds
# ---------------------------------------------------------------------------

# Maximum allowed distance (meters) a source can deviate from the median
# position before being flagged. Default: 500 m.
DISTANCE_THRESHOLD_M = float(os.environ.get("PNT_DISTANCE_THRESHOLD_M", 500))

# Maximum allowed speed (meters/second) between consecutive readings from
# the same source. Readings implying faster speed are flagged.
# Default: 1000 m/s (~Mach 3, well above any civilian vehicle/aircraft).
VELOCITY_THRESHOLD_MS = float(os.environ.get("PNT_VELOCITY_THRESHOLD_MS", 1000))

# ---------------------------------------------------------------------------
# Dashboard / Polling
# ---------------------------------------------------------------------------

# How often the dashboard polls the API (milliseconds in JS, but this
# value is referenced in docs/tests). Default: 3 seconds.
DASHBOARD_POLL_INTERVAL_S = int(os.environ.get("PNT_POLL_INTERVAL_S", 3))

# How many minutes of event history the dashboard fetches. Default: 5.
DASHBOARD_HISTORY_MINUTES = int(os.environ.get("PNT_HISTORY_MINUTES", 5))

# ---------------------------------------------------------------------------
# Signal Simulator
# ---------------------------------------------------------------------------

# URL the simulator posts readings to.
SIMULATOR_URL = os.environ.get("PNT_SIMULATOR_URL", "http://localhost:5000/ingest")

# Seconds between simulator reading batches.
SIMULATOR_INTERVAL_S = float(os.environ.get("PNT_SIMULATOR_INTERVAL_S", 3))

# Probability (0.0-1.0) that any given simulated reading is an anomaly.
# Used for testing detection. Default: 0.05 (5%).
SIMULATOR_ANOMALY_RATE = float(os.environ.get("PNT_SIMULATOR_ANOMALY_RATE", 0.05))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Path to the SQLite database file.
DB_PATH = os.environ.get("PNT_GUARD_DB", "pnt_guard.db")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

SERVER_HOST = os.environ.get("PNT_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PNT_SERVER_PORT", 5000))
