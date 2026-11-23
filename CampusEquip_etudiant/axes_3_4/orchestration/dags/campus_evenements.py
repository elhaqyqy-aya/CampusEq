"""DAG de lots CampusEquip ; les opérations métier sont dans axes_3_4.pipeline."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.decorators import dag, task
from airflow.sensors.base import PokeReturnValue


@dag(
    dag_id='campusequip_evenements',
    schedule='*/1 * * * *',
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={
        'owner': 'campusequip',
        'retries': 2,
        'retry_delay': timedelta(seconds=30),
        'execution_timeout': timedelta(minutes=70),
    },
    tags=['campusequip', 'axes-3-4'],
)
def campus_evenements():
    @task.sensor(
        task_id='attendre_lot_ready',
        poke_interval=15,
        timeout=3600,
        mode='reschedule',
        retries=2,
        retry_delay=timedelta(seconds=30),
    )
    def attendre_lot():
        from axes_3_4.storage.mongodb import prochain_lot_pret

        chemin = prochain_lot_pret(Path(os.environ.get(
            'AXES34_EVENTS_DIR', '/opt/airflow/events')))
        if chemin is None:
            return PokeReturnValue(is_done=False)
        return PokeReturnValue(is_done=True, xcom_value=str(chemin))

    @task(task_id='controler_integrite', retries=0)
    def controler_integrite(chemin: str):
        from airflow.operators.python import get_current_context
        from axes_3_4.orchestration.airflow_support import executer_mesure
        from axes_3_4.pipeline import verifier_lot

        return executer_mesure(get_current_context(), verifier_lot, Path(chemin))

    @task(task_id='traiter_locations')
    def traiter_locations(_lot: dict):
        from airflow.operators.python import get_current_context
        from airflow.exceptions import AirflowFailException
        from axes_3_4.orchestration.airflow_support import executer_mesure
        from axes_3_4.pipeline import LotLocationsRefuse, traiter_lot_locations_configure

        try:
            resultat = executer_mesure(
                get_current_context(), traiter_lot_locations_configure)
        except LotLocationsRefuse as erreur:
            raise AirflowFailException(str(erreur)) from erreur
        return {key: resultat[key] for key in ('mode', 'status', 'batch_id', 'contracts')
                if key in resultat}

    @task(task_id='historiser_evenements')
    def historiser_evenements(chemin: str, _locations: dict):
        from airflow.operators.python import get_current_context
        from axes_3_4.orchestration.airflow_support import executer_mesure
        from axes_3_4.pipeline import traiter_lot_evenements

        return executer_mesure(get_current_context(), traiter_lot_evenements, Path(chemin))

    @task(task_id='actualiser_cache_sql')
    def actualiser_cache_sql(_evenements: dict):
        from airflow.operators.python import get_current_context
        from axes_3_4.orchestration.airflow_support import executer_mesure
        from axes_3_4.pipeline import actualiser_cache_financier

        return executer_mesure(get_current_context(), actualiser_cache_financier)

    @task(task_id='reconstruire_incidents')
    def reconstruire_incidents(_cache: dict):
        from airflow.operators.python import get_current_context
        from axes_3_4.orchestration.airflow_support import executer_mesure
        from axes_3_4.pipeline import reconstruire_file_incidents

        return executer_mesure(get_current_context(), reconstruire_file_incidents)

    @task(task_id='verifier_resultats')
    def verifier_resultats(evenements: dict, _incidents: dict):
        from airflow.operators.python import get_current_context
        from axes_3_4.orchestration.airflow_support import executer_mesure
        from axes_3_4.pipeline import verifier_sorties

        return executer_mesure(
            get_current_context(), verifier_sorties,
            evenements['campaign_id'], evenements['batch_no'],
            evenements['source_sha256'],
        )

    lot = attendre_lot()
    integre = controler_integrite(lot)
    locations = traiter_locations(integre)
    evenements = historiser_evenements(lot, locations)
    cache = actualiser_cache_sql(evenements)
    incidents = reconstruire_incidents(cache)
    verifier_resultats(evenements, incidents)


dag = campus_evenements()
