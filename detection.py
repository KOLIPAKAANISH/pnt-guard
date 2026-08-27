"""
detection.py — Anomaly detection module for PNT-Guard.

Implements rule-based anomaly detection on positioning data:
  1. Distance deviation — flags a source if it's more than a threshold
     (default 500 m) from the median position of the others.
  2. Velocity check — flags a source if the implied speed between two
     consecutive readings exceeds a threshold (default 1000 m/s ≈ Mach 3).

No ML libraries are used. Rules are deterministic and auditable.
"""

import math
import time

import config
from models import (
    get_latest_readings,
    get_previous_reading,
    mark_reading_anomalous,
    insert_event,
)


def haversine_meters(lat1, lon1, lat2, lon2):
    """
    Compute the great-circle distance between two points on Earth in meters.

    Uses the Haversine formula — accurate enough for short-to-medium ranges
    where positional anomalies are checked.

    Args:
        lat1, lon1: First point in decimal degrees.
        lat2, lon2: Second point in decimal degrees.

    Returns:
        Distance in meters.
    """
    R = 6_371_000  # Earth mean radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_median_position(readings):
    """
    Compute the median lat/lon from a list of readings.

    Median is chosen over mean because it's robust to outliers —
    exactly what we want when some sources might be anomalous.

    Args:
        readings: List of dicts with 'lat' and 'lon' keys.

    Returns:
        Tuple of (median_lat, median_lon).
    """
    lats = sorted(r["lat"] for r in readings)
    lons = sorted(r["lon"] for r in readings)
    n = len(lats)
    mid = n // 2
    if n % 2 == 0:
        median_lat = (lats[mid - 1] + lats[mid]) / 2
        median_lon = (lons[mid - 1] + lons[mid]) / 2
    else:
        median_lat = lats[mid]
        median_lon = lons[mid]
    return median_lat, median_lon


def check_distance_deviation(readings, threshold_m=500):
    """
    Flag sources whose position deviates more than threshold_m from the median.

    Args:
        readings:     List of dicts with 'id', 'source_id', 'lat', 'lon'.
        threshold_m:  Maximum allowed deviation in meters.

    Returns:
        Set of source_ids that are flagged.
    """
    if len(readings) < 2:
        # Can't compute deviation with fewer than 2 sources
        return set()

    med_lat, med_lon = compute_median_position(readings)
    flagged = set()

    for r in readings:
        dist = haversine_meters(r["lat"], r["lon"], med_lat, med_lon)
        if dist > threshold_m:
            flagged.add(r["source_id"])

    return flagged


def check_velocity(readings, max_speed_ms=1000):
    """
    Flag sources that imply impossible speed between consecutive readings.

    Compares each source's current reading against its previous reading
    to compute implied speed. If the speed exceeds max_speed_ms, the
    source is flagged.

    Args:
        readings:     List of dicts with 'source_id', 'lat', 'lon', 'timestamp'.
        max_speed_ms: Maximum allowed speed in meters per second.

    Returns:
        Set of source_ids that are flagged.
    """
    flagged = set()

    for r in readings:
        prev = get_previous_reading(r["source_id"], r["timestamp"])
        if prev is None:
            continue  # First reading for this source — can't check velocity

        dt = r["timestamp"] - prev["timestamp"]
        if dt <= 0:
            continue  # Skip if timestamps are out of order or identical

        dist = haversine_meters(prev["lat"], prev["lon"], r["lat"], r["lon"])
        speed = dist / dt

        if speed > max_speed_ms:
            flagged.add(r["source_id"])

    return flagged


def detect_anomalies(distance_threshold_m=None, velocity_threshold_ms=None):
    """
    Run all anomaly checks on the latest readings and update the database.

    This is the main entry point for the detection module. It:
      1. Fetches the latest reading from each source.
      2. Runs distance deviation and velocity checks.
      3. Marks anomalous readings in the DB.
      4. Logs events for audit/history.

    Args:
        distance_threshold_m:  Max deviation from median in meters.
        velocity_threshold_ms: Max implied speed in m/s.

    Returns:
        A dict mapping source_id -> list of flagged reasons.
    """
    if distance_threshold_m is None:
        distance_threshold_m = config.DISTANCE_THRESHOLD_M
    if velocity_threshold_ms is None:
        velocity_threshold_ms = config.VELOCITY_THRESHOLD_MS

    readings = get_latest_readings()
    if not readings:
        return {}

    # Run both checks independently — a source can be flagged for multiple reasons
    distance_flags = check_distance_deviation(readings, distance_threshold_m)
    velocity_flags = check_velocity(readings, velocity_threshold_ms)

    # Merge flags
    flagged_map = {}
    now = time.time()

    for r in readings:
        reasons = []
        if r["source_id"] in distance_flags:
            reasons.append("distance_deviation")
        if r["source_id"] in velocity_flags:
            reasons.append("velocity_violation")

        if reasons:
            flagged_map[r["source_id"]] = reasons
            mark_reading_anomalous(r["id"])

            # Log the flag event
            insert_event(
                event_type="anomaly_flag",
                details={
                    "reading_id": r["id"],
                    "source_id": r["source_id"],
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "reasons": reasons,
                },
                timestamp=now,
            )
        else:
            flagged_map[r["source_id"]] = []

    return flagged_map
