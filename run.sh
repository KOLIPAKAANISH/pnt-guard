#!/usr/bin/env bash
# run.sh — Start the PNT-Guard engine and signal simulator together.
#
# Usage:
#   bash run.sh              # Start both server and simulator
#   bash run.sh --server     # Start server only
#   bash run.sh --simulator  # Start simulator only (server must be running)
#
set -euo pipefail

MODE="${1:-all}"
PORT="${PNT_SERVER_PORT:-5000}"
URL="http://localhost:${PORT}/ingest"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$SERVER_PID" 2>/dev/null || true
    kill "$SIM_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    wait "$SIM_PID" 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

# --- Start the Flask server ---
start_server() {
    echo "Starting PNT-Guard server on port ${PORT}..."
    FLASK_APP=app.py flask run --no-debugger --host 0.0.0.0 --port "${PORT}" &
    SERVER_PID=$!
    sleep 2
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "  Server running (PID ${SERVER_PID})"
    else
        echo "  ERROR: Server failed to start."
        exit 1
    fi
}

# --- Start the signal simulator ---
start_simulator() {
    echo "Starting signal simulator -> ${URL}"
    python signal_simulator.py --url "$URL" --interval "${PNT_SIMULATOR_INTERVAL_S:-3}" &
    SIM_PID=$!
    sleep 1
    if kill -0 "$SIM_PID" 2>/dev/null; then
        echo "  Simulator running (PID ${SIM_PID})"
    else
        echo "  ERROR: Simulator failed to start."
        exit 1
    fi
}

case "$MODE" in
    --server)
        start_server
        echo ""
        echo "Dashboard: http://localhost:${PORT}/dashboard"
        echo "Press Ctrl+C to stop."
        wait "$SERVER_PID"
        ;;
    --simulator)
        start_simulator
        echo "Press Ctrl+C to stop."
        wait "$SIM_PID"
        ;;
    *)
        start_server
        start_simulator
        echo ""
        echo "============================================"
        echo " PNT-Guard is running!"
        echo ""
        echo " Dashboard:  http://localhost:${PORT}/dashboard"
        echo " API Status: http://localhost:${PORT}/status"
        echo " Fused Pos:  http://localhost:${PORT}/fused"
        echo " Health:     http://localhost:${PORT}/health"
        echo "============================================"
        echo "Press Ctrl+C to stop."
        wait
        ;;
esac
