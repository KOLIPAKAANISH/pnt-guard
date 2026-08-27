/**
 * dashboard.js — PNT-Guard Mission Control (Enhanced)
 *
 * Leaflet map with real-time source tracking, anomaly rings,
 * fused position marker, trail polylines, deviation chart,
 * and auto-refresh from /status, /fused, /history, /api/readings.
 *
 * Visual enhancements: boot sequence, confidence meters, live
 * ticking numbers, alert flash, marker-card micro-interactions.
 */

(function () {
    "use strict";

    // ── Config ──────────────────────────────────────────────
    var POLL_MS = 3000;
    var TRAIL_MAX = 80;
    var SOURCE_COLORS = {};
    var PALETTE = ["#22d3ee", "#22c55e", "#eab308", "#f97316", "#a78bfa", "#ec4899"];
    var colorIdx = 0;

    // ── State ───────────────────────────────────────────────
    var map, markers = {}, trails = {}, anomalyRings = {}, fusedMarker = null;
    var trailLines = {};       // track all polyline layers per source
    var chart = null;
    var deviationHistory = {};
    var startTime = Date.now();
    var previousSources = {};      // track previous source data for tick animations
    var previousHistoryCount = 0;  // track history count for alert flash
    var markerToCard = {};         // map source_id -> card element
    var cardToMarker = {};         // map source_id -> marker element (for highlight)
    var lastFusedCoords = "";      // track fused coords for tick animation

    // ── Helpers ─────────────────────────────────────────────
    function getColor(id) {
        if (!SOURCE_COLORS[id]) {
            SOURCE_COLORS[id] = PALETTE[colorIdx % PALETTE.length];
            colorIdx++;
        }
        return SOURCE_COLORS[id];
    }

    function fmtTime(ep) {
        if (!ep) return "--:--:--";
        return new Date(ep * 1000).toLocaleTimeString("en-GB");
    }

    function fmtTimeShort(ep) {
        if (!ep) return "--";
        var d = new Date(ep * 1000);
        return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }

    function escapeHtml(s) {
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    // Compute confidence %: how close a source is to the fused position (0-100)
    function computeConfidence(srcLat, srcLon, fusedLat, fusedLon) {
        if (!fusedLat || !fusedLon) return 0;
        var R = 6371000;
        var phi1 = srcLat * Math.PI / 180, phi2 = fusedLat * Math.PI / 180;
        var dphi = (fusedLat - srcLat) * Math.PI / 180;
        var dlam = (fusedLon - srcLon) * Math.PI / 180;
        var a = Math.sin(dphi / 2) * Math.sin(dphi / 2) +
                Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) * Math.sin(dlam / 2);
        var dist = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        // Map distance to confidence: 0m -> 100%, 500m+ -> 0%
        var conf = Math.max(0, Math.min(100, Math.round(100 - (dist / 5))));
        return conf;
    }

    function getConfidenceClass(val) {
        if (val >= 70) return "high";
        if (val >= 40) return "medium";
        return "low";
    }

    // ── Boot-Up Sequence ────────────────────────────────────
    function runBootSequence() {
        var overlay = document.getElementById("bootOverlay");
        if (!overlay) return;

        var lines = overlay.querySelectorAll(".boot-line");
        var bar = document.getElementById("bootProgressBar");

        lines.forEach(function (line) {
            var delay = parseInt(line.getAttribute("data-delay"), 10) || 0;
            setTimeout(function () {
                line.classList.add("visible");
            }, delay + 200);
        });

        // Progress bar
        var progress = 0;
        var progressInterval = setInterval(function () {
            progress += Math.random() * 25 + 10;
            if (progress >= 100) {
                progress = 100;
                clearInterval(progressInterval);
            }
            if (bar) bar.style.width = progress + "%";
        }, 250);

        // Fade out after 2s
        setTimeout(function () {
            overlay.classList.add("fade-out");
            setTimeout(function () {
                overlay.style.display = "none";
            }, 600);
        }, 2000);
    }

    // ── Alert Flash Effect ──────────────────────────────────
    function triggerAlertFlash() {
        var el = document.getElementById("alertFlash");
        if (!el) return;
        el.classList.remove("active");
        // Force reflow
        void el.offsetWidth;
        el.classList.add("active");
        setTimeout(function () {
            el.classList.remove("active");
        }, 2100);
    }

    // ── Clock & Uptime ──────────────────────────────────────
    function tickClock() {
        var now = new Date();
        document.getElementById("liveClock").textContent =
            now.toLocaleTimeString("en-GB") + " UTC";
        var elapsed = Math.floor((Date.now() - startTime) / 1000);
        var h = String(Math.floor(elapsed / 3600)).padStart(2, "0");
        var m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
        var s = String(elapsed % 60).padStart(2, "0");
        document.getElementById("uptime").textContent = h + ":" + m + ":" + s;
    }
    setInterval(tickClock, 1000);
    tickClock();

    // ── Leaflet Map Init ────────────────────────────────────
    function initMap() {
        map = L.map("map", {
            center: [37.775, -122.419],
            zoom: 16,
            zoomControl: true,
            attributionControl: true
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors",
            maxZoom: 19
        }).addTo(map);
    }

    // ── Custom Marker Icons (with glow halos + pulse) ───────
    function makeSourceIcon(color, anomalous) {
        var size = anomalous ? 16 : 12;
        var glowSize = size + 20;
        var glowColor = anomalous ? "rgba(239, 68, 68, 0.35)" : color.replace(")", ", 0.3)").replace("rgb", "rgba");
        // Convert hex to rgba for glow
        if (color.charAt(0) === "#") {
            var r = parseInt(color.slice(1, 3), 16);
            var g = parseInt(color.slice(3, 5), 16);
            var b = parseInt(color.slice(5, 7), 16);
            glowColor = anomalous ? "rgba(239, 68, 68, 0.35)" : "rgba(" + r + "," + g + "," + b + ", 0.35)";
        }
        return L.divIcon({
            className: "",
            html: '<div class="marker-pulse" style="' +
                'position:relative;width:' + glowSize + 'px;height:' + glowSize + 'px;' +
                '">' +
                '<div class="marker-halo" style="' +
                'width:' + glowSize + 'px;height:' + glowSize + 'px;' +
                'background:radial-gradient(circle,' + glowColor + ' 0%,transparent 70%);' +
                '"></div>' +
                '<div style="' +
                'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
                'width:' + size + 'px;height:' + size + 'px;' +
                'background:' + color + ';' +
                'border:2px solid ' + (anomalous ? '#ef4444' : '#fff') + ';' +
                'border-radius:50%;' +
                'box-shadow:0 0 10px ' + color + ', 0 0 20px ' + glowColor + ';' +
                'transition:all 0.3s ease;' +
                'z-index:2;' +
                '"></div>' +
                '</div>',
            iconSize: [glowSize, glowSize],
            iconAnchor: [glowSize / 2, glowSize / 2]
        });
    }

    function makeFusedIcon() {
        return L.divIcon({
            className: "fused-marker-glow",
            html: '<div style="' +
                'width:28px;height:28px;' +
                'position:relative;' +
                '">' +
                '<div style="' +
                'position:absolute;inset:-6px;' +
                'border-radius:50%;' +
                'background:radial-gradient(circle,rgba(59,130,246,0.25) 0%,transparent 70%);' +
                'animation:fusedGlow 3s ease-in-out infinite;' +
                '"></div>' +
                '<div style="width:28px;height:28px;border:2px solid #3b82f6;border-radius:50%;background:rgba(59,130,246,0.15);box-shadow:0 0 16px rgba(59,130,246,0.5),0 0 32px rgba(59,130,246,0.2);position:relative;z-index:1;"></div>' +
                '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:8px;height:8px;background:#3b82f6;border-radius:50%;box-shadow:0 0 8px #3b82f6;z-index:2;"></div>' +
                '</div>',
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });
    }

    function makeAnomalyRing(color) {
        return L.divIcon({
            className: "anomaly-pulse",
            html: '<div style="' +
                'width:40px;height:40px;' +
                'border:2px solid ' + color + ';' +
                'border-radius:50%;' +
                '"></div>',
            iconSize: [40, 40],
            iconAnchor: [20, 20]
        });
    }

    // ── Source Markers + Trails (with fading opacity) ────────
    function updateSourceMarkers(sources) {
        sources.forEach(function (s) {
            var color = getColor(s.source_id);
            var isAnom = s.status === "anomalous";
            var latlng = [s.lat, s.lon];

            // Marker
            if (markers[s.source_id]) {
                markers[s.source_id].setLatLng(latlng);
                markers[s.source_id].setIcon(makeSourceIcon(color, isAnom));
            } else {
                markers[s.source_id] = L.marker(latlng, {
                    icon: makeSourceIcon(color, isAnom),
                    zIndexOffset: 1000
                }).addTo(map).bindPopup(
                    '<b style="font-family:monospace">' + escapeHtml(s.source_id) + '</b><br>' +
                    s.lat.toFixed(6) + ", " + s.lon.toFixed(6) + "<br>" +
                    '<span style="color:' + (isAnom ? '#ef4444' : '#22c55e') + '">' +
                    (isAnom ? "ANOMALOUS" : "OK") + "</span>"
                );

                // Micro-interaction: hover marker -> highlight card
                markers[s.source_id].on("mouseover", function () {
                    var card = document.querySelector('.source-card[data-source="' + s.source_id + '"]');
                    if (card) card.classList.add("highlight");
                });
                markers[s.source_id].on("mouseout", function () {
                    var card = document.querySelector('.source-card[data-source="' + s.source_id + '"]');
                    if (card) card.classList.remove("highlight");
                });
            }

            // Anomaly ring
            if (isAnom && !anomalyRings[s.source_id]) {
                anomalyRings[s.source_id] = L.marker(latlng, {
                    icon: makeAnomalyRing(color),
                    interactive: false
                }).addTo(map);
            } else if (isAnom && anomalyRings[s.source_id]) {
                anomalyRings[s.source_id].setLatLng(latlng);
            } else if (!isAnom && anomalyRings[s.source_id]) {
                map.removeLayer(anomalyRings[s.source_id]);
                delete anomalyRings[s.source_id];
            }

            // Trail (with fading opacity per older point)
            if (!trails[s.source_id]) trails[s.source_id] = [];
            trails[s.source_id].push(latlng);
            if (trails[s.source_id].length > TRAIL_MAX) {
                trails[s.source_id].shift();
            }

            // Remove old trail segments
            if (trailLines[s.source_id]) {
                trailLines[s.source_id].forEach(function (layer) {
                    map.removeLayer(layer);
                });
                trailLines[s.source_id] = [];
            }
            if (trails[s.source_id].length > 1) {
                // Draw trail as multiple segments with decreasing opacity
                var pts = trails[s.source_id];
                var segs = [];
                for (var i = 0; i < pts.length - 1; i++) {
                    var opacity = 0.05 + (i / pts.length) * 0.55;
                    var weight = 1 + (i / pts.length) * 1.5;
                    var seg = L.polyline([pts[i], pts[i + 1]], {
                        color: color,
                        weight: weight,
                        opacity: opacity,
                        smoothFactor: 1,
                        interactive: false
                    }).addTo(map);
                    segs.push(seg);
                }
                trailLines[s.source_id] = segs;
            }
        });
    }

    // ── Fused Marker (with tick animation) ──────────────────
    function updateFusedMarker(data) {
        var panel = document.getElementById("fusedPanel");

        if (!data || data.status !== "ok") {
            panel.innerHTML =
                '<div class="fused-status no-fix">NO FIX</div>' +
                '<div class="fused-coords">---.------ , ---.------</div>' +
                '<div class="fused-sources">' + (data ? (data.reason || "") : "waiting") + '</div>';
            if (fusedMarker) { map.removeLayer(fusedMarker); fusedMarker = null; }
            lastFusedCoords = "";
            return;
        }

        var latlng = [data.lat, data.lon];
        var newCoords = data.lat.toFixed(6) + " , " + data.lon.toFixed(6);

        // Check if coords changed for tick animation
        var coordsChanged = lastFusedCoords !== "" && lastFusedCoords !== newCoords;
        lastFusedCoords = newCoords;

        panel.innerHTML =
            '<div class="fused-status fix">FIX ACQUIRED</div>' +
            '<div class="fused-coords' + (coordsChanged ? ' updating' : '') + '">' + newCoords + "</div>" +
            '<div class="fused-sources">Sources: ' +
            (data.sources_used || []).join(", ") +
            (data.sources_flagged && data.sources_flagged.length
                ? " | Excl: " + data.sources_flagged.join(", ")
                : "") +
            "</div>";

        if (fusedMarker) {
            fusedMarker.setLatLng(latlng);
        } else {
            fusedMarker = L.marker(latlng, {
                icon: makeFusedIcon(),
                zIndexOffset: 2000
            }).addTo(map).bindPopup("<b>FUSED POSITION</b><br>" + data.lat.toFixed(6) + ", " + data.lon.toFixed(6));
        }
    }

    // ── System Status Badge ─────────────────────────────────
    function updateSystemStatus(sources) {
        var el = document.getElementById("systemStatus");
        var anyAnom = sources.some(function (s) { return s.status === "anomalous"; });
        if (anyAnom) {
            el.textContent = "ANOMALY DETECTED";
            el.className = "system-status alert";
        } else {
            el.textContent = "ALL SYSTEMS NOMINAL";
            el.className = "system-status nominal";
        }
    }

    // ── Source Cards (with confidence meter + micro-interactions) ──
    function renderSourceCards(sources, fusedData) {
        var container = document.getElementById("sourceCards");
        if (!sources.length) {
            container.innerHTML = '<div class="source-card empty">Awaiting data...</div>';
            return;
        }

        var fusedLat = fusedData && fusedData.status === "ok" ? fusedData.lat : null;
        var fusedLon = fusedData && fusedData.status === "ok" ? fusedData.lon : null;

        container.innerHTML = sources.map(function (s) {
            var isAnom = s.status === "anomalous";
            var color = getColor(s.source_id);

            // Compute confidence
            var conf = fusedLat ? computeConfidence(s.lat, s.lon, fusedLat, fusedLon) : 0;
            var confClass = getConfidenceClass(conf);

            // Check if coords changed for tick animation
            var prev = previousSources[s.source_id];
            var coordsChanged = prev && (prev.lat !== s.lat || prev.lon !== s.lon);
            var timeChanged = prev && prev.timestamp !== s.timestamp;

            var coordsClass = coordsChanged ? ' updating' : '';

            return '<div class="source-card ' + (isAnom ? "anomalous" : "ok") + '" data-source="' + escapeHtml(s.source_id) + '">' +
                '<div class="source-card-top">' +
                '<span class="source-name" style="color:' + color + '">' + escapeHtml(s.source_id) + "</span>" +
                '<span class="source-badge ' + (isAnom ? "anomalous" : "ok") + '">' +
                (isAnom ? "FLAGGED" : "OK") + "</span>" +
                "</div>" +
                '<div class="source-coords' + coordsClass + '">' + s.lat.toFixed(6) + ", " + s.lon.toFixed(6) + "</div>" +
                '<div class="source-time">Last: ' + fmtTime(s.timestamp) + "</div>" +
                '<div class="confidence-meter">' +
                '<span class="confidence-label">CONF</span>' +
                '<div class="confidence-track">' +
                '<div class="confidence-fill ' + confClass + '" style="width:' + conf + '%"></div>' +
                '</div>' +
                '<span class="confidence-value ' + confClass + '" style="color:var(--accent-' + (confClass === 'high' ? 'green' : confClass === 'medium' ? 'yellow' : 'red') + ')">' + conf + '%</span>' +
                '</div>' +
                "</div>";
        }).join("");

        // Store previous data for next tick comparison
        sources.forEach(function (s) {
            previousSources[s.source_id] = {
                lat: s.lat,
                lon: s.lon,
                timestamp: s.timestamp
            };
        });

        // Micro-interaction: hover card -> highlight marker
        var cards = container.querySelectorAll(".source-card[data-source]");
        cards.forEach(function (card) {
            card.addEventListener("mouseenter", function () {
                var srcId = card.getAttribute("data-source");
                if (markers[srcId]) {
                    markers[srcId].getElement && markers[srcId].getElement();
                    // Add a temporary highlight class to the marker icon
                    var el = markers[srcId].getElement();
                    if (el) {
                        var inner = el.querySelector("div");
                        if (inner) inner.style.transform = "translate(-50%,-50%) scale(1.4)";
                    }
                }
            });
            card.addEventListener("mouseleave", function () {
                var srcId = card.getAttribute("data-source");
                if (markers[srcId]) {
                    var el = markers[srcId].getElement();
                    if (el) {
                        var inner = el.querySelector("div");
                        if (inner) inner.style.transform = "translate(-50%,-50%) scale(1)";
                    }
                }
            });
        });
    }

    // ── Event Log (terminal-styled, slide-in, color-coded) ──
    function renderEvents(data) {
        var body = document.getElementById("eventBody");
        var badge = document.getElementById("eventCount");
        var mapEvt = document.getElementById("mapEventCount");

        if (!data || !data.events || !data.events.length) {
            body.innerHTML = '<tr><td colspan="4" class="empty-row">No events</td></tr>';
            badge.textContent = "0";
            if (mapEvt) mapEvt.textContent = "0";
            return;
        }

        badge.textContent = data.count;
        if (mapEvt) mapEvt.textContent = data.count;

        // Detect new anomalies for alert flash
        if (data.count > previousHistoryCount) {
            // Check if any new events are anomalies
            var hasNewAnomaly = data.events.some(function (e) {
                return e.event_type === "anomaly_flag";
            });
            if (hasNewAnomaly) {
                triggerAlertFlash();
            }
        }
        previousHistoryCount = data.count;

        body.innerHTML = data.events.map(function (e) {
            var label = e.event_type === "anomaly_flag" ? "ANOMALY" : "FUSION";
            var src = e.details.source_id || (e.details.sources_used || []).join(",") || "--";
            var detail = "";
            if (e.event_type === "anomaly_flag" && e.details.reasons) {
                detail = e.details.reasons.join(", ");
            } else if (e.event_type === "fusion_result") {
                detail = e.details.status === "ok"
                    ? "(" + (e.details.lat || 0).toFixed(4) + ", " + (e.details.lon || 0).toFixed(4) + ")"
                    : e.details.reason || "no fix";
            }

            // Color-code by severity
            var severityClass = "";
            if (e.event_type === "anomaly_flag") {
                severityClass = " event-anomaly";
            }

            return "<tr class=\"event-row" + severityClass + "\">" +
                '<td class="event-time-cell">' + fmtTimeShort(e.timestamp) + "</td>" +
                '<td class="event-source-cell">' + escapeHtml(src) + "</td>" +
                '<td><span class="event-type-badge ' + e.event_type + '">' + label + "</span></td>" +
                '<td class="event-details-cell">' + escapeHtml(detail) + "</td>" +
                "</tr>";
        }).join("");
    }

    // ── Deviation Chart ─────────────────────────────────────
    function initChart() {
        var ctx = document.getElementById("deviationChart");
        if (!ctx) return;
        chart = new Chart(ctx.getContext("2d"), {
            type: "line",
            data: { labels: [], datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 200 },
                plugins: {
                    legend: {
                        display: true,
                        position: "top",
                        labels: { color: "#64748b", font: { size: 9 }, boxWidth: 8, padding: 6 }
                    }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        title: { display: true, text: "m", color: "#475569", font: { size: 9 } },
                        ticks: { color: "#475569", font: { size: 9 } },
                        grid: { color: "rgba(30, 41, 59, 0.5)" },
                        beginAtZero: true
                    }
                }
            }
        });
    }

    function updateDeviationChart(readings, fusedData) {
        if (!chart || !readings || !readings.readings || !fusedData || fusedData.status !== "ok") return;

        var grouped = {};
        readings.readings.forEach(function (r) {
            if (!grouped[r.source_id]) grouped[r.source_id] = [];
            grouped[r.source_id].push(r);
        });

        // Compute deviation from fused for each source's latest reading
        var now = new Date().toLocaleTimeString("en-GB", { second: "2-digit" });
        var labels = chart.data.labels;
        labels.push(now);
        if (labels.length > 30) labels.shift();

        var colors = ["#22d3ee", "#22c55e", "#eab308"];
        var datasets = chart.data.datasets;

        var srcIds = Object.keys(grouped).sort();
        srcIds.forEach(function (srcId, idx) {
            var pts = grouped[srcId];
            if (!pts.length) return;
            var p = pts[0]; // latest
            var R = 6371000;
            var phi1 = p.lat * Math.PI / 180, phi2 = fusedData.lat * Math.PI / 180;
            var dphi = (fusedData.lat - p.lat) * Math.PI / 180;
            var dlam = (fusedData.lon - p.lon) * Math.PI / 180;
            var a = Math.sin(dphi / 2) * Math.sin(dphi / 2) +
                    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) * Math.sin(dlam / 2);
            var dist = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

            if (!datasets[idx]) {
                datasets[idx] = {
                    label: srcId,
                    data: [],
                    borderColor: colors[idx % colors.length],
                    backgroundColor: colors[idx % colors.length] + "33",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false
                };
            }
            datasets[idx].data.push(Math.round(dist));
            if (datasets[idx].data.length > 30) datasets[idx].data.shift();
        });

        chart.update("none");
    }

    // ── Fetch Helpers ───────────────────────────────────────
    function fetchJson(url) {
        return fetch(url).then(function (r) {
            if (!r.ok) return null;
            return r.json();
        }).catch(function () { return null; });
    }

    // ── Main Poll ───────────────────────────────────────────
    function poll() {
        var statusP = fetchJson("/status");
        var fusedP = fetchJson("/fused");
        var histP = fetchJson("/history?minutes=5");
        var readP = fetchJson("/api/readings?limit=" + TRAIL_MAX);

        Promise.all([statusP, fusedP, histP, readP]).then(function (results) {
            var status = results[0];
            var fused = results[1];
            var history = results[2];
            var readings = results[3];

            var sources = status ? status.sources : [];

            updateSourceMarkers(sources);
            updateFusedMarker(fused);
            updateSystemStatus(sources);
            renderSourceCards(sources, fused);
            renderEvents(history);
            updateDeviationChart(readings, fused);

            var mapSrc = document.getElementById("mapSourceCount");
            if (mapSrc) mapSrc.textContent = sources.length;

            // Auto-center map on first data
            if (sources.length && !map._pntGuardCentered) {
                map._pntGuardCentered = true;
                var lats = sources.map(function (s) { return s.lat; });
                var lons = sources.map(function (s) { return s.lon; });
                var avgLat = lats.reduce(function (a, b) { return a + b; }, 0) / lats.length;
                var avgLon = lons.reduce(function (a, b) { return a + b; }, 0) / lons.length;
                map.setView([avgLat, avgLon], 16);
            }
        });
    }

    // ── Init ────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", function () {
        // Run boot-up sequence first
        runBootSequence();

        // Initialize everything after boot completes
        setTimeout(function () {
            initMap();
            initChart();
            poll();
            setInterval(poll, POLL_MS);
        }, 2100);
    });

})();
