# Fire Weather data and service contract

## Data path

Each MQTT message represents one raw weather observation. It contains identifiers, time, and sensor measurements only. It does not contain scenario, severity, risk, outlier, quality, or status labels.

After receipt, the subscriber validates the measurements, derives data quality, assigns a test-profile scenario from the measurements, calculates the transparent screening risk, and writes two PostgreSQL records in one transaction:

- `jena_telemetry` stores the original JSON payload for audit plus downstream database fields.
- `fire_weather_events` stores the flattened dashboard record.

The dashboard API and ML context lookup are read-only PostgreSQL consumers.

## Raw MQTT fields

| Field | Meaning |
| --- | --- |
| `schema_version` | Payload contract version |
| `event_id` | UUID used for duplicate-safe delivery |
| `device_id` | Weather-node identifier |
| `timestamp` | Timezone-aware ISO-8601 observation time |
| `temperature` | Degrees Celsius |
| `pressure_mbar` | Barometric pressure in mbar |
| `humidity` | Relative humidity percent; nullable for a simulated sensor fault |
| `wind_speed_ms`, `wind_gust_ms` | Sustained wind and gust in m/s |
| `wind_dir_deg` | Direction in degrees |
| `air_density` | g/m3 |
| `fuel_moisture_pct` | Synthetic fine-fuel moisture proxy, not a sensor reading |

## Subscriber-derived fields

The subscriber adds `scenario`, `data_quality`, `failure_point`, `status`, `severity`, `is_outlier`, `risk_score`, and `risk_level` to database-facing records. The 0-100 score is an explainable project screening metric, not an official Fire Weather Index.

## Read-only dashboard API

- `GET /api/fire/health` - PostgreSQL availability.
- `GET /api/fire/telemetry?window=24h&scenario=all&limit=5000` - filtered analytics rows and summary.
- `GET /api/fire/stream?limit=30` - newest persisted rows in descending observation order.
- `GET /api/fire/stream/live?after_id=...` - persistent Server-Sent Events connection for newly committed rows.
- `GET /api/ml/health` and `POST /api/ml/predict` - same-origin relay to the standalone Flask service.

## Standalone ML API

`GET http://127.0.0.1:5001/health`

`POST http://127.0.0.1:5001/predict`

```json
{
  "model": "humidity_regression",
  "event": {
    "device_id": "jena_weather_node_01",
    "timestamp": "2026-08-03T20:00:00Z",
    "temperature": 32.0,
    "pressure_mbar": 995.0
  }
}
```

Valid model names are `humidity_regression`, `low_humidity_classifier`, and `pressure_risk_classifier`. A dashboard request always contains one current event. The pressure-risk task retrieves the preceding valid PostgreSQL event and calculates mbar/hour before inference.
