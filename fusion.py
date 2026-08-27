"""
fusion.py — Position fusion module for PNT-Guard.

Computes a single trusted/fused position from multiple non-anomalous
sources using the median method. The median is chosen because it's
resistant to a single outlier — but since anomalous sources are already
filtered out before fusion, it provides a robust central estimate.

If ALL sources are flagged as anomalous, the module returns a sentinel
"no reliable position" instead of producing a false fused value.
"""

import time

from models import get_latest_readings, insert_event
from detection import compute_median_position


def fuse_position():
    """
    Compute the fused (trusted) position from non-anomalous readings.

    Steps:
      1. Fetch the latest reading from each source.
      2. Filter out any with status == 'anomalous'.
      3. If no valid readings remain, return an error status.
      4. Otherwise, compute the median lat/lon of the valid readings.

    Why median over weighted average?
      Weighted average requires knowing each source's reliability a priori,
      which we don't have. The median is a simple, robust estimator that
      handles up to 50% outlier contamination gracefully.

    Returns:
        A dict with:
          - 'status':      'ok' or 'no_reliable_position'
          - 'lat':         Fused latitude (if status == 'ok')
          - 'lon':         Fused longitude (if status == 'ok')
          - 'sources_used': List of source_ids that contributed
          - 'sources_flagged': List of source_ids that were excluded
          - 'timestamp':   Time of fusion
    """
    readings = get_latest_readings()

    if not readings:
        result = {
            "status": "no_reliable_position",
            "reason": "no_readings",
            "timestamp": time.time(),
        }
        _log_fusion(result)
        return result

    valid = [r for r in readings if r["status"] != "anomalous"]
    flagged = [r for r in readings if r["status"] == "anomalous"]

    if not valid:
        result = {
            "status": "no_reliable_position",
            "reason": "all_sources_flagged",
            "sources_flagged": [r["source_id"] for r in flagged],
            "timestamp": time.time(),
        }
        _log_fusion(result)
        return result

    med_lat, med_lon = compute_median_position(valid)

    result = {
        "status": "ok",
        "lat": round(med_lat, 6),
        "lon": round(med_lon, 6),
        "sources_used": [r["source_id"] for r in valid],
        "sources_flagged": [r["source_id"] for r in flagged],
        "source_count": len(valid),
        "timestamp": time.time(),
    }
    _log_fusion(result)
    return result


def _log_fusion(result):
    """Write the fusion result to the events table for history tracking."""
    insert_event(
        event_type="fusion_result",
        details={k: v for k, v in result.items() if k != "timestamp"},
        timestamp=result["timestamp"],
    )
