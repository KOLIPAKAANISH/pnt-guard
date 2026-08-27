"""
test_unit.py — Unit tests for PNT-Guard detection and fusion logic.

Uses only Python's built-in unittest library. Tests the pure functions
directly without needing a running server or database.
"""

import math
import unittest


class TestHaversine(unittest.TestCase):
    """Tests for the haversine distance calculation."""

    def test_same_point_returns_zero(self):
        from detection import haversine_meters
        d = haversine_meters(37.7749, -122.4194, 37.7749, -122.4194)
        self.assertAlmostEqual(d, 0, places=1)

    def test_known_distance(self):
        """San Francisco to San Jose is roughly 67 km."""
        from detection import haversine_meters
        d = haversine_meters(37.7749, -122.4194, 37.3382, -121.8863)
        self.assertGreater(d, 50_000)   # > 50 km
        self.assertLess(d, 80_000)      # < 80 km

    def test_symmetry(self):
        from detection import haversine_meters
        d1 = haversine_meters(37.7749, -122.4194, 37.3382, -121.8863)
        d2 = haversine_meters(37.3382, -121.8863, 37.7749, -122.4194)
        self.assertAlmostEqual(d1, d2, places=1)

    def test_1km_approximately(self):
        """1 degree latitude ~ 111 km. 0.009 degrees ~ 1 km."""
        from detection import haversine_meters
        d = haversine_meters(37.0, 0.0, 37.009, 0.0)
        self.assertGreater(d, 900)
        self.assertLess(d, 1100)


class TestMedianPosition(unittest.TestCase):
    """Tests for median position computation."""

    def test_single_reading(self):
        from detection import compute_median_position
        lat, lon = compute_median_position([{"lat": 10.0, "lon": 20.0}])
        self.assertEqual(lat, 10.0)
        self.assertEqual(lon, 20.0)

    def test_two_readings_averages(self):
        from detection import compute_median_position
        lat, lon = compute_median_position([
            {"lat": 10.0, "lon": 20.0},
            {"lat": 12.0, "lon": 24.0},
        ])
        self.assertEqual(lat, 11.0)
        self.assertEqual(lon, 22.0)

    def test_three_readings_picks_middle(self):
        from detection import compute_median_position
        lat, lon = compute_median_position([
            {"lat": 10.0, "lon": 20.0},
            {"lat": 50.0, "lon": 60.0},
            {"lat": 30.0, "lon": 40.0},
        ])
        self.assertEqual(lat, 30.0)
        self.assertEqual(lon, 40.0)

    def test_outlier_does_not_affect_median(self):
        """Median should be robust to a single outlier."""
        from detection import compute_median_position
        readings = [
            {"lat": 37.774, "lon": -122.419},
            {"lat": 37.775, "lon": -122.420},
            {"lat": 37.776, "lon": -122.418},
            {"lat": 50.000, "lon": -100.000},  # huge outlier
        ]
        lat, lon = compute_median_position(readings)
        # Median should be near 37.775, not pulled toward 50.0
        self.assertAlmostEqual(lat, 37.775, places=2)
        self.assertAlmostEqual(lon, -122.419, places=1)


class TestDistanceDeviation(unittest.TestCase):
    """Tests for the distance deviation anomaly check."""

    def test_no_flag_when_close(self):
        from detection import check_distance_deviation
        readings = [
            {"id": 1, "source_id": "a", "lat": 37.7749, "lon": -122.4194},
            {"id": 2, "source_id": "b", "lat": 37.7750, "lon": -122.4195},
            {"id": 3, "source_id": "c", "lat": 37.7748, "lon": -122.4193},
        ]
        flagged = check_distance_deviation(readings, threshold_m=500)
        self.assertEqual(len(flagged), 0)

    def test_flags_distant_source(self):
        from detection import check_distance_deviation
        readings = [
            {"id": 1, "source_id": "a", "lat": 37.7749, "lon": -122.4194},
            {"id": 2, "source_id": "b", "lat": 37.7750, "lon": -122.4195},
            {"id": 3, "source_id": "c", "lat": 38.0000, "lon": -122.0000},  # ~30 km away
        ]
        flagged = check_distance_deviation(readings, threshold_m=500)
        self.assertIn("c", flagged)
        self.assertNotIn("a", flagged)
        self.assertNotIn("b", flagged)

    def test_no_flag_with_single_source(self):
        """Can't compute deviation with fewer than 2 sources."""
        from detection import check_distance_deviation
        readings = [
            {"id": 1, "source_id": "a", "lat": 37.7749, "lon": -122.4194},
        ]
        flagged = check_distance_deviation(readings, threshold_m=500)
        self.assertEqual(len(flagged), 0)

    def test_custom_threshold(self):
        """With a very tight threshold, even small differences should flag."""
        from detection import check_distance_deviation
        readings = [
            {"id": 1, "source_id": "a", "lat": 37.7740, "lon": -122.4190},
            {"id": 2, "source_id": "b", "lat": 37.7760, "lon": -122.4200},
        ]
        # These are ~200m apart; flag with 100m threshold
        flagged = check_distance_deviation(readings, threshold_m=100)
        self.assertEqual(len(flagged), 2)  # Both deviate from median


class TestFusePosition(unittest.TestCase):
    """Tests for the fusion logic (uses a test database)."""

    def setUp(self):
        """Create a fresh in-memory DB for each test."""
        import os
        os.environ["PNT_GUARD_DB"] = ":memory:"
        # Force reimport to pick up new DB_PATH
        import models
        models.DB_PATH = ":memory:"
        models._local.conn = None
        models.init_db()

    def _insert(self, source_id, lat, lon, ts, status="ok"):
        import models
        return models.insert_reading(source_id, lat, lon, ts, status)

    def test_fusion_with_ok_sources(self):
        from fusion import fuse_position
        self._insert("a", 37.7749, -122.4194, 1000)
        self._insert("b", 37.7750, -122.4195, 1001)
        self._insert("c", 37.7748, -122.4193, 1002)

        result = fuse_position()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["sources_used"]), 3)
        self.assertEqual(len(result["sources_flagged"]), 0)

    def test_fusion_excludes_anomalous(self):
        from fusion import fuse_position
        rid_a = self._insert("a", 37.7749, -122.4194, 1000)
        self._insert("b", 37.7750, -122.4195, 1001)
        self._insert("c", 37.7748, -122.4193, 1002)
        # Mark 'a' as anomalous
        from models import mark_reading_anomalous
        mark_reading_anomalous(rid_a)

        result = fuse_position()
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("a", result["sources_used"])
        self.assertIn("a", result["sources_flagged"])

    def test_fusion_all_anomalous(self):
        from fusion import fuse_position
        rid_a = self._insert("a", 37.7749, -122.4194, 1000)
        rid_b = self._insert("b", 37.7750, -122.4195, 1001)
        from models import mark_reading_anomalous
        mark_reading_anomalous(rid_a)
        mark_reading_anomalous(rid_b)

        result = fuse_position()
        self.assertEqual(result["status"], "no_reliable_position")
        self.assertEqual(result["reason"], "all_sources_flagged")

    def test_fusion_no_readings(self):
        from fusion import fuse_position
        result = fuse_position()
        self.assertEqual(result["status"], "no_reliable_position")
        self.assertEqual(result["reason"], "no_readings")

    def test_fusion_uses_median(self):
        """Fused position should be the median of valid sources."""
        from fusion import fuse_position
        self._insert("a", 37.774, -122.419, 1000)
        self._insert("b", 37.776, -122.421, 1001)
        self._insert("c", 37.775, -122.420, 1002)

        result = fuse_position()
        self.assertEqual(result["status"], "ok")
        # Median of 37.774, 37.775, 37.776 is 37.775
        self.assertAlmostEqual(result["lat"], 37.775, places=3)
        # Median of -122.421, -122.420, -122.419 is -122.420
        self.assertAlmostEqual(result["lon"], -122.420, places=3)


class TestConfig(unittest.TestCase):
    """Tests that config values are accessible and sensible."""

    def test_config_loads(self):
        import config
        self.assertGreater(config.DISTANCE_THRESHOLD_M, 0)
        self.assertGreater(config.VELOCITY_THRESHOLD_MS, 0)
        self.assertGreater(config.SIMULATOR_INTERVAL_S, 0)
        self.assertGreaterEqual(config.SIMULATOR_ANOMALY_RATE, 0)
        self.assertLessEqual(config.SIMULATOR_ANOMALY_RATE, 1)


if __name__ == "__main__":
    unittest.main()
