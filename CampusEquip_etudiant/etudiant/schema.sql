-- =====================================================================
-- CampusEquip v2 — modèle relationnel des axes 1 et 2
-- Base dédiée : campusequip (ne jamais réutiliser la base ShopFlow).
--
-- Ce script réinitialise le schéma : il supprime puis recrée les objets.
-- Il s'exécute sur une base neuve, avec psql :
--     createdb campusequip
--     psql -d campusequip -v ON_ERROR_STOP=1 -f etudiant/schema.sql
-- ou, sans psql, avec le lanceur fourni :
--     python -m outils.init_base --reinitialiser
--
-- Grain :
--   * un campus possède plusieurs sites (guichets) ;
--   * un site et un client portent plusieurs contrats ;
--   * un contrat porte plusieurs lignes, clé (contract_id, line_no) ;
--   * une ligne référence un équipement (type de matériel) et une quantité.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 0. Réinitialisation (base de démonstration uniquement)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS batch_anomalies    CASCADE;
DROP TABLE IF EXISTS batch_rejections   CASCADE;
DROP TABLE IF EXISTS contract_lines     CASCADE;
DROP TABLE IF EXISTS contracts          CASCADE;
DROP TABLE IF EXISTS ingestion_batches  CASCADE;
DROP TABLE IF EXISTS equipments         CASCADE;
DROP TABLE IF EXISTS categories         CASCADE;
DROP TABLE IF EXISTS clients            CASCADE;
DROP TABLE IF EXISTS sites              CASCADE;
DROP TABLE IF EXISTS campus             CASCADE;
DROP TABLE IF EXISTS lab_config         CASCADE;
DROP VIEW  IF EXISTS v_lignes_retenues  CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_montant_jour_campus CASCADE;

-- ---------------------------------------------------------------------
-- 1. Référentiels (contenu fixé par la campagne, fourni par referentiels.json)
-- ---------------------------------------------------------------------
CREATE TABLE campus (
    campus_id  integer     PRIMARY KEY,
    name       text        NOT NULL CHECK (btrim(name) <> '')
);

CREATE TABLE sites (
    site_id    integer     PRIMARY KEY,
    campus_id  integer     NOT NULL REFERENCES campus (campus_id),
    name       text        NOT NULL CHECK (btrim(name) <> '')
);
CREATE INDEX ix_sites_campus ON sites (campus_id);

CREATE TABLE clients (
    client_id  integer     PRIMARY KEY,
    name       text        NOT NULL CHECK (btrim(name) <> '')
);

CREATE TABLE categories (
    category_id integer    PRIMARY KEY,
    name        text       NOT NULL CHECK (btrim(name) <> ''),
    parent_id   integer    REFERENCES categories (category_id),
    -- Un nœud ne peut pas être son propre parent : la remontée récursive
    -- (bonus) resterait sinon infinie. Les cycles plus longs sont contrôlés
    -- par la requête récursive elle-même.
    CONSTRAINT categories_pas_autoreference CHECK (parent_id IS NULL OR parent_id <> category_id)
);
CREATE INDEX ix_categories_parent ON categories (parent_id);

CREATE TABLE equipments (
    equipment_id integer   PRIMARY KEY,
    name         text      NOT NULL CHECK (btrim(name) <> ''),
    category_id  integer   NOT NULL REFERENCES categories (category_id)
);
CREATE INDEX ix_equipments_categorie ON equipments (category_id);

-- ---------------------------------------------------------------------
-- 2. Journal des lots : c'est lui qui rend le rejeu possible.
--    Une ligne = une tentative de traitement, chargée ou refusée en structure.
-- ---------------------------------------------------------------------
CREATE TABLE ingestion_batches (
    batch_id              bigserial   PRIMARY KEY,
    campaign_id           text        NOT NULL,
    batch_number          integer     NOT NULL CHECK (batch_number > 0),
    schema_version        text        NOT NULL,
    rules_version         text        NOT NULL,
    profil                text,
    signature             char(64),            -- SHA-256 des 2 fichiers + version des règles
    locations_sha256      char(64),
    referentiels_sha256   char(64),
    referentiel_signature char(64),
    dossier_source        text        NOT NULL,
    rows_received         integer     NOT NULL DEFAULT 0 CHECK (rows_received  >= 0),
    rows_deduplicated     integer     NOT NULL DEFAULT 0 CHECK (rows_deduplicated >= 0),
    rows_after_dedup      integer     NOT NULL DEFAULT 0 CHECK (rows_after_dedup >= 0),
    rows_accepted         integer     NOT NULL DEFAULT 0 CHECK (rows_accepted >= 0),
    rows_rejected         integer     NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    contracts_received    integer     NOT NULL DEFAULT 0 CHECK (contracts_received >= 0),
    contracts_accepted    integer     NOT NULL DEFAULT 0 CHECK (contracts_accepted >= 0),
    contracts_rejected    integer     NOT NULL DEFAULT 0 CHECK (contracts_rejected >= 0),
    anomalies             integer     NOT NULL DEFAULT 0 CHECK (anomalies >= 0),
    rejection_rate        numeric(6,2) NOT NULL DEFAULT 0 CHECK (rejection_rate BETWEEN 0 AND 100),
    alerte_qualite        boolean     NOT NULL DEFAULT false,
    status                text        NOT NULL CHECK (status IN ('CHARGE', 'REJETE_STRUCTURE')),
    motif_rejet           text,
    recu_le               timestamptz NOT NULL DEFAULT now(),
    charge_le             timestamptz
);

-- Une signature ne peut être chargée qu'une seule fois ; un rejeu est reconnu
-- par le journal, pas par la mémoire du surveilleur. L'index est partiel :
-- un lot refusé en structure garde sa trace, mais peut être rejoué une fois
-- corrigé, et un rejeu de lot valide reste bloqué.
CREATE UNIQUE INDEX ux_batches_signature_chargee
    ON ingestion_batches (signature)
    WHERE status = 'CHARGE' AND signature IS NOT NULL;
CREATE INDEX ix_batches_campagne ON ingestion_batches (campaign_id, batch_number);

-- Rejets : une ligne de quarantaine par ligne source rejetée.
CREATE TABLE batch_rejections (
    batch_id      bigint   NOT NULL REFERENCES ingestion_batches (batch_id) ON DELETE CASCADE,
    position      integer  NOT NULL,          -- numéro de ligne physique du CSV
    contract_id   text,                       -- valeur brute, même illisible
    line_no       text,
    motifs        text[]   NOT NULL,
    valeurs_brutes jsonb   NOT NULL,
    PRIMARY KEY (batch_id, position)
);

-- Anomalies : lignes acceptées mais signalées (ex. quantity > 20).
CREATE TABLE batch_anomalies (
    batch_id    bigint   NOT NULL REFERENCES ingestion_batches (batch_id) ON DELETE CASCADE,
    position    integer  NOT NULL,
    contract_id text,
    line_no     text,
    code        text     NOT NULL,
    detail      text     NOT NULL,
    PRIMARY KEY (batch_id, position, code)
);

-- Paramètres du laboratoire : campagne autorisée et empreinte des référentiels.
-- Une seule campagne par base : c'est cette table qui le garantit.
CREATE TABLE lab_config (
    cle       text        PRIMARY KEY,
    valeur    text        NOT NULL,
    maj_le    timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 3. Contrats et lignes
-- ---------------------------------------------------------------------
CREATE TABLE contracts (
    contract_id  integer     PRIMARY KEY CHECK (contract_id > 0),
    client_id    integer     NOT NULL REFERENCES clients (client_id),
    site_id      integer     NOT NULL REFERENCES sites (site_id),
    start_date   date        NOT NULL,
    status       text        NOT NULL
                             CHECK (status IN ('paid', 'closed', 'draft', 'cancelled')),
    batch_id     bigint      NOT NULL REFERENCES ingestion_batches (batch_id),
    charge_le    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_contracts_date     ON contracts (start_date);
CREATE INDEX ix_contracts_statut   ON contracts (status);
CREATE INDEX ix_contracts_client   ON contracts (client_id);
CREATE INDEX ix_contracts_lot      ON contracts (batch_id);

CREATE TABLE contract_lines (
    contract_id  integer      NOT NULL REFERENCES contracts (contract_id),
    line_no      integer      NOT NULL CHECK (line_no > 0),
    equipment_id integer      NOT NULL REFERENCES equipments (equipment_id),
    quantity     integer      NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    unit         text         NOT NULL CHECK (unit IN ('hour', 'day')),
    duration     integer      NOT NULL CHECK (duration > 0),
    unit_rate    numeric      NOT NULL
                              CHECK (unit_rate >= 0 AND unit_rate <= 9999999999.99)
                              CHECK (unit_rate = round(unit_rate, 2)),
    -- Montant = quantité x durée x tarif : la colonne est calculée par la base,
    -- elle ne peut donc pas diverger du tarif historique conservé.
    line_amount  numeric      GENERATED ALWAYS AS (quantity * duration * unit_rate) STORED,
    PRIMARY KEY (contract_id, line_no),
    -- La durée dépend de l'unité : 1 à 720 heures, ou 1 à 365 jours.
    CONSTRAINT duree_selon_unite CHECK (
        (unit = 'hour' AND duration BETWEEN 1 AND 720) OR
        (unit = 'day'  AND duration BETWEEN 1 AND 365)
    )
);
CREATE INDEX ix_lignes_equipement ON contract_lines (equipment_id);
CREATE INDEX ix_lignes_contrat    ON contract_lines (contract_id);

-- ---------------------------------------------------------------------
-- 4. Vues d'analyse
--    Convention commerciale du projet : seuls paid et closed comptent dans
--    les indicateurs ; tout le montant est rattaché à start_date.
--    draft et cancelled restent stockés mais sont exclus des indicateurs.
-- ---------------------------------------------------------------------
CREATE VIEW v_lignes_retenues AS
SELECT l.contract_id,
       l.line_no,
       c.start_date,
       c.site_id,
       s.campus_id,
       c.client_id,
       l.equipment_id,
       l.unit,
       l.quantity,
       l.duration,
       l.unit_rate,
       l.line_amount,
       c.status
FROM contract_lines l
JOIN contracts c ON c.contract_id = l.contract_id
JOIN sites     s ON s.site_id     = c.site_id
WHERE c.status IN ('paid', 'closed');

-- Résultat précalculé (bonus 2) : agrégat jour x campus, à rafraîchir avec
-- REFRESH MATERIALIZED VIEW. La requête équivalente à la demande est dans
-- bonus/analyse_precalcul.sql ; les deux doivent donner le même total.
CREATE MATERIALIZED VIEW mv_montant_jour_campus AS
SELECT campus_id, start_date AS jour, sum(line_amount) AS montant
FROM v_lignes_retenues
GROUP BY campus_id, start_date;
CREATE UNIQUE INDEX ux_mv_montant_jour_campus ON mv_montant_jour_campus (campus_id, jour);

COMMIT;

-- Contrôle de mise en place : doit renvoyer 10 (8 tables + 1 vue + 1 vue matérialisée).
-- SELECT count(*) FROM pg_class
--  WHERE relname IN ('campus','sites','clients','categories','equipments','contracts',
--                   'contract_lines','ingestion_batches','v_lignes_retenues',
--                   'mv_montant_jour_campus');
