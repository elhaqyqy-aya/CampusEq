"""Fonctions métier indépendantes d'Airflow pour les lots d'événements."""
from __future__ import annotations

import csv
import json
import logging
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from . import events
from .cache import redis_store
from .storage import mongodb, postgres

logger = logging.getLogger(__name__)


class LotLocationsRefuse(RuntimeError):
    """Un lot de locations a été définitivement refusé par le contrôle structurel."""


def verifier_lot(dossier: Path) -> dict:
    manifeste, sha_source, lignes = events.lire_lot(dossier)
    return {
        'path': str(Path(dossier).resolve()),
        'campaign_id': manifeste['campaign_id'],
        'batch_no': manifeste['batch_no'],
        'source_sha256': sha_source,
        'rows': len(lignes),
    }


def traiter_lot_evenements(dossier: Path) -> dict:
    return mongodb.traiter_lot(dossier)


def traiter_lot_locations_configure() -> dict:
    """Réutilise le chargeur des axes 1–2 si un lot est configuré."""
    chemin = os.environ.get('CAMPUSEQUIP_LOCATION_BATCH')
    if not chemin:
        with postgres.session() as cnx, cnx.cursor() as cur:
            cur.execute('SELECT count(*) FROM contracts')
            return {'mode': 'contrats_deja_charges', 'contracts': cur.fetchone()[0]}

    dossier = Path(chemin)
    try:
        manifeste = json.loads((dossier / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise LotLocationsRefuse(f'lot de locations configuré illisible : {erreur}') from None
    from etudiant.traitement import traiter_lot

    resultat = traiter_lot(dossier, manifeste)
    if resultat.get('status') not in {'CHARGE', 'DEJA_CHARGE'}:
        raise LotLocationsRefuse(f"lot de locations refusé : {resultat.get('status')}")
    return {'mode': 'lot_locations', **resultat}


def actualiser_cache_financier() -> dict:
    return redis_store.rafraichir_tous_les_montants()


def reconstruire_file_incidents() -> dict:
    return redis_store.reconstruire_incidents()


def verifier_sorties(campaign_id: str, batch_no: int, source_sha256: str) -> dict:
    client, base = mongodb.ouvrir_mongo()
    try:
        identite = {'campaign_id': campaign_id, 'batch_no': batch_no}
        journal = base.event_batches.find_one(identite)
        if journal is None or journal.get('source_sha256') != source_sha256:
            raise RuntimeError('journal MongoDB absent ou empreinte de lot différente')
        documents = base.events.count_documents(identite)
        if documents < journal['inserted']:
            raise RuntimeError(
                f'historique MongoDB incomplet : {documents} événement(s), '
                f"{journal['inserted']} insertion(s) annoncée(s)")
        if (journal['validated'] != journal['accepted'] + journal['conflicts']
                or journal['accepted'] != journal['inserted'] + journal['copies']):
            raise RuntimeError('les compteurs MongoDB ne se réconcilient pas')
    finally:
        client.close()
    projection = redis_store.verifier_projections()
    client, base = mongodb.ouvrir_mongo()
    try:
        resultat = base.event_batches.update_one(
            {
                'campaign_id': campaign_id, 'batch_no': batch_no,
                'source_sha256': source_sha256,
            },
            {'$set': {
                'status': 'completed',
                'verified_at': datetime.now(timezone.utc),
            }},
        )
        if resultat.matched_count != 1:
            raise RuntimeError('le lot à valider a changé depuis son ingestion')
    finally:
        client.close()
    return {
        'campaign_id': campaign_id, 'batch_no': batch_no,
        'events_from_batch': documents, 'incident_projection': projection,
        'consistent': True,
    }


def exporter_contrats(chemin: Path) -> dict:
    """Exporte uniquement les contrats réellement présents dans PostgreSQL."""
    with postgres.session() as cnx, cnx.cursor() as cur:
        cur.execute('SELECT contract_id FROM contracts ORDER BY contract_id')
        contrats = [ligne[0] for ligne in cur.fetchall()]
    if not contrats:
        raise RuntimeError('aucun contrat accepté à exporter')
    destination = Path(chemin)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', encoding='utf-8', newline='') as flux:
        redacteur = csv.writer(flux, lineterminator='\n')
        redacteur.writerow(['contract_id'])
        redacteur.writerows((identifiant,) for identifiant in contrats)
    from .events import empreinte

    return {'path': str(destination.resolve()), 'contracts': len(contrats),
            'sha256': empreinte(destination)}


def enregistrer_retour_interactif(contract_id: int, event_id: str,
                                  condition: str, notes: str,
                                  observed_at: str | None = None) -> dict:
    """Publishes and ingests one return event through the regular event pipeline."""
    from . import events

    if not isinstance(condition, str) or condition not in {
            'Excellent', 'Good', 'Fair', 'Needs repair'}:
        raise ValueError('condition de retour non prise en charge')
    if not isinstance(notes, str) or len(notes) > 500:
        raise ValueError('les notes sont limitées à 500 caractères')

    evenement = {
        'device_id': 'web-desk',
        'event_id': event_id,
        'contract_id': contract_id,
        'event_type': 'return',
        'observed_at': observed_at if observed_at is not None else datetime.now(
            timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'payload': {
            'summary': f'Return recorded · {condition}',
            'condition': condition,
            'notes': notes,
        },
    }
    events.normaliser_evenement(evenement)

    racine = Path(os.environ.get(
        'CAMPUSEQUIP_UI_EVENTS_DIR',
        Path(__file__).resolve().parent / 'flux_ui',
    ))
    racine.mkdir(parents=True, exist_ok=True)
    campaign_id = str(uuid.uuid4())
    dossier_temporaire = racine / f'.pending-{campaign_id}'
    dossier_campagne = racine / f'campaign-{campaign_id}'
    dossier_temporaire.mkdir()

    export = exporter_contrats(dossier_temporaire / 'contrats_acceptes.csv')
    with (dossier_temporaire / 'contrats_acceptes.csv').open(
            newline='', encoding='utf-8') as flux:
        contrats = {int(ligne['contract_id']) for ligne in csv.DictReader(flux)}
    if contract_id not in contrats:
        raise LookupError(f'contrat accepté introuvable : {contract_id}')

    (dossier_temporaire / 'campagne.json').write_text(
        json.dumps({
            'campaign_id': campaign_id,
            'contrats_sha256': export['sha256'],
        }, ensure_ascii=True, indent=2) + '\n',
        encoding='utf-8',
    )
    dossier_lot = dossier_temporaire / 'lot-000001'
    dossier_lot.mkdir()
    chemin_evenements = dossier_lot / 'evenements.jsonl'
    chemin_evenements.write_text(
        json.dumps(evenement, ensure_ascii=True, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    manifeste = {
        'schema_version': 'campusequip-events-1',
        'campaign_id': campaign_id,
        'batch_no': 1,
        'profile': 'propre',
        'rows': 1,
        'files': {'evenements.jsonl': events.empreinte(chemin_evenements)},
        'contracts_sha256': export['sha256'],
    }
    (dossier_lot / 'manifest.json').write_text(
        json.dumps(manifeste, ensure_ascii=True, indent=2) + '\n',
        encoding='utf-8',
    )
    (dossier_lot / 'READY').write_text('', encoding='utf-8')
    dossier_temporaire.rename(dossier_campagne)

    resultat = mongodb.traiter_lot(dossier_campagne / 'lot-000001')
    from pymongo.errors import PyMongoError
    from redis.exceptions import RedisError

    try:
        projection = {
            'status': 'connected',
            **redis_store.reconstruire_incidents(),
        }
    except (PyMongoError, RedisError) as erreur:
        logger.exception('Return event was ingested, but its Redis projection was not refreshed')
        projection = {
            'status': 'unavailable',
            'error': f'{type(erreur).__name__}: {erreur}',
        }
    return {
        'event_id': event_id,
        'contract_id': contract_id,
        'ingestion': resultat,
        'incident_projection': projection,
        'source_path': str((dossier_campagne / 'lot-000001').resolve()),
    }


def lire_json(valeur):
    return json.dumps(valeur, ensure_ascii=False, default=_json_defaut, indent=2)


def _json_defaut(valeur):
    if isinstance(valeur, (datetime, date)):
        return valeur.isoformat()
    if hasattr(valeur, 'as_tuple'):
        return format(valeur, 'f')
    raise TypeError(f'type non sérialisable : {type(valeur).__name__}')
