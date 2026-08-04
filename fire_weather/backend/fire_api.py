#!/usr/bin/env python3
"""Read-only HTTP API and static server for the Fire Weather dashboard."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
DSN = os.getenv("POSTGRES_DSN", "dbname=iot_platform user=postgres host=localhost port=5432")
PORT = int(os.getenv("FIRE_DASHBOARD_PORT", "8000"))
ML_SERVICE_URL = os.getenv("FIRE_ML_SERVICE_URL", "http://127.0.0.1:5001").rstrip("/")
STREAM_POLL_SECONDS = float(os.getenv("FIRE_STREAM_POLL_SECONDS", "0.25"))
WINDOWS = {
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}
COLUMNS = """
    id, event_id, device_id, observed_at AS timestamp, received_at, temperature,
    pressure_mbar, humidity, wind_speed_ms, wind_gust_ms, wind_dir_deg,
    air_density, fuel_moisture_pct, status, scenario, severity, failure_point,
    data_quality, is_outlier, risk_score, risk_level
"""


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict) -> None:
    """Send one JSON response with the headers used by every API route."""
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_iso_datetime(value: str, name: str) -> datetime:
    """Read an ISO timestamp from a filter and convert it to UTC."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_filters(params: dict[str, list[str]]) -> tuple[str, list[object], dict[str, str | None]]:
    """Turn dashboard filters into a safe SQL WHERE clause and parameter list."""
    window = params.get("window", ["24h"])[0].lower()
    if window not in WINDOWS:
        raise ValueError(f"window must be one of: {', '.join(WINDOWS)}")
    scenario = params.get("scenario", ["all"])[0].lower()
    start = parse_iso_datetime(params["start"][0], "start") if "start" in params else None
    end = parse_iso_datetime(params["end"][0], "end") if "end" in params else None
    if start is None and WINDOWS[window] is not None:
        start = datetime.now(timezone.utc) - WINDOWS[window]
    if start and end and start > end:
        raise ValueError("start must be before end")
    clauses: list[str] = []
    values: list[object] = []
    if start:
        clauses.append("observed_at >= %s")
        values.append(start)
    if end:
        clauses.append("observed_at <= %s")
        values.append(end)
    if scenario != "all":
        clauses.append("scenario = %s")
        values.append(scenario)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, values, {
        "window": window,
        "scenario": scenario,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
    }


def read_events(params: dict[str, list[str]]) -> dict:
    """Read selected historical events and calculate their summary values."""
    limit = max(1, min(int(params.get("limit", ["1000"])[0]), 5000))
    where, values, filters = build_filters(params)
    event_query = f"SELECT {COLUMNS} FROM fire_weather_events {where} ORDER BY observed_at ASC LIMIT %s"
    summary_query = f"""
        SELECT COUNT(*) AS count, MIN(observed_at) AS first_observation, MAX(observed_at) AS last_observation,
               AVG(risk_score) FILTER (WHERE data_quality = 'valid') AS average_risk,
               COUNT(*) FILTER (WHERE risk_level IN ('high', 'extreme')) AS high_risk_events,
               COUNT(*) FILTER (WHERE data_quality = 'invalid') AS invalid_events
        FROM fire_weather_events {where}
    """
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute(event_query, [*values, limit])
        names = [column.name for column in cursor.description]
        events = [dict(zip(names, row)) for row in cursor.fetchall()]
        cursor.execute(summary_query, values)
        summary_names = [column.name for column in cursor.description]
        summary = dict(zip(summary_names, cursor.fetchone()))
    return {"events": events, "count": len(events), "summary": summary, "filters": filters}


def read_live_stream(params: dict[str, list[str]]) -> dict:
    """Return the newest persisted events for the dashboard's live feed."""
    try:
        limit = max(1, min(int(params.get("limit", ["30"])[0]), 100))
    except ValueError as error:
        raise ValueError("limit must be a whole number") from error
    query = f"SELECT {COLUMNS} FROM fire_weather_events ORDER BY observed_at DESC LIMIT %s"
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute(query, [limit])
        names = [column.name for column in cursor.description]
        events = [dict(zip(names, row)) for row in cursor.fetchall()]
    return {
        "events": events,
        "count": len(events),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


def read_events_after_id(after_id: int, limit: int = 100) -> list[dict]:
    """Return newly committed rows in insertion order for the live SSE feed."""
    query = f"SELECT {COLUMNS} FROM fire_weather_events WHERE id > %s ORDER BY id ASC LIMIT %s"
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute(query, [after_id, limit])
        names = [column.name for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def request_ml_service(path: str, method: str = "GET", payload: bytes | None = None) -> tuple[int, dict]:
    """Proxy local ML requests so the browser stays on one origin."""
    request = Request(
        f"{ML_SERVICE_URL}{path}",
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"status": "error", "error": f"ML service returned HTTP {error.code}"}
        return error.code, body
    except (URLError, TimeoutError):
        return 503, {
            "status": "error",
            "error": "ML service is offline. Start it in Terminal 4 with: python .\\ai_worker\\ml_service.py",
        }


def stream_sse(handler: SimpleHTTPRequestHandler, after_id: int) -> None:
    """Keep one HTTP connection open and push committed events as they appear."""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache, no-store")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()
    last_id = after_id
    last_heartbeat = time.monotonic()
    query = f"SELECT {COLUMNS} FROM fire_weather_events WHERE id > %s ORDER BY id ASC LIMIT 100"
    try:
        with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
            connection.autocommit = True
            while True:
                cursor.execute(query, [last_id])
                names = [column.name for column in cursor.description]
                events = [dict(zip(names, row)) for row in cursor.fetchall()]
                for event in events:
                    last_id = max(last_id, int(event["id"]))
                    payload = json.dumps(event, default=str, separators=(",", ":"))
                    handler.wfile.write(f"id: {last_id}\nevent: telemetry\ndata: {payload}\n\n".encode("utf-8"))
                now = time.monotonic()
                if events or now - last_heartbeat >= 10:
                    if not events:
                        handler.wfile.write(b": keep-alive\n\n")
                    handler.wfile.flush()
                    last_heartbeat = now
                time.sleep(STREAM_POLL_SECONDS)
    except (BrokenPipeError, ConnectionResetError):
        return

class Handler(SimpleHTTPRequestHandler):
    """Serve dashboard files and route the read-only API requests."""

    def __init__(self, *args, **kwargs):
        # The browser can only request files from the frontend folder.
        super().__init__(*args, directory=str(FRONTEND_ROOT), **kwargs)

    def do_GET(self) -> None:
        """Handle dashboard reads, health checks, and the live event stream."""
        parsed = urlparse(self.path)
        if parsed.path == "/api/fire/stream/live":
            try:
                after_id = max(0, int(parse_qs(parsed.query).get("after_id", ["0"])[0]))
                stream_sse(self, after_id)
            except ValueError:
                json_response(self, 400, {"error": "after_id must be a whole number"})
            except psycopg2.Error as error:
                print(f"[API] PostgreSQL live connection failed: {error}", file=sys.stderr)
            return
        if parsed.path == "/api/ml/health":
            status, payload = request_ml_service("/health")
            json_response(self, status, payload)
            return
        if parsed.path == "/api/fire/telemetry":
            try:
                json_response(self, 200, read_events(parse_qs(parsed.query)))
            except ValueError as error:
                json_response(self, 400, {"error": str(error)})
            except psycopg2.Error as error:
                print(f"[API] PostgreSQL query failed: {error}", file=sys.stderr)
                json_response(self, 503, {"error": "PostgreSQL connection failed. Verify POSTGRES_DSN, the database name, username, password, host, and port, then restart fire_api.py."})
            return
        if parsed.path == "/api/fire/stream":
            try:
                json_response(self, 200, read_live_stream(parse_qs(parsed.query)))
            except ValueError as error:
                json_response(self, 400, {"error": str(error)})
            except psycopg2.Error as error:
                print(f"[API] PostgreSQL stream query failed: {error}", file=sys.stderr)
                json_response(self, 503, {"error": "PostgreSQL connection failed. Verify POSTGRES_DSN, the database name, username, password, host, and port, then restart fire_api.py."})
            return
        if parsed.path == "/api/fire/health":
            try:
                with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                json_response(self, 200, {"status": "ok"})
            except psycopg2.Error:
                json_response(self, 503, {"status": "unavailable"})
            return
        super().do_GET()
    def do_POST(self) -> None:
        """Forward prediction requests to the separate local ML service."""
        parsed = urlparse(self.path)
        if parsed.path != "/api/ml/predict":
            json_response(self, 404, {"error": "Not found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            json_response(self, 400, {"error": "Invalid Content-Length"})
            return
        if content_length < 2 or content_length > 65536:
            json_response(self, 400, {"error": "Prediction request must contain a small JSON body"})
            return
        body = self.rfile.read(content_length)
        status, payload = request_ml_service("/predict", "POST", body)
        json_response(self, status, payload)

if __name__ == "__main__":
    print(f"[DASHBOARD] http://127.0.0.1:{PORT}/domain-fire.html")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
