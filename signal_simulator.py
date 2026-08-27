"""
signal_simulator.py -- Signal simulator for PNT-Guard.

Generates realistic-looking lat/lon readings for 3 simulated sources
and POSTs them to the ingestion endpoint every few seconds.

This is only for testing/feeding data to the engine. The engine itself
does not know or care whether data is real or simulated.

Sources simulate receivers moving in small circles (simulating
stationary or slow-moving receivers with GPS jitter) around 3
different base locations in the San Francisco Bay Area.

Usage:
    python signal_simulator.py [--url http://localhost:5000] [--interval 3]
"""

import argparse
import json
import math
import random
import sys
import time
import urllib.request
import urllib.error

import config


# --- Simulated source configurations ---
# Each source has a base position and parameters for realistic jitter.
SOURCES = [
    {
        "id": "gps_alpha",
        "base_lat": 37.7749,     # San Francisco
        "base_lon": -122.4194,
        "jitter_m": 15,          # Typical GPS accuracy ~10-20m
        "drift_radius_m": 50,    # Slow drift within this radius
        "drift_speed": 0.002,    # Radians per step for drift circle
    },
    {
        "id": "gnss_beta",
        "base_lat": 37.7755,     # ~70m NE of alpha
        "base_lon": -122.4188,
        "jitter_m": 25,          # Slightly worse receiver
        "drift_radius_m": 60,
        "drift_speed": 0.001,
    },
    {
        "id": "beidou_gamma",
        "base_lat": 37.7745,     # ~50m SW of alpha
        "base_lon": -122.4200,
        "jitter_m": 10,          # High-end receiver
        "drift_radius_m": 40,
        "drift_speed": 0.003,
    },
]


# State for each source's drift circle
_phases = [random.uniform(0, 2 * math.pi) for _ in SOURCES]


def meters_to_deg_lat(meters):
    """Convert meters to approximate latitude degrees (1 deg ~ 111,320 m)."""
    return meters / 111_320.0


def meters_to_deg_lon(meters, at_lat):
    """Convert meters to approximate longitude degrees at a given latitude."""
    return meters / (111_320.0 * math.cos(math.radians(at_lat)))


def generate_reading(source, phase, step):
    """
    Generate a single simulated reading for a source.

    Combines:
      - A slow circular drift around the base position (simulates receiver
        movement or satellite geometry changes).
      - Gaussian noise (simulates GPS/GNSS jitter).

    Args:
        source: Dict with base_lat, base_lon, jitter_m, etc.
        phase:  Current drift phase angle.
        step:   Current step number (for drift progression).

    Returns:
        Dict with source_id, lat, lon, timestamp.
    """
    # Drift component
    drift_lat = meters_to_deg_lat(
        source["drift_radius_m"] * math.cos(phase)
    )
    drift_lon = meters_to_deg_lon(
        source["drift_radius_m"] * math.sin(phase),
        source["base_lat"],
    )

    # Jitter component (Gaussian noise)
    jitter_lat = meters_to_deg_lat(random.gauss(0, source["jitter_m"]))
    jitter_lon = meters_to_deg_lon(
        random.gauss(0, source["jitter_m"]),
        source["base_lat"],
    )

    lat = source["base_lat"] + drift_lat + jitter_lat
    lon = source["base_lon"] + drift_lon + jitter_lon

    return {
        "source_id": source["id"],
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "timestamp": time.time(),
    }


def post_reading(url, reading):
    """
    POST a reading to the PNT-Guard ingestion endpoint.

    Args:
        url:     Full URL of the /ingest endpoint.
        reading: Dict to send as JSON body.

    Returns:
        True on success, False on failure (with error printed to stderr).
    """
    payload = json.dumps(reading).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return True
    except urllib.error.URLError as e:
        print(f"  WARN Failed to post reading for {reading['source_id']}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  WARN Unexpected error: {e}", file=sys.stderr)
        return False


def run(url, interval):
    """
    Main loop: generate and post readings from all sources at regular intervals.

    Args:
        url:      The /ingest endpoint URL.
        interval: Seconds between batches.
    """
    global _phases
    step = 0

    print("PNT-Guard Signal Simulator")
    print(f"   Target: {url}")
    print(f"   Interval: {interval}s")
    print(f"   Sources: {', '.join(s['id'] for s in SOURCES)}")
    print("   Press Ctrl+C to stop.\n")

    while True:
        step += 1
        timestamp = time.time()

        for i, source in enumerate(SOURCES):
            reading = generate_reading(source, _phases[i], step)

            # Occasionally inject an anomaly for testing
            if random.random() < config.SIMULATOR_ANOMALY_RATE:
                # Simulate a sudden jump ~2km away
                reading["lat"] += random.uniform(-0.02, 0.02)
                reading["lon"] += random.uniform(-0.02, 0.02)
                print(f"  [!] Injected anomaly for {source['id']} (step {step})")

            ok = post_reading(url, reading)
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] {source['id']}: ({reading['lat']}, {reading['lon']})")

        # Update drift phases
        _phases = [
            _phases[i] + SOURCES[i]["drift_speed"]
            for i in range(len(SOURCES))
        ]

        print(f"  -- Step {step} complete --\n")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="PNT-Guard Signal Simulator")
    parser.add_argument(
        "--url",
        default=config.SIMULATOR_URL,
        help=f"Ingestion endpoint URL (default: {config.SIMULATOR_URL})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=config.SIMULATOR_INTERVAL_S,
        help=f"Seconds between reading batches (default: {config.SIMULATOR_INTERVAL_S})",
    )
    args = parser.parse_args()

    try:
        run(args.url, args.interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
