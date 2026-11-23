"""Dépôt MongoDB de l'historique immuable des événements."""
from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import events


def ouvrir_mongo(creer_index: bool = True):
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from etudiant.config import charger_env

    charger_env()
    client = MongoClient(
        os.environ.get('MONGODB_URL', 'mongodb://127.0.0.1:27018'),
        serverSelectionTimeoutMS=5000,
    )
    try:
        client.admin.command('ping')
        base = client[os.environ.get('MONGODB_DATABASE', 'campusequip')]
        if creer_index:
            base.events.create_index(
                [('device_id', ASCENDING), ('event_id', ASCENDING)], unique=True,
                name='ux_event_identity',
            )
            base.events.create_index(
                [('contract_id', ASCENDING), ('observed_at_date', ASCENDING),
                 ('device_id', ASCENDING), ('event_id', ASCENDING)],
                name='ix_contract_history',
            )
            base.events.create_index(
                [('contract_id', ASCENDING), ('observed_at_date', DESCENDING),
                 ('device_id', DESCENDING), ('event_id', DESCENDING)],
                name='ix_contract_latest',
            )
            base.event_rejections.create_index(
                [('campaign_id', ASCENDING), ('batch_no', ASCENDING), ('line', ASCENDING)],
                unique=True, name='ux_event_rejection_source',
            )
            base.event_batches.create_index(
                [('campaign_id', ASCENDING), ('batch_no', ASCENDING)],
                unique=True, name='ux_event_batch_identity',
            )
            base.event_ingestion_attempts.create_index(
                [('campaign_id', ASCENDING), ('batch_no', ASCENDING), ('attempt_id', ASCENDING)],
                unique=True, name='ux_event_ingestion_attempt',
            )
        return client, base
    except Exception:
        client.close()
        raise


def _contrats_acceptes() -> set[int]:
    from .postgres import session

    with session() as cnx, cnx.cursor() as cur:
        cur.execute('SELECT contract_id FROM contracts')
        return {ligne[0] for ligne in cur.fetchall()}


def _rejetter(base, manifeste: dict, sha_source: str, numero_ligne: int,
              valeur_brute: Any, raison: str) -> None:
    try:
        valeur_brute = json.dumps(
            valeur_brute, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    except (TypeError, ValueError):
        valeur_brute = repr(valeur_brute)
    base.event_rejections.update_one(
        {'campaign_id': manifeste['campaign_id'],
         'batch_no': manifeste['batch_no'], 'line': numero_ligne},
        {'$set': {
            'source_sha256': sha_source,
            'raw': valeur_brute,
            'reason': raison,
            'recorded_at': datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def traiter_lot(dossier: Path) -> dict:
    """Persiste les événements validés sans écraser une clé composite existante."""
    from pymongo.errors import DuplicateKeyError

    manifeste, sha_source, lignes = events.lire_lot(dossier)
    client, base = ouvrir_mongo()
    try:
        identite = {'campaign_id': manifeste['campaign_id'], 'batch_no': manifeste['batch_no']}
        attempt_id = str(uuid.uuid4())
        commence_le = datetime.now(timezone.utc)
        lot_existant = base.event_batches.find_one(identite)
        if lot_existant and lot_existant.get('source_sha256') != sha_source:
            raise events.LotEvenementsInvalide(
                'un lot déjà journalisé ne peut pas être remplacé par un autre contenu')

        contrats = _contrats_acceptes()
        valides = events.convertir_lignes(lignes, contrats)
        compteurs = {
            'validated': 0, 'accepted': 0, 'copies': 0, 'conflicts': 0,
            'rejected': 0, 'inserted': 0,
        }
        for ligne in valides:
            if 'reason' in ligne:
                compteurs['rejected'] += 1
                _rejetter(base, manifeste, sha_source, ligne['line'], ligne['raw'], ligne['reason'])
                continue

            evenement = ligne['event']
            compteurs['validated'] += 1
            cle = {'device_id': evenement['device_id'], 'event_id': evenement['event_id']}
            document = {
                **cle,
                'contract_id': evenement['contract_id'],
                'event_type': evenement['event_type'],
                'observed_at': evenement['observed_at'],
                'observed_at_date': ligne['observed_at_date'],
                'payload': evenement['payload'],
                'normalized': evenement,
                'campaign_id': manifeste['campaign_id'],
                'batch_no': manifeste['batch_no'],
                'source_line': ligne['line'],
                'source_sha256': sha_source,
            }
            insere = False
            evenement_accepte = True
            try:
                base.events.insert_one(document)
            except DuplicateKeyError:
                existant = base.events.find_one(cle)
                if existant is None:
                    raise
                if events.json_canonique(existant['normalized']) == events.json_canonique(evenement):
                    compteurs['copies'] += 1
                    compteurs['accepted'] += 1
                else:
                    evenement_accepte = False
                    compteurs['conflicts'] += 1
                    _rejetter(base, manifeste, sha_source, ligne['line'], evenement,
                              'CONFLIT_CLE_COMPOSITE')
            else:
                insere = True
                compteurs['accepted'] += 1
                compteurs['inserted'] += 1

            if evenement_accepte and evenement['event_type'] == 'position':
                from .timescale import enregistrer_position

                enregistrer_position(
                    evenement,
                    ligne['observed_at_date'],
                    manifeste['campaign_id'],
                    manifeste['batch_no'],
                )

        resultat = {
            **identite,
            'attempt_id': attempt_id,
            'profile': manifeste['profile'],
            'source_sha256': sha_source,
            'source_path': str(Path(dossier).resolve()),
            'started_at': commence_le,
            **compteurs,
            'status': 'events_written',
            'processed_at': datetime.now(timezone.utc).isoformat(),
        }
        base.event_ingestion_attempts.insert_one(resultat.copy())
        base.event_batches.replace_one(identite, resultat, upsert=True)
        return {**resultat, 'started_at': commence_le.isoformat()}
    finally:
        client.close()


def prochain_lot_pret(dossier_flux: Path) -> Path | None:
    """Choisit le premier lot READY non journalisé ; les .pending sont ignorés."""
    dossier_flux = Path(dossier_flux)
    if not dossier_flux.is_dir():
        return None
    candidats = sorted(
        chemin for chemin in dossier_flux.iterdir()
        if chemin.is_dir() and chemin.name.startswith('lot-')
        and not chemin.name.startswith('.pending-') and (chemin / 'READY').is_file()
    )
    if not candidats:
        return None
    client, base = ouvrir_mongo()
    try:
        for chemin in candidats:
            try:
                manifeste = json.loads(
                    (chemin / 'manifest.json').read_text(encoding='utf-8'))
                if not isinstance(manifeste, dict):
                    return chemin
                campagne_id, batch_no = manifeste.get('campaign_id'), manifeste.get('batch_no')
            except (OSError, UnicodeDecodeError, ValueError):
                return chemin
            if (not isinstance(campagne_id, str) or isinstance(batch_no, bool)
                    or not isinstance(batch_no, int)):
                return chemin
            enregistre = base.event_batches.find_one(
                {'campaign_id': campagne_id, 'batch_no': batch_no})
            try:
                sha_source = events.empreinte(chemin / 'evenements.jsonl')
            except OSError:
                return chemin
            if (enregistre is None or enregistre.get('source_sha256') != sha_source
                    or enregistre.get('status') != 'completed'):
                return chemin
        return None
    finally:
        client.close()


def historique_contrat(contract_id: int) -> list[dict]:
    from pymongo import ASCENDING

    client, base = ouvrir_mongo()
    try:
        curseur = base.events.find(
            {'contract_id': contract_id}, {'_id': 0}
        ).sort([('observed_at_date', ASCENDING), ('device_id', ASCENDING),
                ('event_id', ASCENDING)])
        return list(curseur)
    finally:
        client.close()


def dernier_evenement(contract_id: int) -> dict | None:
    from pymongo import DESCENDING

    client, base = ouvrir_mongo()
    try:
        return base.events.find_one(
            {'contract_id': contract_id}, {'_id': 0},
            sort=[('observed_at_date', DESCENDING), ('device_id', DESCENDING),
                  ('event_id', DESCENDING)],
        )
    finally:
        client.close()


def suivi_enrichi(contract_id: int) -> dict:
    """Joint explicitement en Python les informations PostgreSQL et MongoDB."""
    from .postgres import session

    with session() as cnx, cnx.cursor() as cur:
        cur.execute(
            """
            SELECT c.contract_id, c.start_date, c.status, c.client_id,
                   cl.name AS client_name, c.site_id, s.name AS site_name,
                   s.campus_id, ca.name AS campus_name
            FROM contracts c
            JOIN clients cl ON cl.client_id = c.client_id
            JOIN sites s ON s.site_id = c.site_id
            JOIN campus ca ON ca.campus_id = s.campus_id
            WHERE c.contract_id = %s
            """,
            (contract_id,),
        )
        ligne = cur.fetchone()
        if ligne is None:
            raise LookupError(f'contrat accepté introuvable : {contract_id}')
        noms = [description.name for description in cur.description]
        contrat = dict(zip(noms, ligne))
    return {'contract': contrat, 'events': historique_contrat(contract_id)}


def tous_les_evenements() -> list[dict]:
    client, base = ouvrir_mongo()
    try:
        return list(base.events.find({}, {'_id': 0, 'normalized': 1, 'contract_id': 1}))
    finally:
        client.close()


def derniers_etats_operationnels() -> dict[int, dict]:
    """Agrège le dernier état hors position avec un départage Mongo déterministe."""
    client, base = ouvrir_mongo()
    try:
        pipeline = [
            {'$match': {'event_type': {'$in': ['withdrawal', 'return', 'incident', 'failure']}}},
            {'$sort': {
                'contract_id': 1, 'observed_at_date': -1,
                'device_id': -1, 'event_id': -1,
            }},
            {'$group': {'_id': '$contract_id', 'event': {'$first': '$normalized'}}},
        ]
        return {ligne['_id']: ligne['event'] for ligne in base.events.aggregate(pipeline)}
    finally:
        client.close()


def compte_incidents_attendu() -> int:
    derniers = derniers_etats_operationnels()
    return sum(
        evenement['event_type'] in {'incident', 'failure'}
        for evenement in derniers.values()
    )


def tentatives_ingestion(campaign_id: str, batch_no: int) -> list[dict]:
    from pymongo import ASCENDING

    client, base = ouvrir_mongo()
    try:
        return list(base.event_ingestion_attempts.find(
            {'campaign_id': campaign_id, 'batch_no': batch_no},
            {'_id': 0},
        ).sort('started_at', ASCENDING))
    finally:
        client.close()
