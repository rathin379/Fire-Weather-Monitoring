#!/usr/bin/env python3
"""Publish realistic, repeatable Fire Weather demo events to MQTT."""
from __future__ import annotations

import argparse
import json
import random
import time
import uuid
from collections import Counter
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import paho.mqtt.client as mqtt

from risk_engine import SCENARIOS, assess_fire_weather, canonical_scenario, classify_scenario

DEFAULT_BROKER = "localhost"
DEFAULT_PORT = 1883
DEFAULT_TOPIC = "devices/telemetry"
DEVICE_ID = "jena_weather_node_01"


def _round(value: float) -> float:
    """Keep generated sensor values readable and consistent."""
    return round(value, 2)


def _pick_scenario(requested: str, rng: random.Random) -> str:
    """Choose one realistic profile when mixed mode is requested."""
    if requested != "mixed":
        return requested
    roll = rng.random()
    if roll < 0.03:
        return "sensor_fault"
    if roll < 0.10:
        return "red_flag"
    if roll < 0.30:
        return "elevated_dry"
    return "normal"


def _normal_values(rng: random.Random) -> dict[str, float]:
    """Create measurements for ordinary weather conditions."""
    temperature = _round(rng.uniform(16.0, 27.0))
    humidity = _round(max(42.0, min(78.0, 74.0 - (temperature - 16.0) * 1.7 + rng.uniform(-5.0, 5.0))))
    wind = _round(rng.uniform(0.8, 5.5))
    return {
        "temperature": temperature,
        "pressure_mbar": _round(rng.uniform(990.0, 1024.0)),
        "humidity": humidity,
        "wind_speed_ms": wind,
        "wind_gust_ms": _round(wind + rng.uniform(0.3, 2.5)),
        "wind_dir_deg": _round(rng.uniform(0.0, 359.9)),
        "fuel_moisture_pct": _round(rng.uniform(18.0, 30.0)),
    }


def _scenario_values(scenario: str, rng: random.Random) -> dict[str, Any]:
    """Create measurements that match the selected demo condition."""
    if scenario == "normal":
        return _normal_values(rng)
    if scenario == "elevated_dry":
        wind = _round(rng.uniform(6.0, 11.0))
        return {
            "temperature": _round(rng.uniform(27.0, 35.0)),
            "pressure_mbar": _round(rng.uniform(988.0, 1020.0)),
            "humidity": _round(rng.uniform(18.0, 35.0)),
            "wind_speed_ms": wind,
            "wind_gust_ms": _round(wind + rng.uniform(1.5, 4.5)),
            "wind_dir_deg": _round(rng.uniform(0.0, 359.9)),
            "fuel_moisture_pct": _round(rng.uniform(8.0, 15.0)),
        }
    if scenario == "red_flag":
        wind = _round(rng.uniform(10.0, 18.0))
        return {
            "temperature": _round(rng.uniform(32.0, 42.0)),
            "pressure_mbar": _round(rng.uniform(985.0, 1018.0)),
            "humidity": _round(rng.uniform(5.0, 15.0)),
            "wind_speed_ms": wind,
            "wind_gust_ms": _round(wind + rng.uniform(4.0, 9.0)),
            "wind_dir_deg": _round(rng.uniform(0.0, 359.9)),
            "fuel_moisture_pct": _round(rng.uniform(3.0, 8.0)),
        }
    if scenario == "sensor_fault":
        values = _normal_values(rng)
        values.update({"humidity": None, "wind_speed_ms": None, "wind_gust_ms": None, "fuel_moisture_pct": None})
        return values
    raise ValueError(f"Unsupported scenario: {scenario}")


def _historical_timestamps(
    count: int,
    days: int,
    end: datetime,
    rng: random.Random,
) -> Iterator[datetime]:
    """Spread timestamps across the requested historical window."""
    start = end - timedelta(days=days)
    window = end - start
    for index in range(count):
        # Use one random point inside each bucket so a large backfill has a
        # realistic spread instead of clustering at one end of the window.
        position = (index + rng.random()) / count
        yield start + (window * position)


def generate_jena_telemetry(
    scenario: str = "mixed",
    rng: random.Random | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Create one raw sensor event; scenario only shapes values and is not emitted."""
    rng = rng or random.Random()
    requested = canonical_scenario(scenario)
    resolved = _pick_scenario(requested, rng)
    values = _scenario_values(resolved, rng)
    temperature = float(values["temperature"])
    pressure = float(values["pressure_mbar"])
    air_density = _round((pressure * 100.0) / (287.05 * (temperature + 273.15)) * 1000.0)
    return {
        "schema_version": "2.0",
        "event_id": str(uuid.uuid4()),
        "device_id": DEVICE_ID,
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        **values,
        "air_density": air_density,
    }


def _summary(event: dict[str, Any]) -> str:
    """Describe downstream classification without changing the raw event."""
    scenario = classify_scenario(event)
    quality = "invalid" if scenario == "sensor_fault" else "valid"
    assessment = assess_fire_weather({**event, "data_quality": quality})
    score = "n/a" if assessment["risk_score"] is None else f"{assessment['risk_score']:.1f}"
    return f"derived_scenario={scenario} risk={assessment['risk_level']} score={score} status={assessment['status']}"


def publish_events(args: argparse.Namespace) -> None:
    """Generate events, publish them to MQTT, and print a short run summary."""
    rng = random.Random(args.seed)
    scenario = canonical_scenario(args.scenario)
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    published: Counter[str] = Counter()
    failures = 0
    start = time.perf_counter()
    historical_timestamps: Iterator[datetime] | None = None
    if args.historical:
        historical_end = datetime.now(timezone.utc)
        historical_start = historical_end - timedelta(days=args.days)
        historical_timestamps = _historical_timestamps(args.count, args.days, historical_end, rng)
        print(
            f"[GENERATOR] Historical window: {historical_start.isoformat()} "
            f"to {historical_end.isoformat()}"
        )
    try:
        client.connect(args.broker, args.port, 60)
        client.loop_start()
        print(f"[GENERATOR] Connected to MQTT {args.broker}:{args.port}; topic={args.topic}")
        index = 0
        while args.count == 0 or index < args.count:
            timestamp = next(historical_timestamps) if historical_timestamps is not None else None
            event = generate_jena_telemetry(scenario, rng, timestamp=timestamp)
            info = client.publish(args.topic, json.dumps(event), qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                failures += 1
            else:
                info.wait_for_publish()
                published[classify_scenario(event)] += 1
            index += 1
            if args.verbose:
                print(f"[PUBLISHED] {event['event_id']} {_summary(event)}")
            elif index % args.summary_every == 0:
                print(f"[PROGRESS] published={index} scenarios={dict(published)} failures={failures}")
            if args.count == 0:
                time.sleep(args.interval / 1000.0)
    except KeyboardInterrupt:
        print("[GENERATOR] Stopped by user.")
    finally:
        elapsed = time.perf_counter() - start
        if client.is_connected():
            client.loop_stop()
            client.disconnect()
        total = sum(published.values())
        rate = total / elapsed if elapsed else 0.0
        print(f"[SUMMARY] published={total} failures={failures} elapsed={elapsed:.2f}s rate={rate:.1f}/s scenarios={dict(published)}")


def main() -> None:
    """Read command-line options and start the generator."""
    parser = argparse.ArgumentParser(description="Publish Fire Weather telemetry scenarios through MQTT.")
    parser.add_argument("-s", "--scenario", default="mixed", choices=(*SCENARIOS, "outlier", "failure"), help="Scenario to generate; outlier/failure remain supported aliases.")
    parser.add_argument("-c", "--count", type=int, default=0, help="Number of events to publish (0 streams until Ctrl+C).")
    parser.add_argument("-i", "--interval", type=int, default=1000, help="Streaming interval in milliseconds (default: 1000).")
    parser.add_argument("--summary-every", type=int, default=25, help="Progress interval when not verbose (default: 25).")
    parser.add_argument("--verbose", action="store_true", help="Print every generated event.")
    parser.add_argument("-q", "--quiet", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, help="Optional seed for a reproducible scenario run.")
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Spread a finite run across the previous --days instead of using the current time.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Historical window in days when --historical is used (default: 30).",
    )
    parser.add_argument("--broker", default=DEFAULT_BROKER)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    args = parser.parse_args()
    if args.count < 0 or args.interval < 1 or args.summary_every < 1 or args.days < 1:
        parser.error("count must be non-negative; interval, summary-every, and days must be positive")
    if args.historical and args.count == 0:
        parser.error("--historical requires --count greater than 0")
    if args.quiet:
        args.verbose = False
        args.summary_every = max(args.summary_every, 10_000_000)
    publish_events(args)


if __name__ == "__main__":
    main()
