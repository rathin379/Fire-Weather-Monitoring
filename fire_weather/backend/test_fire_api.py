"""Tests for API filters, PostgreSQL reads, live updates, and ML forwarding."""
from __future__ import annotations

import unittest
from urllib.error import URLError
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.fire_api import (
    build_filters,
    read_events_after_id,
    read_live_stream,
    request_ml_service,
    stream_sse,
)


class FireApiTest(unittest.TestCase):
    """Check the API behavior without requiring live services."""
    def test_invalid_window_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "window must be one of"):
            build_filters({"window": ["yesterday"]})

    def test_custom_range_must_be_ordered(self) -> None:
        with self.assertRaisesRegex(ValueError, "start must be before end"):
            build_filters({
                "window": ["all"],
                "start": ["2026-08-03T12:00:00Z"],
                "end": ["2026-08-03T11:00:00Z"],
            })

    def test_live_stream_returns_newest_persisted_rows(self) -> None:
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.description = [SimpleNamespace(name="event_id")]
        cursor.fetchall.return_value = [("evt-newest",), ("evt-older",)]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        with patch("backend.fire_api.psycopg2.connect", return_value=connection):
            result = read_live_stream({"limit": ["250"]})
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["events"][0]["event_id"], "evt-newest")
        self.assertEqual(cursor.execute.call_args.args[1], [100])
        self.assertIn("ORDER BY observed_at DESC", cursor.execute.call_args.args[0])

    def test_live_sse_query_reads_only_new_ids(self) -> None:
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.description = [SimpleNamespace(name="id")]
        cursor.fetchall.return_value = [(42,)]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        with patch("backend.fire_api.psycopg2.connect", return_value=connection):
            result = read_events_after_id(41, limit=20)
        self.assertEqual(result, [{"id": 42}])
        self.assertEqual(cursor.execute.call_args.args[1], [41, 20])
        self.assertIn("WHERE id > %s", cursor.execute.call_args.args[0])

    def test_sse_writes_a_named_telemetry_event(self) -> None:
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.description = [SimpleNamespace(name="id"), SimpleNamespace(name="event_id")]
        cursor.fetchall.return_value = [(42, "evt-live")]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        handler = MagicMock()
        with (
            patch("backend.fire_api.psycopg2.connect", return_value=connection),
            patch("backend.fire_api.time.sleep", side_effect=ConnectionResetError),
        ):
            stream_sse(handler, 41)
        output = b"".join(call.args[0] for call in handler.wfile.write.call_args_list)
        self.assertIn(b"event: telemetry", output)
        self.assertIn(b'"event_id":"evt-live"', output)
    def test_ml_proxy_returns_actionable_offline_message(self) -> None:
        with patch("backend.fire_api.urlopen", side_effect=URLError("refused")):
            status, body = request_ml_service("/health")
        self.assertEqual(status, 503)
        self.assertIn("python .\\ai_worker\\ml_service.py", body["error"])
    def test_live_stream_limit_must_be_numeric(self) -> None:
        with self.assertRaisesRegex(ValueError, "limit must be a whole number"):
            read_live_stream({"limit": ["many"]})


if __name__ == "__main__":
    unittest.main()
