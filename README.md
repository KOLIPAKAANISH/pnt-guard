# PNT-Guard

A multi-source position fusion and anomaly-detection engine. It accepts
positioning readings from multiple GNSS/satellite sources, detects
anomalous readings using rule-based checks, and computes a trusted
fused position from the healthy sources.

## How It Works

### Signal Ingestion
Readings arrive as `{source_id, lat, lon, timestamp}` via the `/ingest`
endpoint. Each reading is stored in SQLite with a status of `ok`.

### Anomaly Detection
Every time a new reading arrives, the engine compares the latest reading
from each source against the others using two rules:

1. **Distance deviation** — If one source is more than 500 meters from the
   median position of the others, it is flagged. The median is used instead
   of the mean because it is resistant to outliers.

2. **Velocity check** — If a source's position implies a speed greater than
   1000 m/s (~Mach 3) between two consecutive readings, it is flagged.
   This catches sudden jumps that no real vehicle could produce.

Flagged readings are marked as `anomalous` in the database and excluded
from fusion.

### Position Fusion
The fusion module computes a trusted position by taking the **median**
latitude and longitude of all non-anomalous sources. If all sources are
flagged, it returns `"no reliable position"` instead of producing a
false value.

### Dashboard
A live web dashboard at `/dashboard` shows:
- Status cards for each source (green = healthy, red = anomalous)
- A Chart.js scatter plot of source positions over time
- The fused position highlighted as a star
- An event log of anomaly flags and fusion results

The dashboard auto-refreshes every 3 seconds.

## Configuration

All thresholds are tunable in `config.py` (or via environment variables):

| Setting | Default | Env Var | Description |
|---------|---------|---------|-------------|
| Distance threshold | 500 m | `PNT_DISTANCE_THRESHOLD_M` | Max deviation from median |
| Velocity threshold | 1000 m/s | `PNT_VELOCITY_THRESHOLD_MS` | Max implied speed |
| Poll interval | 3 s | `PNT_POLL_INTERVAL_S` | Dashboard refresh rate |
| Simulator interval | 3 s | `PNT_SIMULATOR_INTERVAL_S` | Seconds between readings |
| Anomaly rate | 0.05 | `PNT_SIMULATOR_ANOMALY_RATE` | Simulator anomaly injection rate |
| DB path | `pnt_guard.db` | `PNT_GUARD_DB` | SQLite database file |
| Server port | 5000 | `PNT_SERVER_PORT` | Flask server port |

## Installation

```bash
pip install flask
```

That is the only dependency. Everything else uses Python's standard library.

## Running

### Quick start (server + simulator):
```bash
# Linux/macOS
bash run.sh

# Windows
run.bat
```

### Server only:
```bash
# Option 1: Flask CLI (recommended)
FLASK_APP=app.py flask run

# Option 2: Direct Python
python -c "from app import app; from models import init_db; init_db(); app.run()"

# Open http://localhost:5000/dashboard
```

### Simulator only (if server is already running):
```bash
python signal_simulator.py
```

### Run with custom settings:
```bash
PNT_DISTANCE_THRESHOLD_M=300 PNT_SERVER_PORT=8080 python app.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Submit a reading `{source_id, lat, lon, timestamp?}` |
| GET | `/status` | Latest reading from each source |
| GET | `/fused` | Current trusted position |
| GET | `/history?minutes=5` | Event log for last N minutes |
| GET | `/dashboard` | Live web dashboard |
| GET | `/api/readings?limit=200` | Recent readings for chart data |
| GET | `/health` | Health check |

## Testing

```bash
# Run all backend tests (15 tests)
python test_api.py

# Run frontend tests (5 tests)
python test_frontend.py

# Run unit tests for fusion and detection
python -m unittest test_unit -v
```

## Project Structure

```
app.py                  Flask application and API endpoints
config.py               All tunable thresholds and settings
models.py               SQLite database schema and helpers
ingestion.py            Signal ingestion and validation
detection.py            Anomaly detection (distance + velocity)
fusion.py               Position fusion (median estimator)
signal_simulator.py     Generates test data from 3 simulated sources
run.sh / run.bat        Startup scripts
templates/dashboard.html  Web dashboard
static/style.css          Dashboard styling
static/dashboard.js       Dashboard JavaScript (auto-refresh + Chart.js)
test_api.py              Backend API tests
test_frontend.py         Frontend tests
test_unit.py             Unit tests for detection and fusion logic
```

## Known Limitations

- **Simulated data only** — The signal simulator generates fake readings.
  It is not connected to real GNSS/satellite hardware. To use real data,
  replace the simulator with a script that reads from your GPS receiver
  and POSTs to `/ingest`.

- **Rule-based detection, not ML** — Anomaly detection uses fixed
  thresholds for distance and speed. It will not catch subtle spoofing
  patterns that a machine learning model might detect.

- **Median fusion only** — The fusion uses a simple median. It does not
  weight sources by reported accuracy or reliability.

- **Single-server** — SQLite is file-based and does not scale to
  multiple servers. For production, you would need a proper database.

- **No authentication** — The API and dashboard are open. Anyone on the
  network can submit readings or view positions.

## Extending PNT-Guard

### Connect to real GPS hardware
Replace `signal_simulator.py` with a script that reads NMEA sentences
from a serial port (e.g. via `pyserial`) and POSTs parsed lat/lon to
`/ingest`. The engine does not care where data comes from.

### Add more sources
Just POST readings with a new `source_id`. The engine handles any
number of sources automatically.

### Add ML-based anomaly detection
Create a new module (e.g. `ml_detection.py`) that trains on historical
readings. Call it from `detect_anomalies()` alongside the existing
rule-based checks. The rest of the system stays unchanged.

### Weighted fusion
Replace the median in `fusion.py` with a weighted average based on
each source's reported accuracy (if available in the reading).

### Production database
Swap SQLite for PostgreSQL or similar by changing `models.py`. The
rest of the code only calls helper functions, so the change is
contained.

## License

This is a demonstration project. Use freely.
