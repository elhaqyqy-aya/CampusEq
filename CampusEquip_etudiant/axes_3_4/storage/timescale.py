"""Persistance idempotente des positions et tentatives dans TimescaleDB."""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def _connexion():
    import psycopg2
    from etudiant.config import charger_env

    charger_env()
    url = os.environ.get(
        'TIMESCALE_URL',
        'postgresql://campusequip:campusequip@127.0.0.1:5435/campusequip_ts',
    )
    return psycopg2.connect(url, connect_timeout=5, application_name='campusequip-axes34')


@contextmanager
def _session():
    cnx = _connexion()
    try:
        with cnx:
            yield cnx
    finally:
        cnx.close()


def initialiser_schema() -> None:
    sql = Path(__file__).with_name('timescale.sql').read_text(encoding='utf-8')
    with _session() as cnx, cnx.cursor() as cur:
        cur.execute(sql)


def enregistrer_position(evenement: dict, observe_le: datetime,
                         campaign_id: str, batch_no: int) -> None:
    with _session() as cnx, cnx.cursor() as cur:
        cur.execute(
            """
            INSERT INTO axes34.event_positions
                (observed_at, device_id, event_id, contract_id,
                 latitude_deg, longitude_deg, campaign_id, batch_no)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (observed_at, device_id, event_id) DO NOTHING
            """,
            (
                observe_le, evenement['device_id'], evenement['event_id'],
                evenement['contract_id'], evenement['payload']['latitude'],
                evenement['payload']['longitude'], campaign_id, batch_no,
            ),
        )


def enregistrer_tentative(observe_le: datetime, dag_id: str, run_id: str,
                          task_id: str, try_number: int, status: str,
                          duration_ms: int, error_type: str | None = None) -> None:
    with _session() as cnx, cnx.cursor() as cur:
        cur.execute(
            """
            INSERT INTO axes34.task_attempts
                (observed_at, dag_id, run_id, task_id, try_number,
                 status, duration_ms, error_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (observed_at, dag_id, run_id, task_id, try_number)
            DO UPDATE SET status = EXCLUDED.status,
                          duration_ms = EXCLUDED.duration_ms,
                          error_type = EXCLUDED.error_type
            """,
            (observe_le, dag_id, run_id, task_id, try_number,
             status, duration_ms, error_type),
        )


def statistiques_tentatives(debut: datetime, fin: datetime) -> list[dict]:
    with _session() as cnx, cnx.cursor() as cur:
        cur.execute(
            """
            SELECT time_bucket(INTERVAL '5 minutes', observed_at) AS fenetre_utc,
                   task_id,
                   count(*) AS tentatives,
                   count(*) FILTER (WHERE status = 'failed') AS erreurs,
                   round(100.0 * count(*) FILTER (WHERE status = 'failed')
                         / NULLIF(count(*), 0), 2) AS taux_erreur_pct,
                   round(avg(duration_ms)::numeric, 2) AS duree_moyenne_ms
            FROM axes34.task_attempts
            WHERE observed_at >= %s AND observed_at < %s
            GROUP BY fenetre_utc, task_id
            ORDER BY fenetre_utc, task_id
            """,
            (debut, fin),
        )
        return [
            {
                'fenetre_utc': ligne[0].isoformat(),
                'task_id': ligne[1],
                'tentatives': ligne[2],
                'erreurs': ligne[3],
                'taux_erreur_pct': str(ligne[4]),
                'duree_moyenne_ms': str(ligne[5]),
            }
            for ligne in cur.fetchall()
        ]


def instantane_lecture_seule() -> dict:
    """Retourne des compteurs observés sans modifier TimescaleDB."""
    cnx = _connexion()
    try:
        cnx.set_session(readonly=True)
        with cnx.cursor() as cur:
            cur.execute("""
                SELECT count(*) AS positions,
                       max(observed_at) AS derniere_position
                FROM axes34.event_positions
            """)
            positions = cur.fetchone()
            cur.execute("""
                SELECT count(*) AS tentatives,
                       count(*) FILTER (WHERE status = 'success') AS succes,
                       count(*) FILTER (WHERE status = 'failed') AS echecs,
                       round(avg(duration_ms)::numeric, 2) AS duree_moyenne_ms,
                       max(observed_at) AS derniere_tentative
                FROM axes34.task_attempts
            """)
            tentatives = cur.fetchone()
        return {
            'positions': int(positions[0]),
            'derniere_position': positions[1].isoformat() if positions[1] else None,
            'tentatives': int(tentatives[0]),
            'succes': int(tentatives[1]),
            'echecs': int(tentatives[2]),
            'duree_moyenne_ms': (
                float(tentatives[3]) if tentatives[3] is not None else None
            ),
            'derniere_tentative': tentatives[4].isoformat() if tentatives[4] else None,
        }
    finally:
        cnx.close()
