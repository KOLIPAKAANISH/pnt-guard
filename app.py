"""
app.py — Flask application for the PNT-Guard position fusion engine.

Endpoints:
  POST /ingest   — Accept a positioning reading from a source
  GET  /status   — Latest reading from each source + anomaly flags
  GET  /fused    — Current fused/trusted position
  GET  /history  — Recent event log (flags, fusion results)

Run with:
  python app.py            (development server)
  flask --app app run      (alternative)
"""

from flask import Flask, request, jsonify, render_template
from models import init_db, get_latest_readings, get_recent_events, get_db
from ingestion import ingest_reading
from detection import detect_anomalies
from fusion import fuse_position

app = Flask(__name__)


@app.before_request
def ensure_db():
    """Initialize the database tables on first request if needed."""
    init_db()


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------
@app.route("/ingest", methods=["POST"])
def handle_ingest():
    """
    Accept a positioning reading and store it.

    Expected JSON body:
        {
            "source_id": "gps_a",
            "lat": 37.7749,
            "lon": -122.4194,
            "timestamp": 1700000000.0   // optional, defaults to now
        }

    On success, runs anomaly detection on all latest readings and returns
    the ingestion result plus any newly detected anomalies.
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    # Extract and validate required fields
    source_id = data.get("source_id")
    lat = data.get("lat")
    lon = data.get("lon")
    timestamp = data.get("timestamp")

    if source_id is None or lat is None or lon is None:
        return jsonify({
            "error": "Missing required fields: source_id, lat, lon"
        }), 400

    try:
        result = ingest_reading(
            source_id=str(source_id),
            lat=float(lat),
            lon=float(lon),
            timestamp=float(timestamp) if timestamp is not None else None,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.error(f"Ingestion failed: {e}")
        return jsonify({"error": "Internal server error during ingestion"}), 500

    # Run anomaly detection after each new reading
    try:
        anomaly_flags = detect_anomalies()
    except Exception as e:
        app.logger.error(f"Detection failed: {e}")
        anomaly_flags = {}

    return jsonify({
        "reading": result,
        "anomaly_flags": anomaly_flags,
    }), 201


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------
@app.route("/status", methods=["GET"])
def handle_status():
    """
    Return the latest reading from each source, including anomaly status.

    Response:
        {
            "sources": [
                {
                    "source_id": "gps_a",
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "timestamp": 1700000000.0,
                    "status": "ok"
                },
                ...
            ],
            "source_count": 3
        }
    """
    try:
        readings = get_latest_readings()
    except Exception as e:
        app.logger.error(f"Status query failed: {e}")
        return jsonify({"error": "Failed to query status"}), 500

    return jsonify({
        "sources": readings,
        "source_count": len(readings),
    })


# ---------------------------------------------------------------------------
# GET /fused
# ---------------------------------------------------------------------------
@app.route("/fused", methods=["GET"])
def handle_fused():
    """
    Return the current fused/trusted position.

    The fusion engine excludes anomalous readings and computes the median
    position of the remaining sources. If all sources are flagged, returns
    a 'no_reliable_position' status.
    """
    try:
        result = fuse_position()
    except Exception as e:
        app.logger.error(f"Fusion failed: {e}")
        return jsonify({"error": "Fusion computation failed"}), 500

    status_code = 200 if result["status"] == "ok" else 422
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------
@app.route("/history", methods=["GET"])
def handle_history():
    """
    Return recent event log for the last N minutes.

    Query params:
        minutes — How many minutes of history (default: 5)

    Response:
        {
            "events": [ ... ],
            "minutes": 5,
            "count": 12
        }
    """
    try:
        minutes = request.args.get("minutes", default=5, type=int)
        if minutes < 1 or minutes > 1440:
            return jsonify({"error": "minutes must be between 1 and 1440"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'minutes' parameter"}), 400

    try:
        events = get_recent_events(minutes=minutes)
    except Exception as e:
        app.logger.error(f"History query failed: {e}")
        return jsonify({"error": "Failed to query history"}), 500

    return jsonify({
        "events": events,
        "minutes": minutes,
        "count": len(events),
    })


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def handle_health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "engine": "PNT-Guard"})


# ---------------------------------------------------------------------------
# Dashboard (read-only HTML)
# ---------------------------------------------------------------------------
@app.route("/dashboard", methods=["GET"])
def handle_dashboard():
    """Serve the live monitoring dashboard."""
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# API: recent readings for charting (read-only)
# ---------------------------------------------------------------------------
@app.route("/api/readings", methods=["GET"])
def handle_api_readings():
    """
    Return recent readings for all sources, grouped by source_id.

    Query params:
        limit — Max total readings to return (default: 200)

    This is a read-only endpoint used by the dashboard chart.
    """
    try:
        limit = request.args.get("limit", default=200, type=int)
        limit = max(1, min(limit, 2000))
    except (ValueError, TypeError):
        limit = 200

    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT source_id, lat, lon, timestamp, status "
            "FROM readings ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        readings = [dict(r) for r in rows]
    except Exception as e:
        app.logger.error(f"Readings query failed: {e}")
        return jsonify({"error": "Failed to query readings"}), 500

    return jsonify({"readings": readings, "count": len(readings)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("PNT-Guard engine starting on http://localhost:5000")
    print("  POST /ingest   - Submit a reading")
    print("  GET  /status   - Latest readings from all sources")
    print("  GET  /fused    - Current fused position")
    print("  GET  /history  - Event log (last N minutes)")
    print("  GET  /health   - Health check")
    import os
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
