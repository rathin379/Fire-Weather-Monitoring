-- Fire Weather Monitoring schema.
-- This file is safe to re-run and preserves existing rows.
-- jena_telemetry is the raw MQTT audit table; fire_weather_events is the
-- flattened, dashboard-ready table. Use reset_demo.sql for a clean demo.

CREATE TABLE IF NOT EXISTS jena_telemetry (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID UNIQUE,
    device_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    pressure_mbar DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    wind_speed_ms DOUBLE PRECISION,
    wind_dir_deg DOUBLE PRECISION,
    air_density DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'OK',
    scenario TEXT NOT NULL DEFAULT 'normal',
    severity TEXT NOT NULL DEFAULT 'info',
    failure_point TEXT,
    is_outlier BOOLEAN NOT NULL DEFAULT FALSE,
    wind_gust_ms DOUBLE PRECISION,
    fuel_moisture_pct DOUBLE PRECISION,
    data_quality TEXT NOT NULL DEFAULT 'valid',
    mqtt_topic TEXT NOT NULL DEFAULT 'devices/telemetry',
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB
);

-- One-time compatibility upgrades for an existing jena_telemetry table.
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS event_id UUID;
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS scenario TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS severity TEXT NOT NULL DEFAULT 'info';
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS failure_point TEXT;
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS is_outlier BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS wind_gust_ms DOUBLE PRECISION;
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS fuel_moisture_pct DOUBLE PRECISION;
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS data_quality TEXT NOT NULL DEFAULT 'valid';
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS mqtt_topic TEXT NOT NULL DEFAULT 'devices/telemetry';
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE jena_telemetry ADD COLUMN IF NOT EXISTS payload JSONB;

CREATE UNIQUE INDEX IF NOT EXISTS idx_jena_telemetry_event_id ON jena_telemetry (event_id);
CREATE INDEX IF NOT EXISTS idx_jena_telemetry_timestamp ON jena_telemetry (timestamp DESC);

CREATE TABLE IF NOT EXISTS fire_weather_events (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    device_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    temperature DOUBLE PRECISION,
    pressure_mbar DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    wind_speed_ms DOUBLE PRECISION,
    wind_gust_ms DOUBLE PRECISION,
    wind_dir_deg DOUBLE PRECISION,
    air_density DOUBLE PRECISION,
    fuel_moisture_pct DOUBLE PRECISION,
    status TEXT NOT NULL,
    scenario TEXT NOT NULL,
    severity TEXT NOT NULL,
    failure_point TEXT,
    data_quality TEXT NOT NULL,
    is_outlier BOOLEAN NOT NULL DEFAULT FALSE,
    risk_score DOUBLE PRECISION,
    risk_level TEXT NOT NULL,
    CONSTRAINT fire_weather_humidity_range CHECK (humidity IS NULL OR humidity BETWEEN 0 AND 100),
    CONSTRAINT fire_weather_wind_range CHECK (wind_speed_ms IS NULL OR wind_speed_ms >= 0),
    CONSTRAINT fire_weather_gust_range CHECK (wind_gust_ms IS NULL OR wind_gust_ms >= 0),
    CONSTRAINT fire_weather_fuel_range CHECK (fuel_moisture_pct IS NULL OR fuel_moisture_pct BETWEEN 0 AND 100),
    CONSTRAINT fire_weather_quality CHECK (data_quality IN ('valid', 'invalid'))
);

CREATE INDEX IF NOT EXISTS idx_fire_weather_events_observed_at ON fire_weather_events (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_fire_weather_events_scenario ON fire_weather_events (scenario, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_fire_weather_events_risk_level ON fire_weather_events (risk_level, observed_at DESC);
