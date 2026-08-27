"""
test_api.py — Python-based smoke test for PNT-Guard.

Starts the Flask server in-process and runs all endpoint tests.
No need to manually start the server first.
"""

import json
import sys
import time
import threading

from app import app
from models import init_db


def run_tests():
    """Run all API tests using the Flask test client."""
    app.config["TESTING"] = True
    client = app.test_client()

    passed = 0
    failed = 0

    def check(desc, expected_code, response):
        nonlocal passed, failed
        actual_code = response.status_code
        if actual_code == expected_code:
            print(f"  OK  {desc} (HTTP {actual_code})")
            passed += 1
        else:
            print(f"  FAIL {desc} -- expected HTTP {expected_code}, got {actual_code}")
            try:
                body = response.get_json()
                print(f"       Body: {json.dumps(body, indent=2)[:200]}")
            except Exception:
                print(f"       Body: {response.data[:200]}")
            failed += 1

    # 1. Health check
    print("\n1. Health check")
    r = client.get("/health")
    check("GET /health", 200, r)

    # 2. Ingest normal readings from 3 sources
    print("\n2. Ingest readings (3 sources)")
    for src, lat, lon in [
        ("gps_a", 37.7749, -122.4194),
        ("gps_b", 37.7750, -122.4195),
        ("gps_c", 37.7748, -122.4193),
    ]:
        r = client.post("/ingest", json={
            "source_id": src, "lat": lat, "lon": lon
        })
        check(f"POST /ingest {src} (normal)", 201, r)

    # 3. Error handling
    print("\n3. Error handling")
    r = client.post("/ingest", json={"source_id": "gps_x"})
    check("POST /ingest missing fields -> 400", 400, r)

    r = client.post("/ingest", json={"source_id": "gps_x", "lat": 999, "lon": 0})
    check("POST /ingest out-of-range lat -> 400", 400, r)

    r = client.get("/ingest")
    check("GET /ingest (wrong method) -> 405", 405, r)

    # 4. Status
    print("\n4. Status endpoint")
    r = client.get("/status")
    check("GET /status", 200, r)
    data = r.get_json()
    assert data["source_count"] == 3, f"Expected 3 sources, got {data['source_count']}"
    print(f"       Sources: {[s['source_id'] for s in data['sources']]}")

    # 5. Fused position
    print("\n5. Fused position")
    r = client.get("/fused")
    check("GET /fused", 200, r)
    data = r.get_json()
    assert data["status"] == "ok", f"Expected status ok, got {data['status']}"
    print(f"       Fused: ({data['lat']}, {data['lon']})")
    print(f"       Sources used: {data['sources_used']}")

    # 6. Inject anomaly
    print("\n6. Anomaly injection")
    r = client.post("/ingest", json={
        "source_id": "gps_a",
        "lat": 38.0000,
        "lon": -122.0000,
    })
    check("POST /ingest gps_a (anomalous jump ~30km away)", 201, r)

    r = client.get("/status")
    check("GET /status after anomaly", 200, r)
    data = r.get_json()
    anomalous = [s for s in data["sources"] if s["status"] == "anomalous"]
    print(f"       Anomalous sources: {[s['source_id'] for s in anomalous]}")

    r = client.get("/fused")
    check("GET /fused after anomaly", 200, r)
    data = r.get_json()
    assert "gps_a" in data["sources_flagged"], "gps_a should be flagged"
    print(f"       Fused excludes: {data['sources_flagged']}")
    print(f"       Fused position: ({data['lat']}, {data['lon']})")

    # 7. All-sources-flagged scenario
    print("\n7. All sources anomalous scenario")
    # Make gps_b and gps_c also anomalous
    r = client.post("/ingest", json={
        "source_id": "gps_b",
        "lat": 30.0000,
        "lon": -130.0000,
    })
    r = client.post("/ingest", json={
        "source_id": "gps_c",
        "lat": 45.0000,
        "lon": -115.0000,
    })

    r = client.get("/fused")
    check("GET /fused (all anomalous)", 422, r)
    data = r.get_json()
    assert data["status"] == "no_reliable_position"
    print(f"       Status: {data['status']} (correctly refused)")

    # 8. History
    print("\n8. History endpoint")
    r = client.get("/history?minutes=5")
    check("GET /history", 200, r)
    data = r.get_json()
    print(f"       Events in last 5 min: {data['count']}")
    event_types = set(e["event_type"] for e in data["events"])
    print(f"       Event types: {event_types}")

    r = client.get("/history?minutes=0")
    check("GET /history invalid minutes -> 400", 400, r)

    # Summary
    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"WARNING: {failed} test(s) failed.")
    return failed == 0


if __name__ == "__main__":
    init_db()
    success = run_tests()
    sys.exit(0 if success else 1)
