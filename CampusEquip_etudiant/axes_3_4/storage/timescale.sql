CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE SCHEMA IF NOT EXISTS axes34;

CREATE TABLE IF NOT EXISTS axes34.event_positions (
    observed_at       timestamptz NOT NULL,
    device_id         text        NOT NULL,
    event_id          text        NOT NULL,
    contract_id       integer     NOT NULL CHECK (contract_id > 0),
    latitude_deg      double precision NOT NULL CHECK (latitude_deg BETWEEN -90 AND 90),
    longitude_deg     double precision NOT NULL CHECK (longitude_deg BETWEEN -180 AND 180),
    campaign_id       text        NOT NULL,
    batch_no          integer     NOT NULL CHECK (batch_no > 0),
    PRIMARY KEY (observed_at, device_id, event_id)
);
SELECT create_hypertable(
    'axes34.event_positions', 'observed_at', if_not_exists => TRUE
);

CREATE TABLE IF NOT EXISTS axes34.task_attempts (
    observed_at       timestamptz NOT NULL,
    dag_id            text        NOT NULL,
    run_id            text        NOT NULL,
    task_id           text        NOT NULL,
    try_number        integer     NOT NULL CHECK (try_number > 0),
    status            text        NOT NULL CHECK (status IN ('success', 'failed')),
    duration_ms       bigint      NOT NULL CHECK (duration_ms >= 0),
    error_type        text,
    PRIMARY KEY (observed_at, dag_id, run_id, task_id, try_number)
);
SELECT create_hypertable(
    'axes34.task_attempts', 'observed_at', if_not_exists => TRUE
);
CREATE INDEX IF NOT EXISTS ix_task_attempts_task_time
    ON axes34.task_attempts (task_id, observed_at DESC);
