"""
test_frontend.py — Tests for the PNT-Guard dashboard frontend.
"""

import json
import sys
from app import app
from models import init_db


def run_tests():
    app.config["TESTING"] = True
    client = app.test_client()
    passed = 0
    failed = 0

    def check(desc, expected_code, response):
        nonlocal passed, failed
        actual = response.status_code
        if actual == expected_code:
            print(f"  OK  {desc} (HTTP {actual})")
            passed += 1
        else:
            print(f"  FAIL {desc} -- expected {expected_code}, got {actual}")
            failed += 1

    # Seed some data first
    for src, lat, lon in [("gps_a", 37.7749, -122.4194), ("gps_b", 37.775, -122.4195)]:
        client.post("/ingest", json={"source_id": src, "lat": lat, "lon": lon})

    # 1. Dashboard HTML
    print("\n1. Dashboard page")
    r = client.get("/dashboard")
    check("GET /dashboard serves HTML", 200, r)
    html = r.data.decode()
    assert "PNT-Guard" in html or "PNT-GUARD" in html, "Dashboard should contain title"
    assert "chart.js" in html.lower() or "chart.js" in html, "Dashboard should load Chart.js"
    assert "leaflet" in html.lower(), "Dashboard should load Leaflet"
    assert "sourceCards" in html, "Dashboard should have source cards container"
    assert "deviationChart" in html or "positionChart" in html, "Dashboard should have chart canvas"
    assert "eventBody" in html, "Dashboard should have event log table"
    assert "map" in html, "Dashboard should have map container"
    print("       HTML contains all required elements")

    # 2. Static CSS
    print("\n2. Static files")
    r = client.get("/static/style.css")
    check("GET /static/style.css", 200, r)
    css = r.data.decode()
    assert "--bg-primary" in css or "--bg" in css, "CSS should have custom properties"

    r = client.get("/static/dashboard.js")
    check("GET /static/dashboard.js", 200, r)
    js = r.data.decode()
    assert "poll" in js, "JS should have poll function"
    assert "/status" in js, "JS should poll /status"
    assert "/fused" in js, "JS should poll /fused"
    assert "/history" in js, "JS should poll /history"
    assert "/api/readings" in js, "JS should fetch /api/readings"

    # 3. API readings endpoint
    print("\n3. /api/readings endpoint")
    r = client.get("/api/readings")
    check("GET /api/readings", 200, r)
    data = r.get_json()
    assert "readings" in data
    assert data["count"] >= 2
    print(f"       Returned {data['count']} readings")

    r = client.get("/api/readings?limit=1")
    check("GET /api/readings?limit=1", 200, r)
    data = r.get_json()
    assert data["count"] == 1

    # 4. Dashboard page content checks
    print("\n4. Dashboard content")
    r = client.get("/dashboard")
    html = r.data.decode()
    assert "chart.js" in html.lower(), "Should load Chart.js CDN"
    assert "setInterval" in open("static/dashboard.js").read(), "JS should have setInterval"
    print("       Chart.js CDN and auto-refresh confirmed")

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    init_db()
    ok = run_tests()
    sys.exit(0 if ok else 1)
