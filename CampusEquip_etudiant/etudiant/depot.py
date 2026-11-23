"""Accès PostgreSQL : chargement transactionnel d'un lot, journal et rejeu.

Toutes les écritures métier d'un lot se font dans UNE transaction :
journal + référentiels (au premier lot) + contrats + lignes + quarantaine.
Si une seule étape échoue, rien n'est conservé : la base ne peut pas contenir
un lot à moitié chargé, et le journal ne peut pas annoncer un succès partiel.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

from . import config, regles

# Clé du verrou consultatif : sérialise deux surveillants sur la même base.
CLE_VERROU = 4_245_611_219


class DejaCharge(Exception):
    """La signature du lot est déjà dans le journal : aucun ajout métier."""

    def __init__(self, batch: dict):
        super().__init__(f"lot déjà chargé (batch {batch['batch_id']})")
        self.batch = batch


class RefusStructure(Exception):
    """Le lot est refusé avant toute écriture métier (motif explicite)."""

    def __init__(self, code: str, detail: str):
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail


class ConflitContrat(Exception):
    """Un contract_id du lot existe déjà : la transaction entière échoue."""

    def __init__(self, contrat_ids: list[int]):
        super().__init__(
            f'{len(contrat_ids)} contrat(s) déjà chargés : '
            + ', '.join(str(identifiant) for identifiant in sorted(contrat_ids)[:10]))
        self.contrat_ids = sorted(contrat_ids)


@dataclass
class LotACharger:
    """Tout ce qu'il faut pour écrire un lot, sans relire les fichiers."""

    dossier_source: str
    campaign_id: str
    batch_number: int
    schema_version: str
    profil: str | None
    signature: str | None
    locations_sha256: str
    referentiels_sha256: str
    referentiel_signature: str | None
    analyse: regles.AnalyseLot
    referentiels: regles.Referentiels
    lignes_ajoutees: int = 0


@dataclass
class ResultatChargement:
    statut: str
    batch_id: int | None
    lignes_ajoutees: int
    existant: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Connexion et schéma
# ---------------------------------------------------------------------------
def connexion() -> psycopg2.extensions.connection:
    cnx = psycopg2.connect(**config.parametres_connexion())
    cnx.set_client_encoding('UTF8')
    return cnx


def executer_script(cnx, chemin: Path) -> None:
    with cnx.cursor() as cur:
        cur.execute(Path(chemin).read_text(encoding='utf-8'))
    cnx.commit()


def schema(cnx) -> None:
    executer_script(cnx, Path(__file__).with_name('schema.sql'))


# ---------------------------------------------------------------------------
# Lecture de la configuration du laboratoire
# ---------------------------------------------------------------------------
def lire_config(cur) -> dict:
    cur.execute('SELECT cle, valeur FROM lab_config')
    return dict(cur.fetchall())


def ecrire_config(cur, cle: str, valeur: str) -> None:
    cur.execute(
        """
        INSERT INTO lab_config (cle, valeur) VALUES (%s, %s)
        ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, maj_le = now()
        """, (cle, valeur))


def batch_charge(cur, signature: str) -> dict | None:
    cur.execute(
        """
        SELECT batch_id, campaign_id, batch_number, rows_accepted, rows_rejected,
               contracts_accepted, contracts_rejected, rejection_rate, charge_le
        FROM ingestion_batches
        WHERE signature = %s AND status = 'CHARGE'
        """, (signature,))
    ligne = cur.fetchone()
    if ligne is None:
        return None
    colonnes = ('batch_id', 'campaign_id', 'batch_number', 'rows_accepted', 'rows_rejected',
                'contracts_accepted', 'contracts_rejected', 'rejection_rate', 'charge_le')
    return dict(zip(colonnes, ligne))


def contrats_existants(cur, contrat_ids: list[int]) -> list[int]:
    if not contrat_ids:
        return []
    cur.execute('SELECT contract_id FROM contracts WHERE contract_id = ANY(%s)',
                (contrat_ids,))
    return [ligne[0] for ligne in cur.fetchall()]


# ---------------------------------------------------------------------------
# Écritures
# ---------------------------------------------------------------------------
def _inserer_referentiels(cur, referentiels: regles.Referentiels) -> None:
    execute_values(cur, 'INSERT INTO campus (campus_id, name) VALUES %s',
                   sorted(referentiels.campuses.items()))
    execute_values(cur, 'INSERT INTO sites (site_id, campus_id, name) VALUES %s',
                   [(site_id, campus_id, nom)
                    for site_id, (campus_id, nom) in sorted(referentiels.sites.items())])
    execute_values(cur, 'INSERT INTO clients (client_id, name) VALUES %s',
                   sorted(referentiels.clients.items()))
    # Les catégories peuvent se référencer : insertion en deux temps.
    execute_values(cur, 'INSERT INTO categories (category_id, name, parent_id) VALUES %s',
                   [(category_id, nom, None)
                    for category_id, (nom, _) in sorted(referentiels.categories.items())])
    parents = [(parent_id, category_id) for category_id, (_, parent_id)
               in sorted(referentiels.categories.items()) if parent_id is not None]
    if parents:
        execute_values(cur, 'UPDATE categories SET parent_id = v.parent_id '
                            'FROM (VALUES %s) AS v(parent_id, category_id) '
                            'WHERE categories.category_id = v.category_id', parents)
    execute_values(cur, 'INSERT INTO equipments (equipment_id, name, category_id) VALUES %s',
                   [(equipment_id, nom, category_id)
                    for equipment_id, (category_id, nom) in sorted(referentiels.equipments.items())])


def _inserer_contrats(cur, lot: LotACharger, batch_id: int) -> None:
    contrats = {}
    for ligne in lot.analyse.acceptees:
        contrats[ligne.valeurs['contract_id']] = (
            ligne.valeurs['contract_id'], ligne.valeurs['client_id'], ligne.valeurs['site_id'],
            ligne.valeurs['start_date'], ligne.valeurs['status'], batch_id)
    execute_values(
        cur,
        'INSERT INTO contracts (contract_id, client_id, site_id, start_date, status, batch_id) '
        'VALUES %s', list(contrats.values()), page_size=500)

    lignes = [(ligne.valeurs['contract_id'], ligne.valeurs['line_no'], ligne.valeurs['equipment_id'],
               ligne.valeurs['quantity'], ligne.valeurs['unit'], ligne.valeurs['duration'],
               ligne.valeurs['unit_rate'])
              for ligne in lot.analyse.acceptees]
    execute_values(
        cur,
        'INSERT INTO contract_lines (contract_id, line_no, equipment_id, quantity, unit, '
        'duration, unit_rate) VALUES %s', lignes, page_size=500)


def _inserer_quarantaine(cur, lot: LotACharger, batch_id: int) -> None:
    rejets = [(batch_id, ligne.position, ligne.contrat_cle,
               (ligne.norm or {}).get('line_no'), ligne.motifs,
               Json(ligne.valeurs_brutes_json()))
              for ligne in lot.analyse.rejetees]
    if rejets:
        execute_values(
            cur,
            'INSERT INTO batch_rejections (batch_id, position, contract_id, line_no, motifs, '
            'valeurs_brutes) VALUES %s', rejets, page_size=500)

    anomalies = []
    for ligne in lot.analyse.anomalies:
        for detail in ligne.anomalies:
            code = detail.split(':', 1)[0]
            anomalies.append((batch_id, ligne.position, ligne.contrat_cle,
                              ligne.norm.get('line_no'), code, detail))
    if anomalies:
        execute_values(
            cur,
            'INSERT INTO batch_anomalies (batch_id, position, contract_id, line_no, code, detail) '
            'VALUES %s', anomalies, page_size=500)


def _inserer_batch(cur, lot: LotACharger, statut: str, motif: str | None = None) -> int:
    analyse = lot.analyse
    charge_le = datetime.now(timezone.utc) if statut == 'CHARGE' else None
    cur.execute(
        """
        INSERT INTO ingestion_batches (
            campaign_id, batch_number, schema_version, rules_version, profil, signature,
            locations_sha256, referentiels_sha256, referentiel_signature, dossier_source,
            rows_received, rows_deduplicated, rows_after_dedup, rows_accepted, rows_rejected,
            contracts_received, contracts_accepted, contracts_rejected, anomalies,
            rejection_rate, alerte_qualite, status, motif_rejet, charge_le)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s)
        RETURNING batch_id
        """,
        (lot.campaign_id, lot.batch_number, lot.schema_version, regles.RULES_VERSION,
         lot.profil, lot.signature, lot.locations_sha256, lot.referentiels_sha256,
         lot.referentiel_signature, lot.dossier_source,
         analyse.lignes_recues, len(analyse.doublons), analyse.lignes_apres_dedoublonnage,
         len(analyse.acceptees), len(analyse.rejetees), analyse.contrats_recus,
         analyse.contrats_acceptes, analyse.contrats_rejetes, len(analyse.anomalies),
         analyse.taux_rejet, analyse.alerte, statut, motif, charge_le))
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Chargement d'un lot
# ---------------------------------------------------------------------------
def charger_lot(cnx, lot: LotACharger) -> ResultatChargement:
    """Charge un lot ou reconnaît son rejeu, dans une seule transaction."""
    try:
        with cnx.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s)', (CLE_VERROU,))
            reglages = lire_config(cur)

            campagne = reglages.get('campaign_id')
            if campagne and campagne != lot.campaign_id:
                raise RefusStructure(
                    'CAMPAGNE_REFUSEE',
                    f"cette base est liée à la campagne {campagne}, le lot vient de "
                    f"{lot.campaign_id} ; créez une base neuve pour une autre campagne")

            referentiel = reglages.get('referentiel_signature')
            if referentiel and lot.referentiel_signature and referentiel != lot.referentiel_signature:
                raise RefusStructure(
                    'REFERENTIELS_INCOHERENTS',
                    "les référentiels du lot diffèrent de ceux de la campagne ; "
                    "les référentiels doivent rester fixes")

            if lot.signature:
                charge = batch_charge(cur, lot.signature)
                if charge:
                    raise DejaCharge(charge)

            conflits = contrats_existants(cur, list(lot.analyse.contrats_acceptes_ids))
            if conflits:
                raise ConflitContrat(conflits)

            batch_id = _inserer_batch(cur, lot, 'CHARGE')
            if not campagne:
                _inserer_referentiels(cur, lot.referentiels)
                ecrire_config(cur, 'campaign_id', lot.campaign_id)
                if lot.referentiel_signature:
                    ecrire_config(cur, 'referentiel_signature', lot.referentiel_signature)
            _inserer_contrats(cur, lot, batch_id)
            _inserer_quarantaine(cur, lot, batch_id)
        cnx.commit()
        lot.lignes_ajoutees = len(lot.analyse.acceptees)
        return ResultatChargement('CHARGE', batch_id, lot.lignes_ajoutees)
    except DejaCharge as deja:
        cnx.rollback()
        return ResultatChargement('DEJA_CHARGE', deja.batch['batch_id'], 0, deja.batch)
    except Exception:
        cnx.rollback()
        raise


def enregistrer_refus(cnx, lot: LotACharger, code: str, detail: str) -> int:
    """Trace un REJETE_STRUCTURE dans le journal, hors transaction métier."""
    try:
        with cnx.cursor() as cur:
            batch_id = _inserer_batch(cur, lot, 'REJETE_STRUCTURE', f'{code}: {detail}')
        cnx.commit()
        return batch_id
    except Exception:
        cnx.rollback()
        raise


# ---------------------------------------------------------------------------
# Lectures de contrôle (tests, analyses, rapport)
# ---------------------------------------------------------------------------
def compter(cnx, table: str) -> int:
    if table not in {'campus', 'sites', 'clients', 'categories', 'equipments', 'contracts',
                     'contract_lines', 'ingestion_batches', 'batch_rejections', 'batch_anomalies'}:
        raise ValueError(f'table inconnue : {table}')
    with cnx.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM {table}')
        return cur.fetchone()[0]


def montant_par_contrat(cnx, contract_id: int) -> list[dict]:
    with cnx.cursor() as cur:
        cur.execute(
            """
            SELECT l.contract_id, c.start_date, c.status, l.line_no, l.quantity, l.duration,
                   l.unit, l.unit_rate, l.line_amount
            FROM contract_lines l JOIN contracts c USING (contract_id)
            WHERE l.contract_id = %s ORDER BY l.line_no
            """, (contract_id,))
        colonnes = ('contract_id', 'start_date', 'status', 'line_no', 'quantity', 'duration',
                    'unit', 'unit_rate', 'line_amount')
        return [dict(zip(colonnes, ligne)) for ligne in cur.fetchall()]


def total_retenu(cnx, contract_id: int) -> object:
    """Montant retenu d'un contrat : paid/closed seulement, Decimal."""
    with cnx.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(sum(line_amount), 0)
            FROM v_lignes_retenues WHERE contract_id = %s
            """, (contract_id,))
        return cur.fetchone()[0]
