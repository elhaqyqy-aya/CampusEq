"""Adaptateur de mesures Airflow ; les fonctions métier restent autonomes."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable


def executer_mesure(contexte: dict, fonction: Callable, *arguments) -> object:
    ti = contexte['ti']
    commencee = datetime.now(timezone.utc)
    depart = time.perf_counter()
    try:
        resultat = fonction(*arguments)
    except Exception as erreur:
        duree_ms = max(0, round((time.perf_counter() - depart) * 1000))
        try:
            from ..storage.timescale import enregistrer_tentative

            enregistrer_tentative(
                commencee, contexte['dag'].dag_id, contexte['run_id'], ti.task_id,
                ti.try_number, 'failed', duree_ms, type(erreur).__name__,
            )
        except Exception as erreur_mesure:
            raise RuntimeError(
                f'{type(erreur).__name__}: {erreur}; échec de la mesure TimescaleDB : '
                f'{type(erreur_mesure).__name__}: {erreur_mesure}'
            ) from erreur
        raise

    duree_ms = max(0, round((time.perf_counter() - depart) * 1000))
    from ..storage.timescale import enregistrer_tentative

    enregistrer_tentative(
        commencee, contexte['dag'].dag_id, contexte['run_id'], ti.task_id,
        ti.try_number, 'success', duree_ms,
    )
    return resultat
