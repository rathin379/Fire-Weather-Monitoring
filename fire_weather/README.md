# Fire Weather Monitoring package

The complete setup guide is maintained in the repository's main README:

[Open the full Windows and macOS setup guide](../README.md)

That guide explains how to install the prerequisites, create the PostgreSQL tables, configure the database connection, start the MQTT subscriber, dashboard API, ML service, and event generator on one computer, verify the live pipeline, run tests, and troubleshoot common issues.

This folder contains the runnable package:

- `backend/` contains the MQTT generator, subscriber, API, risk engine, and tests.
- `frontend/` contains the read-only dashboard.
- `ai_worker/` contains the saved exploratory models and inference service.
- `db/` contains the PostgreSQL schema and verification scripts.
- `edge/` contains the Arduino placeholder and future hardware notes.
- `docs/` contains the research report, presentation, dataset, and data contract.
