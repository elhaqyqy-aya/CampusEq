"""Commandes locales de démonstration et d'exploitation des axes 3–4."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from . import pipeline
from .cache import redis_store
from .storage import mongodb, timescale


def _instant(valeur: str) -> datetime:
    instant = datetime.fromisoformat(valeur.replace('Z', '+00:00'))
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(
        timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sous = parser.add_subparsers(dest='commande', required=True)

    exporter = sous.add_parser('exporter-contrats', help='exporter les contrats acceptés')
    exporter.add_argument('--sortie', type=Path, default=Path('axes_3_4/flux/contrats_acceptes.csv'))

    traiter = sous.add_parser('traiter-lot', help='ingérer un lot terrain publié')
    traiter.add_argument('dossier', type=Path)

    cache = sous.add_parser('montant-jour', help='lire ou réchauffer le cache SQL')
    cache.add_argument('date', type=date.fromisoformat)
    cache.add_argument('--publier', action='store_true',
                       help='imposer une publication Redis (échec visible si Redis est indisponible)')
    sous.add_parser('actualiser-cache', help='invalider puis réchauffer les montants journaliers')

    sous.add_parser('reconstruire-incidents', help='reconstruire la projection Redis depuis MongoDB')
    sous.add_parser('file-incidents', help='lire le classement Redis des incidents courants')
    etat = sous.add_parser('etat-operationnel', help='lire l’état Redis avec son TTL')
    etat.add_argument('contract_id', type=int)
    historique = sous.add_parser('historique', help='lire les événements ordonnés d’un contrat')
    historique.add_argument('contract_id', type=int)
    dernier = sous.add_parser('dernier', help='lire le dernier événement d’un contrat')
    dernier.add_argument('contract_id', type=int)
    enrichi = sous.add_parser('suivi-enrichi', help='joindre contrat PostgreSQL et événements MongoDB')
    enrichi.add_argument('contract_id', type=int)
    essais = sous.add_parser('tentatives-evenements', help='lister les tentatives MongoDB d’un lot')
    essais.add_argument('campaign_id')
    essais.add_argument('batch_no', type=int)

    init_ts = sous.add_parser('initialiser-timescale', help='créer le schéma TimescaleDB')
    tentatives = sous.add_parser('tentatives', help='agréger les tentatives par fenêtre de cinq minutes')
    tentatives.add_argument('--debut', required=True, help='instant ISO-8601 UTC')
    tentatives.add_argument('--fin', required=True, help='borne de fin ISO-8601 UTC, exclusive')

    arguments = parser.parse_args(argv)
    if arguments.commande == 'exporter-contrats':
        resultat = pipeline.exporter_contrats(arguments.sortie)
    elif arguments.commande == 'traiter-lot':
        resultat = pipeline.traiter_lot_evenements(arguments.dossier)
    elif arguments.commande == 'montant-jour':
        resultat = (
            redis_store.publier_montant_journalier(arguments.date)
            if arguments.publier else redis_store.lire_montant_journalier(arguments.date)
        )
    elif arguments.commande == 'actualiser-cache':
        resultat = redis_store.rafraichir_tous_les_montants()
    elif arguments.commande == 'reconstruire-incidents':
        resultat = redis_store.reconstruire_incidents()
    elif arguments.commande == 'file-incidents':
        resultat = redis_store.lire_file_incidents()
    elif arguments.commande == 'etat-operationnel':
        resultat = redis_store.lire_etat_operationnel(arguments.contract_id)
    elif arguments.commande == 'historique':
        resultat = mongodb.historique_contrat(arguments.contract_id)
    elif arguments.commande == 'dernier':
        resultat = mongodb.dernier_evenement(arguments.contract_id)
    elif arguments.commande == 'suivi-enrichi':
        resultat = mongodb.suivi_enrichi(arguments.contract_id)
    elif arguments.commande == 'tentatives-evenements':
        resultat = mongodb.tentatives_ingestion(arguments.campaign_id, arguments.batch_no)
    elif arguments.commande == 'initialiser-timescale':
        timescale.initialiser_schema()
        resultat = {'initialized': True}
    elif arguments.commande == 'tentatives':
        debut, fin = _instant(arguments.debut), _instant(arguments.fin)
        if fin <= debut:
            parser.error('--fin doit être postérieur à --debut')
        resultat = timescale.statistiques_tentatives(debut, fin)
    else:
        parser.error('commande non prise en charge')
        return 2
    print(pipeline.lire_json(resultat))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
