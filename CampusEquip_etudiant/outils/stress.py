"""Banc de charge local : événements simulés et réellement chargés dans PostgreSQL.

Exemple :
    python -m outils.stress --debits 10,100,1000,10000 --duree 3
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import generer


def parse_debits(texte: str) -> list[int]:
    try:
        debits = [int(element.strip()) for element in texte.split(',')]
    except ValueError:
        raise argparse.ArgumentTypeError('utilisez des débits entiers séparés par des virgules') from None
    if not debits or any(debit <= 0 for debit in debits):
        raise argparse.ArgumentTypeError('chaque débit doit être strictement positif')
    if len(set(debits)) != len(debits):
        raise argparse.ArgumentTypeError('un débit ne peut apparaître qu’une seule fois')
    return debits


def _memoire_pic_mib() -> float:
    if os.name == 'nt':
        class CompteursMemoire(ctypes.Structure):
            _fields_ = [
                ('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            ]

        noyau = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        noyau.GetCurrentProcess.restype = ctypes.c_void_p
        handle = noyau.GetCurrentProcess()
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(CompteursMemoire), ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        compteurs = CompteursMemoire()
        compteurs.cb = ctypes.sizeof(compteurs)
        if not psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(compteurs), compteurs.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return compteurs.PeakWorkingSetSize / (1024 * 1024)

    import resource

    pic = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return pic / ((1024 * 1024) if sys.platform == 'darwin' else 1024)


def verifier_base_vierge() -> None:
    """Refuse une base déjà utilisée; le banc ne réinitialise jamais la base."""
    from etudiant import depot

    cnx = depot.connexion()
    try:
        with cnx.cursor() as cur:
            cur.execute("""
                SELECT (SELECT count(*) FROM contracts),
                       (SELECT count(*) FROM ingestion_batches),
                       (SELECT count(*) FROM lab_config)
            """)
            contrats, lots, configuration = cur.fetchone()
        cnx.rollback()
    finally:
        cnx.close()
    if contrats or lots or configuration:
        raise RuntimeError(
            'La base n’est pas vierge. Utilisez une base PostgreSQL dédiée au stress test; '
            'aucune donnée existante n’a été modifiée.')


def _nouvelle_etape(debit: int) -> dict:
    return {
        'debit_cible_evenements_s': debit,
        'duree_generation_s': 0.0,
        'lots_generes': 0,
        'evenements_generes': 0,
        'lots_recus': 0,
        'evenements_recus': 0,
        'evenements_traites': 0,
        'doublons': 0,
        'rejets': 0,
        'refus_structure': 0,
        'anomalies': 0,
        'champs_manquants': 0,
        'lignes_avec_donnees_manquantes': 0,
        'octets_csv': 0,
        'temps_traitement_lots_s': 0.0,
        'latences_lots_ms': [],
        'pic_backlog_evenements': 0,
    }


def _percentile95(valeurs: list[float]) -> float:
    if not valeurs:
        return 0.0
    return sorted(valeurs)[max(0, math.ceil(len(valeurs) * 0.95) - 1)]


def executer(debits: list[int], duree: int, graine: int = 42,
             connexion_factory: Callable | None = None,
             on_progress: Callable[[dict], None] | None = None,
             stop_event: threading.Event | None = None) -> dict:
    """Exécute les paliers dans une campagne et renvoie les mesures observées."""
    from etudiant import config, traitement

    if not debits or any(debit <= 0 for debit in debits):
        raise ValueError('Les débits doivent être des entiers strictement positifs.')
    if len(set(debits)) != len(debits):
        raise ValueError('Les débits doivent être uniques.')
    if duree <= 0:
        raise ValueError('La durée de chaque palier doit être strictement positive.')
    contrat_max = max(debits) * len(debits) * duree
    if contrat_max > 2_147_483_647:
        raise ValueError('Le volume demandé dépasse la plage des identifiants PostgreSQL.')

    etapes = {debit: _nouvelle_etape(debit) for debit in debits}
    statistiques = {
        'generes': 0, 'recus': 0, 'traites': 0, 'doublons': 0,
        'backlog_max': 0,
    }
    palier_actif: int | None = None
    erreurs: list[str] = []
    verrou = threading.Lock()
    arret = stop_event or threading.Event()
    generation_terminee = threading.Event()

    def publier_progression() -> None:
        if on_progress is None:
            return
        with verrou:
            progression = {
                'evenements_generes': statistiques['generes'],
                'evenements_recus': statistiques['recus'],
                'evenements_traites': statistiques['traites'],
                'doublons': statistiques['doublons'],
                'backlog_max_evenements': statistiques['backlog_max'],
                'etapes': [
                    {cle: valeur for cle, valeur in etape.items()
                     if cle != 'latences_lots_ms'}
                    for etape in etapes.values()
                ],
            }
        on_progress(progression)

    def actualiser_backlog() -> None:
        backlog = max(0, statistiques['generes'] - statistiques['traites']
                     - statistiques['doublons'])
        statistiques['backlog_max'] = max(statistiques['backlog_max'], backlog)
        if palier_actif is not None:
            etapes[palier_actif]['pic_backlog_evenements'] = max(
                etapes[palier_actif]['pic_backlog_evenements'], backlog)

    def generer_flux(flux: Path, etat: dict) -> None:
        nonlocal palier_actif
        try:
            for debit in debits:
                etape = etapes[debit]
                with verrou:
                    palier_actif = debit
                debut_palier = time.perf_counter()
                for seconde in range(duree):
                    if arret.is_set():
                        return
                    cible = debut_palier + seconde
                    with verrou:
                        statistiques['generes'] += debit
                        actualiser_backlog()
                    try:
                        generer.make_batch(
                            flux, etat, event_count=debit,
                            target_events_per_second=debit, inject_missing=True)
                    except Exception:
                        with verrou:
                            statistiques['generes'] -= debit
                            actualiser_backlog()
                        raise
                    with verrou:
                        etape['lots_generes'] += 1
                        etape['evenements_generes'] += debit
                    publier_progression()
                    attente = cible + 1 - time.perf_counter()
                    if attente > 0:
                        arret.wait(attente)
                etape['duree_generation_s'] = round(time.perf_counter() - debut_palier, 3)
                with verrou:
                    palier_actif = None
        except Exception as erreur:
            with verrou:
                erreurs.append(f'Génération: {type(erreur).__name__}: {erreur}')
            arret.set()
        finally:
            generation_terminee.set()

    def traiter_flux(flux: Path) -> None:
        numero = 1
        try:
            while True:
                dossier = flux / f'lot_{numero:06d}'
                if dossier.is_dir():
                    manifeste = json.loads(
                        (dossier / 'manifest.json').read_text(encoding='utf-8'))
                    debit = manifeste.get('target_events_per_second')
                    if debit not in etapes:
                        raise ValueError(f'Débit absent ou invalide dans {dossier.name}')
                    debut_lot = time.perf_counter()
                    attendu = datetime.fromisoformat(
                        manifeste['created_at'].replace('Z', '+00:00'))
                    resultat = traitement.traiter_lot(
                        dossier, manifeste, connexion_factory=connexion_factory,
                        sorties=sorties)
                    duree_lot = time.perf_counter() - debut_lot
                    if resultat.get('status') not in {
                            'CHARGE', 'DEJA_CHARGE', 'REJETE_STRUCTURE'}:
                        raise RuntimeError(
                            f"{dossier.name}: statut inattendu {resultat.get('status')!r}")

                    compteur = resultat
                    recues = int(manifeste['rows'])
                    traitees = int(compteur.get('lignes_acceptees', 0)) + int(
                        compteur.get('lignes_rejetees', 0))
                    doublons = int(compteur.get('doublons_retires', 0))
                    octets = (dossier / 'locations.csv').stat().st_size
                    latence = max(0.0, (datetime.now(timezone.utc) - attendu).total_seconds() * 1000)
                    rapport = json.loads(
                        Path(resultat['rapport']).read_text(encoding='utf-8'))
                    champs_manquants = 0
                    lignes_manquantes = 0
                    for rejet in rapport.get('rejets', []):
                        brutes = rejet.get('valeurs_brutes')
                        if isinstance(brutes, dict):
                            nb_manquants = sum(
                                valeur is None or (
                                    isinstance(valeur, str) and not valeur.strip())
                                for valeur in brutes.values())
                            champs_manquants += nb_manquants
                            lignes_manquantes += int(nb_manquants > 0)
                    with verrou:
                        etape = etapes[debit]
                        statistiques['recus'] += recues
                        statistiques['traites'] += traitees
                        statistiques['doublons'] += doublons
                        actualiser_backlog()
                        etape['lots_recus'] += 1
                        etape['evenements_recus'] += recues
                        etape['evenements_traites'] += traitees
                        etape['doublons'] += doublons
                        etape['rejets'] += int(compteur.get('lignes_rejetees', 0))
                        etape['refus_structure'] += int(
                            resultat['status'] == 'REJETE_STRUCTURE')
                        etape['anomalies'] += int(compteur.get('anomalies', 0))
                        etape['champs_manquants'] += champs_manquants
                        etape['lignes_avec_donnees_manquantes'] += lignes_manquantes
                        etape['octets_csv'] += octets
                        etape['temps_traitement_lots_s'] += duree_lot
                        etape['latences_lots_ms'].append(latence)
                    publier_progression()
                    numero += 1
                    continue
                if generation_terminee.is_set():
                    break
                time.sleep(0.025)
        except Exception as erreur:
            with verrou:
                erreurs.append(f'Traitement: {type(erreur).__name__}: {erreur}')
            arret.set()

    debut_cpu = time.process_time()
    debut_total = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='campusequip-stress-') as temporaire:
        racine_temp = Path(temporaire)
        flux = racine_temp / 'flux'
        rapports = racine_temp / 'rapports'
        quarantaine = racine_temp / 'quarantaine'
        flux.mkdir()
        rapports.mkdir()
        quarantaine.mkdir()

        sorties = config.Sorties(rapports, quarantaine)
        etat = {
            'contracts': max(debits),
            'contract_stride': max(debits),
            'seed': graine,
            'profile': 'mixte',
            'next_batch': 1,
            'campaign_id': str(uuid.uuid4()),
        }
        producteur = threading.Thread(target=generer_flux, args=(flux, etat), daemon=True)
        consommateur = threading.Thread(target=traiter_flux, args=(flux,), daemon=True)
        consommateur.start()
        producteur.start()
        producteur.join()
        consommateur.join()

    duree_totale = time.perf_counter() - debut_total
    cpu_s = time.process_time() - debut_cpu
    for etape in etapes.values():
        etape['debit_generation_effectif_eps'] = round(
            etape['evenements_generes'] / etape['duree_generation_s'], 2
        ) if etape['duree_generation_s'] else 0.0
        etape['debit_traitement_effectif_eps'] = round(
            etape['evenements_traites'] / etape['temps_traitement_lots_s'], 2
        ) if etape['temps_traitement_lots_s'] else 0.0
        latences = etape.pop('latences_lots_ms')
        etape['latence_moyenne_lot_ms'] = round(
            sum(latences) / len(latences), 2) if latences else 0.0
        etape['latence_p95_lot_ms'] = round(_percentile95(latences), 2)
        etape['temps_traitement_lots_s'] = round(etape['temps_traitement_lots_s'], 3)

    total_genere = statistiques['generes']
    total_recu = statistiques['recus']
    total_traite = statistiques['traites']
    total_doublons = statistiques['doublons']
    return {
        'horodatage': datetime.now(timezone.utc).isoformat(),
        'base': config.nom_base(),
        'debits_testes_evenements_s': debits,
        'duree_cible_palier_s': duree,
        'duree_totale_s': round(duree_totale, 3),
        'evenements_generes': total_genere,
        'evenements_recus': total_recu,
        'evenements_traites': total_traite,
        'doublons': total_doublons,
        'erreurs': sum(etape['rejets'] + etape['refus_structure']
                       for etape in etapes.values()) + len(erreurs),
        'erreurs_pipeline': sum(etape['refus_structure']
                                for etape in etapes.values()) + len(erreurs),
        'rejets': sum(etape['rejets'] for etape in etapes.values()),
        'anomalies': sum(etape['anomalies'] for etape in etapes.values()),
        'champs_manquants': sum(etape['champs_manquants']
                                for etape in etapes.values()),
        'lignes_avec_donnees_manquantes': sum(
            etape['lignes_avec_donnees_manquantes'] for etape in etapes.values()),
        'evenements_perdus_non_recus': max(0, total_genere - total_recu),
        'evenements_en_attente_ou_non_comptabilises': max(
            0, total_genere - total_traite - total_doublons),
        'backlog_max_evenements': statistiques['backlog_max'],
        'octets_csv_ingere': sum(etape['octets_csv'] for etape in etapes.values()),
        'cpu_processus_python_s': round(cpu_s, 3),
        'cpu_processus_python_pct_d_un_coeur': round(
            cpu_s / duree_totale * 100, 1) if duree_totale else 0.0,
        'memoire_pic_processus_python_mib': round(_memoire_pic_mib(), 2),
        'etapes': list(etapes.values()),
        'details_erreurs': erreurs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--debits', type=parse_debits, default=parse_debits(
        '10,100,1000,10000'), help='événements/s par palier, séparés par des virgules')
    parser.add_argument('--duree', type=int, default=3,
                        help='durée de chaque palier en secondes (défaut : 3)')
    parser.add_argument('--graine', type=int, default=42)
    parser.add_argument('--rapport', type=Path,
                        help='fichier JSON de sortie (défaut : resultats/stress_<date>.json)')
    arguments = parser.parse_args()
    if arguments.duree <= 0:
        parser.error('--duree doit être strictement positive')
    contrat_max = max(arguments.debits) * len(arguments.debits) * arguments.duree
    if contrat_max > 2_147_483_647:
        parser.error('le volume demandé dépasse la plage des identifiants PostgreSQL')

    try:
        verifier_base_vierge()
        resultat = executer(arguments.debits, arguments.duree, arguments.graine)
    except Exception as erreur:
        print(f'Échec du stress test : {type(erreur).__name__}: {erreur}')
        return 1

    chemin = arguments.rapport or (
        Path('resultats') / f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + '.tmp')
    temporaire.write_text(json.dumps(resultat, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8')
    os.replace(temporaire, chemin)
    for etape in resultat['etapes']:
        print(f"cible={etape['debit_cible_evenements_s']:>6} événements/s  "
              f"générés={etape['evenements_generes']:>7}  "
              f"reçus={etape['evenements_recus']:>7}  "
              f"traités={etape['evenements_traites']:>7}  "
              f"latence p95={etape['latence_p95_lot_ms']:>8} ms  "
              f"backlog max={etape['pic_backlog_evenements']:>7}")
    print(f"Qualité: {resultat['doublons']} doublons, {resultat['rejets']} rejets, "
          f"{resultat['champs_manquants']} champ(s) manquant(s), "
          f"{resultat['anomalies']} anomalie(s)")
    print(f"Perdus/non reçus: {resultat['evenements_perdus_non_recus']}  |  "
          f"En attente/non comptabilisés: "
          f"{resultat['evenements_en_attente_ou_non_comptabilises']}")
    print(f"CSV ingéré: {resultat['octets_csv_ingere']} octets")
    print(f"CPU Python: {resultat['cpu_processus_python_s']} s  |  "
          f"pic RAM Python: {resultat['memoire_pic_processus_python_mib']} Mio")
    print(f"Rapport: {chemin}")
    if resultat['details_erreurs']:
        for erreur in resultat['details_erreurs']:
            print(erreur)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
