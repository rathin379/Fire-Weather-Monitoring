"""Regression tests for the raw MQTT contract and downstream classification."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jena_event_generator import _historical_timestamps, generate_jena_telemetry
from jena_subscriber import validate_event
from risk_engine import classify_scenario


class PipelineContractTests(unittest.TestCase):
    """Protect the boundary between raw MQTT data and derived labels."""
    def test_raw_event_contains_measurements_not_derived_labels(self) -> None:
        event = generate_jena_telemetry("red_flag", random.Random(29))
        for forbidden in ("scenario", "severity", "risk_level", "risk_score", "is_outlier", "status", "data_quality"):
            self.assertNotIn(forbidden, event)
        validate_event(event)
        self.assertEqual(classify_scenario(event), "red_flag")

    def test_sensor_fault_is_derived_from_missing_measurements(self) -> None:
        event = generate_jena_telemetry("sensor_fault", random.Random(29))
        validate_event(event)
        self.assertEqual(classify_scenario(event), "sensor_fault")

    def test_normal_and_elevated_profiles_classify_after_receipt(self) -> None:
        normal = generate_jena_telemetry("normal", random.Random(29))
        elevated = generate_jena_telemetry("elevated_dry", random.Random(29))
        self.assertEqual(classify_scenario(normal), "normal")
        self.assertEqual(classify_scenario(elevated), "elevated_dry")


    def test_historical_timestamps_are_spread_and_accepted(self) -> None:
        end = datetime(2026, 8, 7, tzinfo=timezone.utc)
        timestamps = list(_historical_timestamps(100, 30, end, random.Random(29)))

        self.assertEqual(len(timestamps), 100)
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertGreaterEqual(timestamps[0], end - timedelta(days=30))
        self.assertLess(timestamps[-1], end)

        event = generate_jena_telemetry("normal", random.Random(29), timestamp=timestamps[0])
        validate_event(event)
        self.assertEqual(event["timestamp"], timestamps[0].isoformat())

if __name__ == "__main__":
    unittest.main()
