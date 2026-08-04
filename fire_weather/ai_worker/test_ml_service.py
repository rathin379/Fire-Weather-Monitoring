from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_worker.ml_service import create_app
from ai_worker.train_models import DEFAULT_DATASET, train_models


class MLServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_models = tempfile.TemporaryDirectory()
        model_dir = Path(cls.temporary_models.name)
        train_models(DEFAULT_DATASET, model_dir, "test", 10_000, 3.0)
        cls.app = create_app(model_dir)
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_models.cleanup()

    def predict(self, model: str, event: dict) -> tuple[int, dict]:
        response = self.client.post("/predict", json={"model": model, "event": event})
        return response.status_code, json.loads(response.data)

    def test_health_lists_three_tasks(self) -> None:
        response = self.client.get("/health")
        body = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(body["models"]), 3)

    def test_humidity_prediction(self) -> None:
        status, body = self.predict("humidity_regression", {"temperature": 30, "pressure_mbar": 1000})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["prediction"]["value"], 0)
        self.assertLessEqual(body["prediction"]["value"], 100)

    def test_low_humidity_prediction(self) -> None:
        status, body = self.predict("low_humidity_classifier", {"temperature": 35, "pressure_mbar": 1000})
        self.assertEqual(status, 200)
        self.assertIn("probability_pct", body["prediction"])
        self.assertIn("decision_threshold", body["prediction"])

    def test_pressure_risk_accepts_one_context_event(self) -> None:
        status, body = self.predict("pressure_risk_classifier", {
            "temperature": 35,
            "pressure_mbar": 995,
            "pressure_rate_mbar_per_hour": -1.5,
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["context"]["source"], "request")

    def test_invalid_event_is_rejected(self) -> None:
        status, body = self.predict("humidity_regression", {"temperature": 500, "pressure_mbar": 1000})
        self.assertEqual(status, 422)
        self.assertEqual(body["status"], "error")


if __name__ == "__main__":
    unittest.main()
