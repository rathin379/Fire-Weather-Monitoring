# Fire Weather Monitoring

This package contains the completed Fire Weather Monitoring internship project. It demonstrates a database-backed IoT pipeline: a Python generator publishes raw weather measurements over MQTT, a subscriber stores the raw JSON and a flattened record in PostgreSQL, a read-only web dashboard presents persisted data, and a standalone Flask service supplies machine-learning predictions.

## Package structure

```text
fire_weather/
|-- frontend/                 Dashboard HTML, JavaScript, CSS, and local Chart.js
|-- db/                       PostgreSQL schema, reset/report/export scripts, sample export
|-- ai_worker/                Training notebook/scripts, saved models, and inference service
|-- backend/                  MQTT generator/subscriber, API, risk engine, and tests
|-- edge/                     Arduino placeholder and future hardware images
|-- docs/
|   |-- datasets/             Downloaded Jena climate training dataset
|   |-- presentation/         PowerPoint and Google Slides link
|   `-- research/             Research report and source URL list
|-- requirements.txt
`-- README.md
```

## How the data moves

1. `backend/jena_event_generator.py` creates raw measurements and publishes them to MQTT.
2. `backend/jena_subscriber.py` validates each message and stores the original JSON in `jena_telemetry`.
3. The subscriber uses `backend/risk_engine.py` to derive scenario and risk fields, then stores the dashboard-ready row in `fire_weather_events`.
4. `backend/fire_api.py` reads PostgreSQL and serves JSON to the browser. It does not create or change events.
5. The dashboard displays the API response. The optional ML service uses a selected event to make one of the three trained predictions.

The raw MQTT message stays separate from the derived interpretation. It does not contain scenario, severity, risk, outlier, status, or data-quality labels.

No original SensorDashboard package, another intern's files, virtual environment, cache, or generated QA files are included.

## Prerequisites

- Python 3.11 or newer
- PostgreSQL with the `psql` command available
- Eclipse Mosquitto broker
- A modern browser

The commands below use Windows PowerShell and assume the current directory is the `fire_weather` folder.

After cloning the repository, enter that folder first:

```powershell
git clone https://github.com/rathin379/Fire-Weather-Monitoring.git
cd .\Fire-Weather-Monitoring\fire_weather
```

## 1. Install the Python packages

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

## 2. Drop and recreate the database

Open PostgreSQL:

```powershell
psql -U postgres -h 127.0.0.1 -d postgres
```

Run these commands inside `psql`. Replace the schema path with the full path on the computer running the demo and use forward slashes in that path.

```sql
DROP DATABASE IF EXISTS iot_platform WITH (FORCE);
CREATE DATABASE iot_platform;
\connect iot_platform
\i 'C:/FULL/PATH/TO/fire_weather/db/create_jena_telemetry.sql'
```

Set the database connection for each PowerShell terminal. Replace `YOUR_PASSWORD`.

```powershell
$env:POSTGRES_DSN = "dbname=iot_platform user=postgres password=YOUR_PASSWORD host=127.0.0.1 port=5432"
```

## 3. Start the project

Use separate PowerShell terminals and activate `.venv` in each one.

1. Start the Mosquitto service or run the broker:

   ```powershell
   mosquitto -v
   ```

2. Start the MQTT listener/subscriber:

   ```powershell
   python .\backend\jena_subscriber.py
   ```

3. Start the dashboard API and static-file server:

   ```powershell
   python .\backend\fire_api.py
   ```

4. Start the optional ML inference service:

   ```powershell
   python .\ai_worker\ml_service.py
   ```

5. Generate and insert reproducible sample data through the real MQTT pipeline:

   ```powershell
   python .\backend\jena_event_generator.py --scenario mixed --count 300 --seed 29
   ```

6. Open [http://127.0.0.1:8000/domain-fire.html](http://127.0.0.1:8000/domain-fire.html).

The generator's raw payload contains only event/device identifiers, time, and sensor measurements. Scenario, risk, severity, and outlier labels are derived after receipt; the browser never generates or writes events.

## 4. Verify the database and dashboard

```powershell
python .\db\database_report.py --window 24h
python .\db\export_telemetry.py --format flat
```

The report shows the selected event count, time range, scenario coverage, risk summary, and latest 10 records. The dashboard reads PostgreSQL through the backend API and receives new persisted events through server-sent events.

For a repeatable demo reset that keeps the database and tables:

```powershell
psql -U postgres -h 127.0.0.1 -d iot_platform -f .\db\reset_demo.sql
```

Then restart the subscriber and run the generator command again.

## 5. Train or test the ML components

The package contains three saved exploratory models for the demonstration. Rebuild them from the packaged dataset with:

```powershell
python .\ai_worker\train_models.py --max-samples 100000
```

Run the automated tests with:

```powershell
python -m unittest backend.test_fire_api backend.test_pipeline_contract ai_worker.test_ml_service -v
```

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `POSTGRES_DSN` | Local `iot_platform` database | PostgreSQL connection |
| `MQTT_BROKER` / `MQTT_PORT` | `localhost` / `1883` | MQTT broker |
| `MQTT_TOPIC` | `devices/telemetry` | Raw telemetry topic |
| `FIRE_DASHBOARD_PORT` | `8000` | Dashboard/API port |
| `FIRE_ML_PORT` | `5001` | ML inference port |
| `FIRE_ML_SERVICE_URL` | `http://127.0.0.1:5001` | API-to-ML service URL |

## 6. Troubleshooting and shutdown

- If the API returns HTTP 503, confirm PostgreSQL is running and `POSTGRES_DSN` is correct.
- If port 8000 or 5001 is already in use, stop the old process before starting another copy.
- If no events arrive, confirm Mosquitto is listening on port 1883 and the generator/subscriber use the same topic.
- If the ML tab reports an offline service, start `python .\ai_worker\ml_service.py`.

Stop the generator, subscriber, API, ML service, and foreground Mosquitto broker with `Ctrl+C` in their terminals. PostgreSQL and Mosquitto Windows services may then be stopped through Windows Services if the demonstration computer does not need them.

## Edge status

Arduino sketches and physical sensor photographs are intentionally not included yet. The required placeholder, future image folder, and handoff instructions are in `edge/README.md`. No physical hardware implementation is claimed in this release.

## Project documents

- [PowerPoint presentation](fire_weather/docs/presentation/Fire%20Weather%20Monitoring%20Project.pptx)
- [Google Slides access document](fire_weather/docs/presentation/Google_Slides_Link.docx)
- [Deep-dive research report](fire_weather/docs/research/Fire_Weather_Monitoring_Deep_Dive.docx)
- [Research URL list](fire_weather/docs/research/research_urls.txt)
- [Raw event and database contract](fire_weather/docs/FIRE_DATA_CONTRACT.md)

The research report distinguishes the implemented software system from proposed future Arduino deployment.
