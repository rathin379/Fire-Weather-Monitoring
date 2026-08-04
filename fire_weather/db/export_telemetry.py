#!/usr/bin/env python3
"""Export persisted Fire Weather data for dashboard audit or notebook retraining."""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2

import sys

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from risk_engine import jena_compatible_values

DSN = os.getenv("POSTGRES_DSN", "dbname=iot_platform user=postgres host=localhost port=5432")

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "exports" / "jena_retraining_export.csv"
JENA_HEADERS = [
    "Date Time", "p (mbar)", "T (degC)", "Tpot (K)", "Tdew (degC)", "rh (%)",
    "VPmax (mbar)", "VPact (mbar)", "VPdef (mbar)", "sh (g/kg)",
    "H2OC (mmol/mol)", "rho (g/m**3)", "wv (m/s)", "max. wv (m/s)", "wd (deg)",
]
FLAT_HEADERS = [
    "event_id", "device_id", "observed_at", "temperature", "pressure_mbar", "humidity",
    "wind_speed_ms", "wind_gust_ms", "wind_dir_deg", "air_density", "fuel_moisture_pct",
    "status", "scenario", "severity", "failure_point", "data_quality", "is_outlier",
    "risk_score", "risk_level",
]
QUERY = """
    SELECT event_id, device_id, observed_at, temperature, pressure_mbar, humidity,
           wind_speed_ms, wind_gust_ms, wind_dir_deg, air_density, fuel_moisture_pct,
           status, scenario, severity, failure_point, data_quality, is_outlier,
           risk_score, risk_level
    FROM fire_weather_events
    WHERE data_quality = 'valid'
    ORDER BY observed_at ASC
"""


def format_number(value: Any) -> str:
    """Format a database number without unnecessary trailing zeroes."""
    if value is None:
        return ""
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def jena_row(event: dict[str, Any]) -> list[str]:
    """Convert one stored event to the column order used by the Jena dataset."""
    derived = jena_compatible_values(event)
    observed_at = event["observed_at"]
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    return [
        observed_at.strftime("%d.%m.%Y %H:%M:%S"),
        format_number(event["pressure_mbar"]),
        format_number(event["temperature"]),
        format_number(derived["Tpot (K)"]),
        format_number(derived["Tdew (degC)"]),
        format_number(event["humidity"]),
        format_number(derived["VPmax (mbar)"]),
        format_number(derived["VPact (mbar)"]),
        format_number(derived["VPdef (mbar)"]),
        format_number(derived["sh (g/kg)"]),
        format_number(derived["H2OC (mmol/mol)"]),
        format_number(event["air_density"]),
        format_number(event["wind_speed_ms"]),
        format_number(event["wind_gust_ms"]),
        format_number(event["wind_dir_deg"]),
    ]


def fetch_events() -> list[dict[str, Any]]:
    """Read valid events in timestamp order for a consistent export."""
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute(QUERY)
        names = [column.name for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def main() -> None:
    """Export either an ML-ready CSV or a full audit CSV."""
    parser = argparse.ArgumentParser(description="Export persisted Fire Weather data.")
    parser.add_argument("--format", choices=("ml", "flat"), default="ml", help="ml matches the Jena notebook header exactly; flat is an auditable event export.")
    parser.add_argument("--output", type=Path, default=Path(os.getenv("FIRE_EXPORT_PATH", DEFAULT_OUTPUT)))
    args = parser.parse_args()
    events = fetch_events()
    if not events:
        raise SystemExit("No valid Fire Weather events exist. Generate and ingest a scenario before exporting.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    headers = JENA_HEADERS if args.format == "ml" else FLAT_HEADERS
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        if args.format == "ml":
            writer.writerows(jena_row(event) for event in events)
        else:
            writer.writerows([[event.get(header, "") for header in FLAT_HEADERS] for event in events])
    print(f"[EXPORT] rows={len(events)} format={args.format} path={args.output.resolve()}")
    if args.format == "ml":
        print("[EXPORT] Sensor-fault rows are intentionally excluded because the existing notebooks require numeric features.")


if __name__ == "__main__":
    main()
