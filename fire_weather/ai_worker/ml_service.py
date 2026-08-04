#!/usr/bin/env python3
"""Standalone Flask service for one-event Fire Weather ML inference."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import psycopg2
from flask import Flask, jsonify, request

MODEL_DIR = Path(os.getenv("FIRE_ML_MODEL_DIR", Path(__file__).resolve().parent / "models"))
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "dbname=iot_platform user=postgres host=localhost port=5432")
HOST = os.getenv("FIRE_ML_HOST", "127.0.0.1")
PORT = int(os.getenv("FIRE_ML_PORT", "5001"))
ALLOWED_ORIGINS = {"http://127.0.0.1:8000", "http://localhost:8000"}
TASKS = {
    "humidity_regression": "Predict relative humidity",
    "low_humidity_classifier": "Predict humidity below 30 percent",
    "pressure_risk_classifier": "Predict pressure-drop fire-risk signal",
}


class PredictionError(ValueError):
    """A safe, user-facing inference error."""


def parse_number(event: dict[str, Any], field: str, minimum: float, maximum: float) -> float:
    try:
        value = float(event[field])
    except (KeyError, TypeError, ValueError) as error:
        raise PredictionError(f"{field} must be a number") from error
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise PredictionError(f"{field} must be between {minimum:g} and {maximum:g}")
    return value


def parse_timestamp(value: Any) -> datetime:
    if value in (None, ""):
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise PredictionError("timestamp must be an ISO-8601 date and time") from error
    if parsed.tzinfo is None:
        raise PredictionError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def load_models(model_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = model_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Model manifest not found: {manifest_path}. Run train_models.py first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    models: dict[str, Any] = {}
    for task in TASKS:
        details = manifest.get("tasks", {}).get(task)
        if not details or not details.get("file"):
            raise RuntimeError(f"Model manifest is missing task: {task}")
        bundle = joblib.load(model_dir / details["file"])
        if bundle.get("task") != task or "model" not in bundle:
            raise RuntimeError(f"Invalid model bundle for task: {task}")
        models[task] = bundle
    return manifest, models


def find_previous_pressure(device_id: str, observed_at: datetime) -> dict[str, Any]:
    query = """
        SELECT pressure_mbar, observed_at
        FROM fire_weather_events
        WHERE device_id = %s
          AND observed_at < %s
          AND pressure_mbar IS NOT NULL
          AND data_quality = 'valid'
        ORDER BY observed_at DESC
        LIMIT 1
    """
    try:
        with psycopg2.connect(POSTGRES_DSN) as connection, connection.cursor() as cursor:
            cursor.execute(query, (device_id, observed_at))
            row = cursor.fetchone()
    except psycopg2.Error as error:
        raise PredictionError("PostgreSQL is unavailable; pressure-risk context could not be loaded") from error
    if row is None:
        raise PredictionError(f"No earlier valid pressure event exists for device {device_id}")
    return {"pressure_mbar": float(row[0]), "timestamp": row[1]}


def pressure_rate_for_event(
    event: dict[str, Any], current_pressure: float, observed_at: datetime
) -> tuple[float, dict[str, Any]]:
    # Automated API tests may provide an explicit rate. The dashboard does not;
    # it exercises the manager-requested PostgreSQL context lookup.
    explicit = event.get("pressure_rate_mbar_per_hour")
    if explicit not in (None, ""):
        rate = parse_number(event, "pressure_rate_mbar_per_hour", -5000, 5000)
        return rate, {"source": "request", "pressure_rate_mbar_per_hour": rate}
    device_id = str(event.get("device_id") or "jena_weather_node_01").strip()
    if not device_id:
        raise PredictionError("device_id cannot be blank")
    previous = find_previous_pressure(device_id, observed_at)
    previous_time = previous["timestamp"]
    if previous_time.tzinfo is None:
        previous_time = previous_time.replace(tzinfo=timezone.utc)
    elapsed_hours = (observed_at - previous_time.astimezone(timezone.utc)).total_seconds() / 3600
    if elapsed_hours <= 0:
        raise PredictionError("The previous database event must be older than the submitted event")
    rate = (current_pressure - previous["pressure_mbar"]) / elapsed_hours
    return rate, {
        "source": "PostgreSQL",
        "device_id": device_id,
        "previous_pressure_mbar": round(previous["pressure_mbar"], 4),
        "previous_timestamp": previous_time.isoformat(),
        "elapsed_hours": round(elapsed_hours, 6),
        "pressure_rate_mbar_per_hour": round(rate, 4),
    }


def make_prediction(models: dict[str, Any], task: str, event: dict[str, Any]) -> dict[str, Any]:
    if task not in TASKS:
        raise PredictionError(f"model must be one of: {', '.join(TASKS)}")
    temperature = parse_number(event, "temperature", -80, 60)
    pressure = parse_number(event, "pressure_mbar", 800, 1100)
    observed_at = parse_timestamp(event.get("timestamp"))
    bundle = models[task]
    model = bundle["model"]
    context: dict[str, Any] = {}

    if task == "humidity_regression":
        raw_value = float(model.predict([[temperature, pressure]])[0])
        value = min(100.0, max(0.0, raw_value))
        prediction = {
            "label": "Predicted relative humidity",
            "value": round(value, 2),
            "unit": "%",
            "interpretation": "Estimated humidity from the submitted temperature and pressure.",
        }
    elif task == "low_humidity_classifier":
        probability = float(model.predict_proba([[temperature, pressure]])[0][1])
        decision_threshold = float(bundle.get("decision_threshold", 0.5))
        dangerous = probability >= decision_threshold
        prediction = {
            "label": "Dangerous low humidity" if dangerous else "Humidity threshold not predicted",
            "class": int(dangerous),
            "probability": round(probability, 6),
            "probability_pct": round(probability * 100, 2),
            "decision_threshold": round(decision_threshold, 6),
            "interpretation": "Probability that relative humidity is below the project's 30 percent threshold.",
        }
    else:
        rate, context = pressure_rate_for_event(event, pressure, observed_at)
        probability = float(model.predict_proba([[temperature, rate]])[0][1])
        decision_threshold = float(bundle.get("decision_threshold", 0.5))
        risk = probability >= decision_threshold
        prediction = {
            "label": "Pressure-drop risk signal" if risk else "No pressure-drop risk signal",
            "class": int(risk),
            "probability": round(probability, 6),
            "probability_pct": round(probability * 100, 2),
            "decision_threshold": round(decision_threshold, 6),
            "interpretation": "Exploratory probability based on temperature and pressure change per hour; not an official fire warning.",
        }

    return {
        "status": "ok",
        "task": task,
        "task_name": TASKS[task],
        "model_version": bundle.get("model_version", "unknown"),
        "event": {
            "device_id": str(event.get("device_id") or "jena_weather_node_01"),
            "timestamp": observed_at.isoformat(),
            "temperature": temperature,
            "pressure_mbar": pressure,
        },
        "prediction": prediction,
        "context": context,
    }


def create_app(model_dir: Path = MODEL_DIR) -> Flask:
    app = Flask(__name__)
    manifest, models = load_models(model_dir)
    app.config["MODEL_MANIFEST"] = manifest
    app.config["MODELS"] = models

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "fire-weather-ml",
            "model_version": manifest.get("model_version"),
            "models": list(TASKS),
        })

    @app.route("/predict", methods=["POST", "OPTIONS"])
    def predict():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("event"), dict):
            return jsonify({"status": "error", "error": "Request must contain a JSON event object"}), 400
        task = str(payload.get("model", "")).strip()
        print(f"[ML SERVICE] Event received model={task or 'missing'}")
        try:
            print("[ML SERVICE] Making prediction")
            result = make_prediction(models, task, payload["event"])
        except PredictionError as error:
            print(f"[ML SERVICE] Prediction rejected: {error}")
            return jsonify({"status": "error", "error": str(error)}), 422
        print(f"[ML SERVICE] Prediction={result['prediction']['label']}")
        return jsonify(result)

    return app


def main() -> None:
    print("[ML SERVICE] Starting AI/ML service")
    app = create_app()
    manifest = app.config["MODEL_MANIFEST"]
    print(f"[ML SERVICE] Loaded model version {manifest.get('model_version')} ({len(TASKS)} prediction tasks)")
    print(f"[ML SERVICE] Listening on http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
