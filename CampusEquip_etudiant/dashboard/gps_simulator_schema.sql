CREATE SCHEMA IF NOT EXISTS gps_sim;

CREATE TABLE IF NOT EXISTS gps_sim.devices (
    device_id          text PRIMARY KEY,
    name               text NOT NULL,
    route_key          text NOT NULL,
    progress_m         double precision NOT NULL DEFAULT 0,
    base_speed_kmh     double precision NOT NULL,
    initial_battery    integer NOT NULL CHECK (initial_battery BETWEEN 0 AND 100),
    battery_pct        double precision NOT NULL CHECK (battery_pct BETWEEN 0 AND 100),
    signal_strength    integer NOT NULL CHECK (signal_strength BETWEEN 0 AND 5),
    status             text NOT NULL CHECK (status IN ('online', 'weak', 'offline')),
    latitude           double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude          double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    speed_kmh          double precision NOT NULL DEFAULT 0 CHECK (speed_kmh >= 0),
    heading_deg        double precision NOT NULL DEFAULT 0 CHECK (heading_deg >= 0 AND heading_deg < 360),
    altitude_m         double precision NOT NULL DEFAULT 0,
    last_update_at     timestamptz NOT NULL DEFAULT now(),
    last_telemetry_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gps_sim.telemetry (
    id                 bigserial PRIMARY KEY,
    device_id          text NOT NULL REFERENCES gps_sim.devices(device_id) ON DELETE CASCADE,
    latitude           double precision NOT NULL,
    longitude          double precision NOT NULL,
    speed_kmh          double precision NOT NULL,
    heading_deg        double precision NOT NULL,
    altitude_m         double precision NOT NULL,
    battery_pct        double precision NOT NULL CHECK (battery_pct BETWEEN 0 AND 100),
    signal_strength    integer NOT NULL,
    status             text NOT NULL CHECK (status IN ('online', 'weak', 'offline')),
    recorded_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_gps_telemetry_device_time
    ON gps_sim.telemetry (device_id, recorded_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_gps_telemetry_recorded_at
    ON gps_sim.telemetry (recorded_at);

CREATE TABLE IF NOT EXISTS gps_sim.simulation_state (
    singleton          boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    status             text NOT NULL DEFAULT 'paused' CHECK (status IN ('running', 'paused')),
    speed_multiplier   double precision NOT NULL DEFAULT 1
                       CHECK (speed_multiplier BETWEEN 0.25 AND 8),
    last_tick_at       timestamptz,
    last_cleanup_at    timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gps_sim.geofences (
    id                 bigserial PRIMARY KEY,
    slug               text NOT NULL UNIQUE,
    name               text NOT NULL CHECK (btrim(name) <> ''),
    center_latitude    double precision NOT NULL CHECK (center_latitude BETWEEN -90 AND 90),
    center_longitude   double precision NOT NULL CHECK (center_longitude BETWEEN -180 AND 180),
    radius_m           integer NOT NULL CHECK (radius_m BETWEEN 50 AND 10000),
    enabled            boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gps_sim.geofence_events (
    id                 bigserial PRIMARY KEY,
    geofence_id        bigint REFERENCES gps_sim.geofences(id) ON DELETE SET NULL,
    geofence_name      text NOT NULL,
    device_id          text NOT NULL REFERENCES gps_sim.devices(device_id) ON DELETE CASCADE,
    event_type         text NOT NULL CHECK (event_type IN ('enter', 'exit')),
    latitude           double precision NOT NULL,
    longitude          double precision NOT NULL,
    occurred_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_gps_geofence_events_time
    ON gps_sim.geofence_events (occurred_at DESC, id DESC);
