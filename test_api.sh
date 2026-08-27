#!/usr/bin/env bash
# test_api.sh — Quick smoke test for the PNT-Guard API.
#
# Usage:
#   1. Start the server:  python app.py
#   2. Run this script:   bash test_api.sh
#
set -euo pipefail

BASE="http://localhost:5000"
PASS=0
FAIL=0

check() {
    local desc="$1" expect_code="$2" body="$3"
    local actual_code
    actual_code=$(echo "$body" | tail -1)
    body=$(echo "$body" | head -n -1)

    if [ "$actual_code" = "$expect_code" ]; then
        echo "  ✅ $desc (HTTP $actual_code)"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $desc — expected HTTP $expect_code, got $actual_code"
        echo "     $body"
        FAIL=$((FAIL + 1))
    fi
}

# We use a helper that captures both body and status code.
# `curl -w '\n%{http_code}'` appends the status code on a new line.
api() {
    curl -s -w '\n%{http_code}' "$@"
}

echo "🛰️  PNT-Guard API Test Suite"
echo "============================"
echo ""

# --- Health Check ---
echo "1. Health check"
BODY=$(api "$BASE/health")
check "GET /health" "200" "$BODY"
echo ""

# --- Ingest readings from 3 sources ---
echo "2. Ingest readings (3 sources)"

# Source A — normal
BODY=$(api -X POST "$BASE/ingest" \
    -H "Content-Type: application/json" \
    -d '{"source_id":"gps_a","lat":37.7749,"lon":-122.4194}')
check "POST /ingest gps_a (normal)" "201" "$BODY"

sleep 0.1

# Source B — normal
BODY=$(api -X POST "$BASE/ingest" \
    -H "Content-Type: application/json" \
    -d '{"source_id":"gps_b","lat":37.7750,"lon":-122.4195}')
check "POST /ingest gps_b (normal)" "201" "$BODY"

sleep 0.1

# Source C — normal
BODY=$(api -X POST "$BASE/ingest" \
    -H "Content-Type: application/json" \
    -d '{"source_id":"gps_c","lat":37.7748,"lon":-122.4193}')
check "POST /ingest gps_c (normal)" "201" "$BODY"

echo ""

# --- Error cases ---
echo "3. Error handling"

BODY=$(api -X POST "$BASE/ingest" \
    -H "Content-Type: application/json" \
    -d '{"source_id":"gps_a"}')
check "POST /ingest missing fields → 400" "400" "$BODY"

BODY=$(api -X POST "$BASE/ingest" \
    -H "Content-Type: application/json" \
    -d '{"source_id":"gps_x","lat":999,"lon":0}')
check "POST /ingest out-of-range lat → 400" "400" "$BODY"

BODY=$(api "$BASE/ingest")
check "GET /ingest (wrong method) → 405" "405" "$BODY"

echo ""

# --- Status ---
echo "4. Status endpoint"
BODY=$(api "$BASE/status")
check "GET /status" "200" "$BODY"
echo ""

# --- Fused ---
echo "5. Fused position"
BODY=$(api "$BASE/fused")
check "GET /fused" "200" "$BODY"
echo ""

# --- Inject anomaly and re-test ---
echo "6. Anomaly injection"

# Send another reading from gps_a that's ~3 km away
BODY=$(api -X POST "$BASE/ingest" \
    -H "Content-Type: application/json" \
    -d '{"source_id":"gps_a","lat":37.8000,"lon":-122.4500}')
check "POST /ingest gps_a (anomalous jump)" "201" "$BODY"

# Check status — gps_a should now be anomalous
BODY=$(api "$BASE/status")
check "GET /status after anomaly" "200" "$BODY"

# Check fused — should exclude gps_a
BODY=$(api "$BASE/fused")
check "GET /fused after anomaly" "200" "$BODY"
echo ""

# --- History ---
echo "7. History endpoint"
BODY=$(api "$BASE/history?minutes=5")
check "GET /history" "200" "$BODY"

BODY=$(api "$BASE/history?minutes=9999")
check "GET /history large window" "200" "$BODY"
echo ""

# --- Summary ---
echo "============================"
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "⚠️  Some tests failed."
    exit 1
fi
