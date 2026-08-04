#!/usr/bin/env python3
"""MQTT subscriber that atomically dual-writes raw and flat Fire Weather events."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import Json

from risk_engine import assess_fire_weather, classify_scenario, is_number

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "devices/telemetry")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "dbname=iot_platform user=postgres host=localhost port=5432")

REQUIRED_FIELDS = {
    "event_id", "device_id", "timestamp", "temperature", "pressure_mbar", "humidity",
    "wind_speed_ms", "wind_gust_ms", "wind_dir_deg", "air_density", "fuel_moisture_pct",
}
NULLABLE_MEASUREMENTS = {"humidity", "wind_speed_ms", "wind_gust_ms", "fuel_moisture_pct"}


def validate_event(event: dict[str, Any]) -> None:
    """Reject a raw MQTT event when required IDs or measurements are invalid."""
    missing = REQUIRED_FIELDS - event.keys()
    if missing:
        raise ValueError(f"Missing fields: {', '.join(sorted(missing))}")
    uuid.UUID(str(event["event_id"]))
    datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
    if not str(event["device_id"]).strip():
        raise ValueError("device_id cannot be blank")
    for field in ("temperature", "pressure_mbar", "humidity", "wind_speed_ms", "wind_gust_ms", "wind_dir_deg", "air_density", "fuel_moisture_pct"):
        value = event[field]
        if value is None and field in NULLABLE_MEASUREMENTS:
            continue
        if not is_number(value):
            raise ValueError(f"{field} must be a finite number")
    if is_number(event["humidity"]) and not 0 <= float(event["humidity"]) <= 100:
        raise ValueError("humidity must be between 0 and 100")
    if is_number(event["wind_dir_deg"]) and not 0 <= float(event["wind_dir_deg"]) < 360:
        raise ValueError("wind_dir_deg must be between 0 and 360")


def persist_event(event: dict[str, Any], topic: str = MQTT_TOPIC) -> bool:
    """Classify one valid raw event and save the raw and dashboard-ready rows."""
    scenario = classify_scenario(event)
    data_quality = "invalid" if scenario == "sensor_fault" else "valid"
    failure_point = "humidity_wind_anemometer" if scenario == "sensor_fault" else None
    assessment = assess_fire_weather({**event, "data_quality": data_quality})
    raw_insert = """
        INSERT INTO jena_telemetry (
            event_id, device_id, timestamp, temperature, pressure_mbar, humidity,
            wind_speed_ms, wind_gust_ms, wind_dir_deg, air_density, fuel_moisture_pct,
            status, scenario, severity, failure_point, is_outlier, data_quality,
            mqtt_topic, payload
        ) VALUES (
            %(event_id)s, %(device_id)s, %(timestamp)s, %(temperature)s, %(pressure_mbar)s, %(humidity)s,
            %(wind_speed_ms)s, %(wind_gust_ms)s, %(wind_dir_deg)s, %(air_density)s, %(fuel_moisture_pct)s,
            %(raw_status)s, %(scenario)s, %(severity)s, %(failure_point)s, %(is_outlier)s, %(data_quality)s,
            %(mqtt_topic)s, %(payload)s
        ) ON CONFLICT (event_id) DO NOTHING RETURNING id;
    """
    flat_insert = """
        INSERT INTO fire_weather_events (
            event_id, device_id, observed_at, temperature, pressure_mbar, humidity,
            wind_speed_ms, wind_gust_ms, wind_dir_deg, air_density, fuel_moisture_pct,
            status, scenario, severity, failure_point, data_quality, is_outlier,
            risk_score, risk_level
        ) VALUES (
            %(event_id)s, %(device_id)s, %(timestamp)s, %(temperature)s, %(pressure_mbar)s, %(humidity)s,
            %(wind_speed_ms)s, %(wind_gust_ms)s, %(wind_dir_deg)s, %(air_density)s, %(fuel_moisture_pct)s,
            %(status)s, %(scenario)s, %(severity)s, %(failure_point)s, %(data_quality)s, %(is_outlier)s,
            %(risk_score)s, %(risk_level)s
        ) ON CONFLICT (event_id) DO NOTHING;
    """
    record = dict(event)
    record["scenario"] = scenario
    record["data_quality"] = data_quality
    record["failure_point"] = failure_point
    record["raw_status"] = "SENSOR_FAULT" if data_quality == "invalid" else "OK"
    record.update(assessment)
    record["mqtt_topic"] = topic
    record["payload"] = Json(event)
    with psycopg2.connect(POSTGRES_DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(raw_insert, record)
            if cursor.fetchone() is None:
                return False
            cursor.execute(flat_insert, record)
    return True


def on_message(_client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
    """Decode each MQTT message and pass it to the database writer."""
    try:
        event = json.loads(message.payload.decode("utf-8"))
        validate_event(event)
        inserted = persist_event(event, message.topic)
        outcome = "INSERTED" if inserted else "DUPLICATE IGNORED"
        print(f"[MQTT->POSTGRES] {outcome} event={event['event_id']} derived_scenario={classify_scenario(event)}")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, psycopg2.Error) as error:
        print(f"[REJECTED] {error}")


def main() -> None:
    """Connect to MQTT and listen until the user stops the program."""
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC, qos=1)
    print(f"[LISTENER] MQTT {MQTT_BROKER}:{MQTT_PORT}; topic={MQTT_TOPIC}; dual-write=enabled")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("[LISTENER] Stopped by user.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
