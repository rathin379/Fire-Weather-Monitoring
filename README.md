# Fire Weather Monitoring

This repository contains the Fire Weather Monitoring internship project. It is a database-backed IoT pipeline that:

1. Publishes raw weather measurements through MQTT.
2. Stores the raw messages and derived dashboard records in PostgreSQL.
3. Serves a read-only dashboard from the stored records.
4. Provides a separate local machine-learning service for predictions.

Everything can run on one computer. The manual setup below uses separate terminal windows for the services so that each service has its own visible log. No second laptop is required.

## How the data moves

1. `backend/jena_event_generator.py` creates raw measurements and publishes them to MQTT.
2. `backend/jena_subscriber.py` validates each message and stores the original JSON in `jena_telemetry`.
3. The subscriber derives scenario and risk fields with `backend/risk_engine.py`, then stores a dashboard-ready row in `fire_weather_events`.
4. `backend/fire_api.py` reads PostgreSQL and serves JSON and the live event stream. It does not create or change events.
5. The dashboard displays the API response. The separate ML service makes predictions for selected events.

The raw MQTT message contains identifiers, time, and sensor measurements only. It does not contain scenario, severity, risk, outlier, status, or data-quality labels. Those fields are derived after receipt.

## Before you start

You need:

- Python 3.11 or newer
- PostgreSQL
- Eclipse Mosquitto
- Git, if you are cloning the repository yourself
- A modern web browser

Install PostgreSQL and Mosquitto before following the pipeline steps. During PostgreSQL setup, remember the password you create for the `postgres` user. The password is used locally through `POSTGRES_DSN`; it is never stored in this repository.

The software demo does not require an Arduino. The `edge/` folder contains the internship sensor sketches for reference; those sketches are separate from the simulated MQTT pipeline.

## Clone the repository

If you already have the repository, skip the clone command and change into your existing `fire_weather` folder.

### Windows PowerShell

```powershell
git clone https://github.com/rathin379/Fire-Weather-Monitoring.git
```

```powershell
cd .\Fire-Weather-Monitoring\fire_weather
```

### macOS Terminal

```bash
git clone https://github.com/rathin379/Fire-Weather-Monitoring.git
```

```bash
cd Fire-Weather-Monitoring/fire_weather
```

From this point forward, run commands from the `fire_weather` folder.

## Install or verify the required software

### Windows

Install Python, PostgreSQL, and Eclipse Mosquitto using their Windows installers. If a command below says it is not recognized, add that program's installation folder to PATH or use the full executable path installed on your computer.

```powershell
python --version
```

```powershell
psql --version
```

```powershell
mosquitto -h
```

Start the PostgreSQL and Mosquitto services from the Windows **Services** application. Do not start a second foreground Mosquitto process if the Mosquitto service is already running.

### macOS

If Homebrew is already installed, these commands install the required services:

```bash
brew install python postgresql mosquitto
```

```bash
brew services start postgresql
```

```bash
brew services start mosquitto
```

Verify the tools:

```bash
python3 --version
```

```bash
psql --version
```

```bash
mosquitto -h
```

If PostgreSQL or Mosquitto is already installed and running, do not install or start a second copy.

## Create the Python environment

Create the environment once. It must be activated again in every terminal that starts a Python service.

### Windows PowerShell

If PowerShell blocks local activation scripts, run this once in the current PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

```powershell
python -m pip install -r .\requirements.txt
```

### macOS Terminal

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
```

## Create the database tables

Do this once for a new computer or a new database. The schema command is safe to run again because it creates missing tables and indexes without deleting existing rows.

First open PostgreSQL from the `fire_weather` folder:

```text
psql -U postgres -h 127.0.0.1 -d postgres
```

Inside the `psql` window, run each command separately:

```sql
CREATE DATABASE iot_platform;
```

If PostgreSQL says that `iot_platform` already exists, that is okay. Continue with the next command.

```sql
\connect iot_platform
```

```sql
\i 'db/create_jena_telemetry.sql'
```

```sql
\q
```

If the database user has a password, PostgreSQL may ask for it when `psql` opens. Use the password created during PostgreSQL installation.

## Set the database connection

Set this variable in each terminal that runs the subscriber, dashboard API, ML service, database report, or export script. Replace only `YOUR_PASSWORD`. Do not commit the real password or put it in a project file.

### Windows PowerShell

```powershell
$env:POSTGRES_DSN = "dbname=iot_platform user=postgres password=YOUR_PASSWORD host=127.0.0.1 port=5432"
```

### macOS Terminal

```bash
export POSTGRES_DSN="dbname=iot_platform user=postgres password=YOUR_PASSWORD host=127.0.0.1 port=5432"
```

The variable only applies to the current terminal window. If a service is started before this command, stop and restart that service after setting it.

## Check that the MQTT broker is ready

Mosquitto must be running before the subscriber or generator starts. If the check succeeds, leave the existing broker running and do not start another one.

### Windows PowerShell

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 1883 -InformationLevel Quiet
```

Continue only when the output is `True`. If it is false, start Mosquitto from the Services application. If you installed Mosquitto in the default location and it is not a service, this is the common fallback:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -v
```

### macOS Terminal

```bash
nc -z 127.0.0.1 1883
```

If that command fails, start the broker in its own terminal:

```bash
mosquitto -v
```

## Start the complete pipeline on one computer

Use four terminal windows on the same computer:

- Terminal 1: MQTT subscriber
- Terminal 2: dashboard API
- Terminal 3: ML service
- Terminal 4: event generator

The PostgreSQL and Mosquitto services normally run in the background. Open a fifth terminal only if you had to start Mosquitto with `mosquitto -v`.

Prepare each project terminal separately before starting its service. A folder change, virtual-environment activation, and `POSTGRES_DSN` value only apply to the terminal where you type them.

### Windows PowerShell

At the beginning of each of the four project terminals, run:

```powershell
cd .\Fire-Weather-Monitoring\fire_weather
```

If the prompt already ends in `Fire-Weather-Monitoring\fire_weather>`, skip the `cd` command.

```powershell
.\.venv\Scripts\Activate.ps1
```

In Terminal 1 (subscriber), Terminal 2 (API), and Terminal 3 (ML service), also run:

```powershell
$env:POSTGRES_DSN = "dbname=iot_platform user=postgres password=YOUR_PASSWORD host=127.0.0.1 port=5432"
```

Use the PostgreSQL password created on that computer. Do not use a GitHub or Windows password. Then verify the database connection in those three terminals:

```powershell
python -c "import os, psycopg2; c=psycopg2.connect(os.environ['POSTGRES_DSN'], connect_timeout=5); print('PostgreSQL connection OK'); c.close()"
```

Terminal 4 (event generator) does not use PostgreSQL, so it needs only the folder and virtual-environment setup.

### macOS Terminal

At the beginning of each of the four project terminals, run:

```bash
cd Fire-Weather-Monitoring/fire_weather
```

If the terminal is already in the `Fire-Weather-Monitoring/fire_weather` folder, skip the `cd` command.

```bash
source .venv/bin/activate
```

In Terminal 1 (subscriber), Terminal 2 (API), and Terminal 3 (ML service), also run:

```bash
export POSTGRES_DSN="dbname=iot_platform user=postgres password=YOUR_PASSWORD host=127.0.0.1 port=5432"
```

Use the PostgreSQL password created on that computer. Do not use a GitHub or macOS password. Then verify the database connection in those three terminals:

```bash
python -c "import os, psycopg2; c=psycopg2.connect(os.environ['POSTGRES_DSN'], connect_timeout=5); print('PostgreSQL connection OK'); c.close()"
```

Terminal 4 (event generator) does not use PostgreSQL, so it needs only the folder and virtual-environment setup.

Start the subscriber first. It listens for MQTT messages and writes them to PostgreSQL.

### Windows PowerShell

```powershell
python .\backend\jena_subscriber.py
```

### macOS Terminal

```bash
python ./backend/jena_subscriber.py
```

Start the read-only dashboard API in a second terminal.

### Windows PowerShell

```powershell
python .\backend\fire_api.py
```

### macOS Terminal

```bash
python ./backend/fire_api.py
```

Start the ML inference service in a third terminal. It is required for the Machine Learning tab and all three prediction tasks.

### Windows PowerShell

```powershell
python .\ai_worker\ml_service.py
```

### macOS Terminal

```bash
python ./ai_worker/ml_service.py
```

Before starting Terminal 4, confirm that Terminal 2 and Terminal 3 are responding:

### Windows PowerShell

```powershell
curl.exe http://127.0.0.1:8000/api/fire/health
```

```powershell
curl.exe http://127.0.0.1:5001/health
```

### macOS Terminal

```bash
curl http://127.0.0.1:8000/api/fire/health
```

```bash
curl http://127.0.0.1:5001/health
```

Continue only after both services respond successfully. The ML health endpoint confirms that the models loaded; the PostgreSQL connection test above confirms that the ML service can access its database context.

Generate reproducible demo data in a fourth terminal. Run this only after the broker and subscriber are running.

### Windows PowerShell

```powershell
python .\backend\jena_event_generator.py --scenario mixed --count 300 --seed 29
```

Optional historical backfill:

```powershell
python .\backend\jena_event_generator.py --historical --days 30 --count 10000
```

### macOS Terminal

```bash
python ./backend/jena_event_generator.py --scenario mixed --count 300 --seed 29
```

Open the dashboard after the generator finishes publishing:

[http://127.0.0.1:8000/domain-fire.html](http://127.0.0.1:8000/domain-fire.html)

The generator publishes raw event/device identifiers, timestamps, and sensor measurements only. Scenario, risk, severity, outlier, and data-quality fields are derived by the subscriber after receipt. The browser never creates or writes events.

## Verify that the pipeline is working

The health checks should return a successful response. Run them from any activated project terminal.

### Windows PowerShell

```powershell
curl.exe http://127.0.0.1:8000/api/fire/health
```

```powershell
curl.exe http://127.0.0.1:5001/health
```

### macOS Terminal

```bash
curl http://127.0.0.1:8000/api/fire/health
```

```bash
curl http://127.0.0.1:5001/health
```

The database report confirms that events reached PostgreSQL through the real MQTT path.

### Windows PowerShell

```powershell
python .\db\database_report.py --window 24h
```

### macOS Terminal

```bash
python ./db/database_report.py --window 24h
```

The report should show an event count, recent timestamps, scenario coverage, and risk summaries. A flat export is optional:

### Windows PowerShell

```powershell
python .\db\export_telemetry.py --format flat
```

### macOS Terminal

```bash
python ./db/export_telemetry.py --format flat
```

The export is written under `db/exports/` on the local computer.

## Reset the demo data without deleting the database

This clears only the two Fire Weather tables, then lets you run the generator again. Do not run it if you need to keep the current demo rows.

### Windows PowerShell

```powershell
psql -U postgres -h 127.0.0.1 -d iot_platform -f .\db\reset_demo.sql
```

### macOS Terminal

```bash
psql -U postgres -h 127.0.0.1 -d iot_platform -f ./db/reset_demo.sql
```

## Run the automated tests

These tests check the API contract, raw-event contract, risk classification, and ML service behavior. They do not replace the live MQTT-to-PostgreSQL check above.

### Windows PowerShell

```powershell
python -m unittest backend.test_fire_api backend.test_pipeline_contract ai_worker.test_ml_service -v
```

### macOS Terminal

```bash
python -m unittest backend.test_fire_api backend.test_pipeline_contract ai_worker.test_ml_service -v
```

## Train the exploratory models again (optional)

Saved exploratory models are already included. Retraining is not required to run the dashboard.

### Windows PowerShell

```powershell
python .\ai_worker\train_models.py --max-samples 100000
```

### macOS Terminal

```bash
python ./ai_worker/train_models.py --max-samples 100000
```

## Troubleshooting

- **API health returns HTTP 503:** PostgreSQL is unreachable or `POSTGRES_DSN` is wrong. Set the variable in the same terminal before starting `fire_api.py`, confirm the `iot_platform` database and tables exist, then restart the API.
- **Mosquitto will not start:** Check whether port `1883` is already occupied. If the broker is already running, do not launch a second broker; use the existing one.
- **No new events appear:** Start the subscriber before the generator, confirm both use `localhost:1883` and topic `devices/telemetry`, and keep the subscriber terminal open.
- **The ML tab says the service is offline:** Start `ml_service.py` and confirm `http://127.0.0.1:5001/health` responds successfully.
- **Pressure-risk prediction says PostgreSQL is unavailable:** Set POSTGRES_DSN in Terminal 3 and restart ml_service.py. This task loads the previous valid pressure event from PostgreSQL; the ML health endpoint alone does not verify that database query.
- **A port is already in use:** Stop the old copy of that service before starting another one. The dashboard API uses port `8000`; the ML service uses port `5001`; Mosquitto uses port `1883`; PostgreSQL uses port `5432`.
- **PowerShell refuses activation:** Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell window, then activate `.venv` again.
- **macOS says a command is not found:** Confirm Python, PostgreSQL, Mosquitto, and Homebrew are installed and that their command folders are on PATH.

## Stop the demo

Press `Ctrl+C` in the generator, subscriber, API, ML, and any foreground Mosquitto terminals. Leave PostgreSQL and Mosquitto running if you will use the demo again. If you started them as services and want to stop them afterward:

### Windows

Use the Windows **Services** application and stop the PostgreSQL or Mosquitto service there.

### macOS

```bash
brew services stop mosquitto
```

```bash
brew services stop postgresql
```

## Project structure

```text
fire_weather/
|-- frontend/                 Dashboard HTML, JavaScript, CSS, and local Chart.js
|-- db/                       PostgreSQL schema, reset/report/export scripts, sample export
|-- ai_worker/                Training notebook/scripts, saved models, and inference service
|-- backend/                  MQTT generator/subscriber, API, risk engine, and tests
|-- edge/                     Arduino sensor sketches and future hardware images
|-- docs/                     Dataset, report, presentation, and data contract
|-- requirements.txt
`-- README.md
```

## Project documents

- [PowerPoint presentation](fire_weather/docs/presentation/Fire%20Weather%20Monitoring%20Project.pptx)
- [Google Slides access document](fire_weather/docs/presentation/Google_Slides_Link.docx)
- [Deep-dive research report](fire_weather/docs/research/Fire_Weather_Monitoring_Deep_Dive.docx)
- [Google Docs research report link](fire_weather/docs/research/Google_Doc_Report_Link.docx)
- [Research URL list](fire_weather/docs/research/research_urls.txt)
- [Raw event and database contract](fire_weather/docs/FIRE_DATA_CONTRACT.md)

The research report distinguishes the implemented software system from proposed future Arduino deployment. The dashboard is a read-only client of the database; event generation remains outside the browser.
