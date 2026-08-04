#!/usr/bin/env python3
"""Print a concise, time-bounded database verification report for the demo."""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import psycopg2

DSN = os.getenv("POSTGRES_DSN", "dbname=iot_platform user=postgres host=localhost port=5432")
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "all": None}


def main() -> None:
    """Run the standard database checks used during the project demo."""
    parser = argparse.ArgumentParser(description="Verify Fire Weather records in PostgreSQL.")
    parser.add_argument("--window", choices=WINDOWS, default="24h")
    args = parser.parse_args()
    start = datetime.now(timezone.utc) - WINDOWS[args.window] if WINDOWS[args.window] else None
    where = "WHERE observed_at >= %s" if start else ""
    values = [start] if start else []
    summary = f"""
        SELECT COUNT(*) AS events, MIN(observed_at) AS first_event, MAX(observed_at) AS last_event,
               ROUND((AVG(risk_score) FILTER (WHERE data_quality = 'valid'))::numeric, 1) AS avg_risk,
               COUNT(*) FILTER (WHERE risk_level IN ('high', 'extreme')) AS high_or_extreme,
               COUNT(*) FILTER (WHERE data_quality = 'invalid') AS invalid_sensor_events
        FROM fire_weather_events {where}
    """
    scenarios = f"SELECT scenario, COUNT(*) FROM fire_weather_events {where} GROUP BY scenario ORDER BY scenario"
    recent = f"""SELECT observed_at, scenario, risk_level, risk_score, status
                 FROM fire_weather_events {where} ORDER BY observed_at DESC LIMIT 10"""
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute(summary, values)
        row = cursor.fetchone()
        cursor.execute(scenarios, values)
        scenario_rows = cursor.fetchall()
        cursor.execute(recent, values)
        recent_rows = cursor.fetchall()
    print(f"FIRE WEATHER DATABASE CHECK | window={args.window}")
    print(f"events={row[0]} first={row[1]} last={row[2]} avg_risk={row[3]} high_or_extreme={row[4]} invalid_sensor_events={row[5]}")
    print("scenario coverage:")
    for scenario, count in scenario_rows:
        print(f"  {scenario}: {count}")
    print("latest 10:")
    for observed_at, scenario, level, score, status in recent_rows:
        print(f"  {observed_at} | {scenario:12} | {level:8} | score={score} | {status}")


if __name__ == "__main__":
    main()
