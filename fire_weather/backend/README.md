# Fire Weather backend

This folder contains the non-UI middleware:

- `jena_event_generator.py`: publishes repeatable raw weather events to MQTT.
- `jena_subscriber.py`: validates each event and atomically writes raw JSON plus a flattened PostgreSQL row.
- `fire_api.py`: serves the dashboard, read-only JSON endpoints, and the server-sent event stream.
- `risk_engine.py`: derives scenario, risk, severity, and outlier interpretations downstream.
- `test_fire_api.py` and `test_pipeline_contract.py`: regression tests.

From the project root, start the subscriber and API in separate terminals:

```powershell
python .\backend\jena_subscriber.py
python .\backend\fire_api.py
```

Generate a finite demonstration:

```powershell
python .\backend\jena_event_generator.py --scenario mixed --count 300 --seed 29
```

Optional historical backfill:

```powershell
python .\backend\jena_event_generator.py --historical --days 30 --count 10000
```

Database setup/report/export programs are deliberately in `../db`. Full setup, reset, and verification instructions are in `../README.md`.