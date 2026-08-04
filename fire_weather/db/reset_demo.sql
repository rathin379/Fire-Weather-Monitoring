-- Intentionally clear only Fire Weather demo data.
-- Do not use DROP DATABASE: iot_platform may contain other internship projects.
-- Run create_jena_telemetry.sql first on a new database.
BEGIN;
TRUNCATE TABLE fire_weather_events, jena_telemetry RESTART IDENTITY;
COMMIT;
