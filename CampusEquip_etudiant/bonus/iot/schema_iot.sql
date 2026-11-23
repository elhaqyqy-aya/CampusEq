-- =====================================================================
-- Bonus IoT — capteurs GPS simulés (table distincte des locations)
--
-- Les observations ne modifient JAMAIS les montants des contrats : elles sont
-- stockées dans leur propre table, avec leur propre clé (device_id, event_id).
-- =====================================================================

CREATE TABLE IF NOT EXISTS iot_devices (
    device_id text PRIMARY KEY,
    label     text
);

CREATE TABLE IF NOT EXISTS iot_observations (
    device_id    text          NOT NULL,
    event_id     text          NOT NULL,
    equipment_id integer       NOT NULL REFERENCES equipments (equipment_id),
    observed_at  timestamptz   NOT NULL,
    latitude     numeric(9, 6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude    numeric(9, 6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    received_at  timestamptz   NOT NULL DEFAULT now(),
    source_file  text          NOT NULL,
    PRIMARY KEY (device_id, event_id)
);
CREATE INDEX IF NOT EXISTS ix_iot_observations_equipement
    ON iot_observations (equipment_id, observed_at);

CREATE TABLE IF NOT EXISTS iot_lots (
    batch_id              bigserial  PRIMARY KEY,
    fichier               text       NOT NULL,
    signature             char(64)   NOT NULL UNIQUE,
    statut                text       NOT NULL
                                     CHECK (statut IN ('CHARGE', 'REJETE_STRUCTURE')),
    observations_recues   integer    NOT NULL DEFAULT 0,
    acceptees             integer    NOT NULL DEFAULT 0,
    rejetees              integer    NOT NULL DEFAULT 0,
    rejeu                 integer    NOT NULL DEFAULT 0,
    inserees              integer    NOT NULL DEFAULT 0,
    motif                 text,
    traite_le             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS iot_rejets (
    batch_id  bigint  NOT NULL REFERENCES iot_lots (batch_id) ON DELETE CASCADE,
    position  integer NOT NULL,
    device_id text,
    event_id  text,
    motifs    text[]  NOT NULL,
    brut      jsonb   NOT NULL,
    PRIMARY KEY (batch_id, position)
);
