"""Instantané en lecture seule destiné au prototype CampusEquip."""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

import psycopg2

logger = logging.getLogger(__name__)


def _texte(valeur) -> str:
    if isinstance(valeur, (date, datetime)):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return format(valeur, 'f')
    return str(valeur)


def lire_postgresql(cur) -> dict:
    cur.execute("""
        SELECT count(*) AS campuses
        FROM campus
    """)
    campus_count = int(cur.fetchone()['campuses'])

    cur.execute("""
        SELECT count(*) AS types_equipement
        FROM equipments
    """)
    equipment_count = int(cur.fetchone()['types_equipement'])

    cur.execute("""
        SELECT count(*) AS contrats,
               count(*) FILTER (WHERE status IN ('paid', 'closed')) AS acceptes
        FROM contracts
    """)
    contracts_summary = cur.fetchone()

    cur.execute("""
        SELECT ca.campus_id, ca.name,
               count(DISTINCT c.contract_id) AS contrats,
               count(DISTINCT c.contract_id)
                   FILTER (WHERE c.status IN ('paid', 'closed')) AS contrats_acceptes,
               COALESCE(sum(l.quantity), 0) AS quantites_louees,
               COALESCE(sum(l.line_amount)
                   FILTER (WHERE c.status IN ('paid', 'closed')), 0) AS montant
        FROM campus ca
        LEFT JOIN sites s ON s.campus_id = ca.campus_id
        LEFT JOIN contracts c ON c.site_id = s.site_id
        LEFT JOIN contract_lines l ON l.contract_id = c.contract_id
        GROUP BY ca.campus_id, ca.name
        ORDER BY ca.name
    """)
    campuses = [{
        'id': int(row['campus_id']),
        'name': row['name'],
        'contracts': int(row['contrats']),
        'accepted_contracts': int(row['contrats_acceptes']),
        'historical_quantity': int(row['quantites_louees']),
        'amount': _texte(row['montant']),
    } for row in cur.fetchall()]

    cur.execute("""
        SELECT e.equipment_id, e.name, cat.name AS category,
               COALESCE(sum(l.quantity), 0) AS historical_quantity,
               count(DISTINCT l.contract_id) AS contracts,
               COALESCE(string_agg(DISTINCT ca.name, ', ' ORDER BY ca.name), '')
                   AS campuses
        FROM equipments e
        JOIN categories cat ON cat.category_id = e.category_id
        LEFT JOIN contract_lines l ON l.equipment_id = e.equipment_id
        LEFT JOIN contracts c ON c.contract_id = l.contract_id
        LEFT JOIN sites s ON s.site_id = c.site_id
        LEFT JOIN campus ca ON ca.campus_id = s.campus_id
        GROUP BY e.equipment_id, e.name, cat.name
        ORDER BY e.name, e.equipment_id
    """)
    equipment = [{
        'id': f"EQ-{row['equipment_id']}",
        'name': row['name'],
        'category': row['category'],
        'campus': row['campuses'] or 'Not associated with a campus',
        'location': 'Not tracked by the project schema',
        'status': 'Catalogue type',
        'condition': 'Not tracked',
        'tag': f"{int(row['historical_quantity'])} historical rental unit(s)",
        'quantity': int(row['historical_quantity']),
        'contracts': int(row['contracts']),
    } for row in cur.fetchall()]

    cur.execute("""
        SELECT c.contract_id, c.start_date, c.status, cl.name AS borrower,
               ca.name AS campus,
               COALESCE(string_agg(DISTINCT e.name, ', ' ORDER BY e.name), '')
                   AS equipment,
               COALESCE(sum(l.quantity), 0) AS quantity
        FROM contracts c
        JOIN clients cl ON cl.client_id = c.client_id
        JOIN sites s ON s.site_id = c.site_id
        JOIN campus ca ON ca.campus_id = s.campus_id
        LEFT JOIN contract_lines l ON l.contract_id = c.contract_id
        LEFT JOIN equipments e ON e.equipment_id = l.equipment_id
        GROUP BY c.contract_id, c.start_date, c.status, cl.name, ca.name
        ORDER BY c.start_date DESC, c.contract_id DESC
        LIMIT 200
    """)
    contracts = [{
        'reference': str(row['contract_id']),
        'borrower': row['borrower'],
        'item': row['equipment'] or 'No equipment line',
        'itemId': f"{int(row['quantity'])} historical unit(s)",
        'campus': row['campus'],
        'due': _texte(row['start_date']),
        'start_date': _texte(row['start_date']),
        'status': row['status'],
    } for row in cur.fetchall()]

    cur.execute("""
        SELECT to_char(start_date, 'DD Mon') AS label,
               count(*) AS contracts
        FROM contracts
        WHERE start_date >= (
            SELECT COALESCE(max(start_date), current_date) - 13 FROM contracts
        )
        GROUP BY start_date
        ORDER BY start_date
    """)
    daily = [{'label': row['label'], 'contracts': int(row['contracts'])}
             for row in cur.fetchall()]

    return {
        'summary': {
            'campuses': campus_count,
            'equipment_types': equipment_count,
            'contracts': int(contracts_summary['contrats']),
            'accepted_contracts': int(contracts_summary['acceptes']),
        },
        'campuses': campuses,
        'equipment': equipment,
        'contracts': contracts,
        'daily': daily,
        'services': {'postgresql': {'status': 'connected'}},
    }


def _event_view(document: dict) -> dict:
    event = document.get('normalized') or {}
    payload = event.get('payload') or {}
    event_type = event.get('event_type', 'event')
    observed_at = event.get('observed_at', '')
    return {
        'time': observed_at,
        'type': event_type,
        'title': str(payload.get('summary') or payload.get('description')
                     or event_type.replace('_', ' ').capitalize()),
        'detail': (
            f"Contract {event.get('contract_id', document.get('contract_id', '—'))}"
            f" · {event.get('device_id', '—')} · {event.get('event_id', '—')}"
        ),
        'source': 'MongoDB event history',
        'status': 'Stored in MongoDB',
        'reference': str(event.get('event_id', '')),
        'item': str(event.get('device_id', 'Device not specified')),
        'itemId': str(event.get('device_id', '')),
        'campus': 'Campus is not part of the event record',
        'severity': str(payload.get('severity') or 'Not recorded'),
        'state': event_type.replace('_', ' ').capitalize(),
    }


def lire_mongodb() -> dict:
    from pymongo import DESCENDING
    from pymongo.errors import PyMongoError

    from axes_3_4.storage import mongodb

    client, base = mongodb.ouvrir_mongo(creer_index=False)
    try:
        total_events = base.events.count_documents({})
        recent_documents = list(
            base.events.find({}, {'_id': 0, 'normalized': 1, 'contract_id': 1})
            .sort([
                ('observed_at_date', DESCENDING),
                ('device_id', DESCENDING),
                ('event_id', DESCENDING),
            ])
            .limit(50)
        )
        activity = [_event_view(document) for document in recent_documents]

        latest_states = list(base.events.aggregate([
            {'$match': {'event_type': {'$in': ['withdrawal', 'return', 'incident', 'failure']}}},
            {'$sort': {
                'contract_id': 1, 'observed_at_date': -1,
                'device_id': -1, 'event_id': -1,
            }},
            {'$group': {'_id': '$contract_id', 'event': {'$first': '$normalized'}}},
        ]))
        incidents = [
            _event_view({'normalized': row['event']})
            for row in latest_states
            if row['event'].get('event_type') in {'incident', 'failure'}
        ]
        batches = list(
            base.event_batches.find(
                {},
                {
                    '_id': 0, 'campaign_id': 1, 'batch_no': 1, 'status': 1,
                    'validated': 1, 'accepted': 1, 'rejected': 1, 'copies': 1,
                    'conflicts': 1, 'inserted': 1, 'started_at': 1, 'processed_at': 1,
                },
            )
            .sort('started_at', DESCENDING)
            .limit(10)
        )
        totals = next(iter(base.event_batches.aggregate([{
            '$group': {
                '_id': None,
                'batches': {'$sum': 1},
                'validated': {'$sum': '$validated'},
                'accepted': {'$sum': '$accepted'},
                'rejected': {'$sum': '$rejected'},
                'copies': {'$sum': '$copies'},
                'conflicts': {'$sum': '$conflicts'},
                'inserted': {'$sum': '$inserted'},
            },
        }])), {})
        for batch in batches:
            for key in ('started_at', 'processed_at'):
                if isinstance(batch.get(key), datetime):
                    batch[key] = batch[key].isoformat()
        return {
            'event_count': total_events,
            'activity': activity,
            'incidents': incidents,
            'rejections': base.event_rejections.count_documents({}),
            'pipeline': {
                'batches': int(totals.get('batches', 0)),
                'validated': int(totals.get('validated', 0)),
                'accepted': int(totals.get('accepted', 0)),
                'rejected': int(totals.get('rejected', 0)),
                'copies': int(totals.get('copies', 0)),
                'conflicts': int(totals.get('conflicts', 0)),
                'inserted': int(totals.get('inserted', 0)),
                'events': total_events,
                'rejections': base.event_rejections.count_documents({}),
                'recent_batches': batches,
            },
            'services': {'mongodb': {'status': 'connected'}},
        }
    except PyMongoError:
        raise
    finally:
        client.close()


def lire_redis() -> dict:
    import redis

    from axes_3_4.cache import redis_store

    client = redis_store.ouvrir_redis()
    try:
        client.ping()
        return {
            'incident_projection': int(client.zcard(redis_store.CLE_INCIDENTS)),
            'services': {'redis': {'status': 'connected'}},
        }
    finally:
        client.close()


def lire_instantane(cur) -> dict:
    instantane = lire_postgresql(cur)
    try:
        from pymongo.errors import PyMongoError

        mongo = lire_mongodb()
        instantane.update({key: value for key, value in mongo.items() if key != 'services'})
        instantane['services'].update(mongo['services'])
    except PyMongoError as erreur:
        logger.warning('MongoDB prototype read unavailable: %s', erreur)
        instantane['services']['mongodb'] = {'status': 'unavailable'}
        instantane.update({
            'event_count': None, 'activity': [], 'incidents': [],
            'pipeline': None,
        })

    try:
        from redis.exceptions import RedisError

        redis_data = lire_redis()
        instantane.update({
            key: value for key, value in redis_data.items() if key != 'services'
        })
        instantane['services'].update(redis_data['services'])
    except RedisError as erreur:
        logger.warning('Redis prototype read unavailable: %s', erreur)
        instantane['services']['redis'] = {'status': 'unavailable'}
        instantane['incident_projection'] = None

    try:
        from psycopg2 import Error
        from axes_3_4.storage.timescale import instantane_lecture_seule

        instantane['timescale'] = instantane_lecture_seule()
        instantane['services']['timescaledb'] = {'status': 'connected'}
    except Error as erreur:
        logger.warning('TimescaleDB prototype read unavailable: %s', erreur)
        instantane['timescale'] = None
        instantane['services']['timescaledb'] = {'status': 'unavailable'}

    instantane['captured_at'] = datetime.now().astimezone().isoformat()
    return instantane
