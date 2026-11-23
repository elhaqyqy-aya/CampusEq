"""Cache financier et projections reconstructibles dans Redis."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from ..storage import mongodb


PREFIXE = 'campusequip:axe34'
TTL_SECONDES = 60
CLE_INCIDENTS = f'{PREFIXE}:incidents'


def cle_montant(jour: date) -> str:
    return f'{PREFIXE}:montant:{jour.isoformat()}'


def ouvrir_redis():
    import redis
    from etudiant.config import charger_env

    charger_env()
    return redis.Redis.from_url(
        os.environ.get('REDIS_URL', 'redis://127.0.0.1:6380/0'),
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=5,
    )


def _montant_postgres(jour: date) -> Decimal:
    from ..storage.postgres import session

    with session() as cnx, cnx.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(sum(line_amount), 0)
            FROM v_lignes_retenues
            WHERE start_date = %s
            """,
            (jour,),
        )
        resultat = cur.fetchone()[0]
    return Decimal(resultat)


def lire_montant_journalier(jour: date) -> dict:
    """Lit Redis d'abord, puis PostgreSQL sans transformer une panne SQL en zéro."""
    import redis

    client = ouvrir_redis()
    try:
        try:
            valeur = client.get(cle_montant(jour))
        except redis.exceptions.RedisError:
            montant = _montant_postgres(jour)
            return {'date': jour.isoformat(), 'montant': format(montant, 'f'),
                    'cache': 'UNAVAILABLE', 'source': 'postgresql'}
        if valeur is not None:
            try:
                montant_cache = Decimal(valeur)
            except InvalidOperation:
                montant_cache = Decimal('NaN')
            if montant_cache.is_finite():
                return {'date': jour.isoformat(), 'montant': valeur,
                        'cache': 'HIT', 'source': 'redis'}

        montant = _montant_postgres(jour)
        texte = format(montant, 'f')
        try:
            client.set(cle_montant(jour), texte, ex=TTL_SECONDES)
        except redis.exceptions.RedisError:
            return {'date': jour.isoformat(), 'montant': texte,
                    'cache': 'BYPASS', 'source': 'postgresql'}
        return {'date': jour.isoformat(), 'montant': texte,
                'cache': 'MISS', 'source': 'postgresql'}
    finally:
        client.close()


def publier_montant_journalier(jour: date) -> dict:
    """Calcule depuis PostgreSQL et publie ; une panne Redis reste une erreur visible."""
    montant = _montant_postgres(jour)
    texte = format(montant, 'f')
    client = ouvrir_redis()
    try:
        client.set(cle_montant(jour), texte, ex=TTL_SECONDES)
    finally:
        client.close()
    return {'date': jour.isoformat(), 'montant': texte, 'ttl_seconds': TTL_SECONDES}


def invalider_montants(jours: list[date]) -> int:
    if not jours:
        return 0
    client = ouvrir_redis()
    try:
        return int(client.delete(*(cle_montant(jour) for jour in sorted(set(jours)))))
    finally:
        client.close()


def rafraichir_tous_les_montants() -> dict:
    """Invalide puis réchauffe les dates commerciales connues après le chargement."""
    from ..storage.postgres import session

    with session() as cnx, cnx.cursor() as cur:
        cur.execute(
            """
            SELECT start_date, COALESCE(sum(line_amount), 0)
            FROM v_lignes_retenues
            GROUP BY start_date
            ORDER BY start_date
            """)
        montants = cur.fetchall()
    client = ouvrir_redis()
    try:
        cles_existantes = list(client.scan_iter(match=f'{PREFIXE}:montant:*'))
        invalides = int(client.delete(*cles_existantes)) if cles_existantes else 0
        pipeline = client.pipeline(transaction=True)
        for jour, montant in montants:
            pipeline.set(cle_montant(jour), format(Decimal(montant), 'f'), ex=TTL_SECONDES)
        pipeline.execute()
        return {'dates': len(montants), 'invalidated': invalides, 'warmed': len(montants)}
    finally:
        client.close()


def reconstruire_incidents() -> dict:
    """Reconstruit l'état opérationnel et son classement à partir de tout l'historique."""
    derniers = mongodb.derniers_etats_operationnels()
    incidents = {
        contract_id: evenement
        for contract_id, evenement in derniers.items()
        if evenement['event_type'] in {'incident', 'failure'}
    }

    redis_client = ouvrir_redis()
    suffixe = os.urandom(8).hex()
    temp = f'{CLE_INCIDENTS}:rebuild:{suffixe}'
    try:
        try:
            pipeline = redis_client.pipeline(transaction=True)
            anciennes_cles_etat = list(redis_client.scan_iter(match=f'{PREFIXE}:state:*'))
            if anciennes_cles_etat:
                pipeline.delete(*anciennes_cles_etat)
            for contract_id, evenement in derniers.items():
                pipeline.set(
                    f'{PREFIXE}:state:{contract_id}',
                    json.dumps(evenement, sort_keys=True, separators=(',', ':')),
                    ex=TTL_SECONDES,
                )
            if incidents:
                scores = {}
                for contract_id, evenement in incidents.items():
                    horodatage = datetime.strptime(
                        evenement['observed_at'], '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=timezone.utc)
                    scores[str(contract_id)] = horodatage.timestamp()
                pipeline.zadd(temp, scores)
            pipeline.execute()
            if incidents:
                redis_client.rename(temp, CLE_INCIDENTS)
            else:
                redis_client.delete(CLE_INCIDENTS)
        finally:
            redis_client.delete(temp)
    finally:
        redis_client.close()
    return {'contracts': len(derniers), 'incidents': len(incidents)}


def lire_file_incidents() -> list[dict]:
    redis_client = ouvrir_redis()
    try:
        membres = redis_client.zrange(CLE_INCIDENTS, 0, -1, withscores=True)
        return [{'contract_id': membre, 'observed_at_epoch': score} for membre, score in membres]
    finally:
        redis_client.close()


def lire_etat_operationnel(contract_id: int) -> dict:
    redis_client = ouvrir_redis()
    try:
        cle = f'{PREFIXE}:state:{contract_id}'
        valeur = redis_client.get(cle)
        if valeur is None:
            return {'contract_id': contract_id, 'state': None, 'cache': 'MISS'}
        return {
            'contract_id': contract_id,
            'state': json.loads(valeur),
            'cache': 'HIT',
            'ttl_seconds': int(redis_client.ttl(cle)),
        }
    finally:
        redis_client.close()


def verifier_projections() -> dict:
    attendus = mongodb.compte_incidents_attendu()
    redis_client = ouvrir_redis()
    try:
        obtenus = int(redis_client.zcard(CLE_INCIDENTS))
    finally:
        redis_client.close()
    if obtenus != attendus:
        raise RuntimeError(
            f'projection Redis divergente : {obtenus} incident(s), {attendus} attendu(s)')
    return {'incidents': obtenus, 'consistent': True}
