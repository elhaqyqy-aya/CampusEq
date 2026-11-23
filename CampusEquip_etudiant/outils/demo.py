"""Démonstration complète, reproductible en une commande.

    python -m outils.demo

Déroule le parcours demandé par le sujet :
    1. base neuve + schéma ;
    2. génération d'une campagne (plusieurs lots) ;
    3. surveillance : chargement automatique des lots ;
    4. rejeu : les mêmes lots sont reconnus, rien n'est ajouté ;
    5. analyses SQL, tableaux et graphiques.

Tout est écrit sous `flux_demo/`, `rapports/`, `quarantaine/` et `resultats/`.
Le script s'arrête au premier échec : aucun statut n'est annoncé sans preuve.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402
from outils import init_base  # noqa: E402


def _executer(arguments: list[str], titre: str) -> str:
    print(f'\n=== {titre} ===', flush=True)
    debut = time.perf_counter()
    resultat = subprocess.run([sys.executable, *arguments], cwd=str(RACINE),
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace')
    duree = time.perf_counter() - debut
    if resultat.stdout:
        print(resultat.stdout.rstrip())
    if resultat.returncode != 0:
        print(resultat.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(f'Échec de « {titre} » (code {resultat.returncode}).')
    print(f'({duree:.1f} s)')
    return resultat.stdout


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dossier', default='flux_demo')
    p.add_argument('--contrats', type=int, default=300)
    p.add_argument('--lots', type=int, default=4)
    p.add_argument('--graine', type=int, default=42)
    p.add_argument('--profil', choices=['propre', 'mixte'], default='mixte')
    p.add_argument('--sans-reinitialiser', action='store_true')
    a = p.parse_args()

    flux = RACINE / a.dossier
    if flux.exists():
        shutil.rmtree(flux, ignore_errors=True)

    if not a.sans_reinitialiser:
        print('=== Base neuve ===')
        init_base.reinitialiser(init_base.config.url_base())
        cnx = depot.connexion()
        try:
            depot.schema(cnx)
        finally:
            cnx.close()
        print('Schéma appliqué.')

    _executer(['generer.py', '--sortie', a.dossier, '--contrats', str(a.contrats),
               '--lots', str(a.lots), '--profil', a.profil, '--intervalle', '0',
               '--graine', str(a.graine)], 'Génération des lots')

    _executer(['surveiller.py', '--entree', a.dossier, '--une-fois', '--intervalle', '1'],
              'Chargement automatique')
    _executer(['surveiller.py', '--entree', a.dossier, '--une-fois', '--intervalle', '1'],
              'Rejeu des mêmes lots')

    _executer(['-m', 'outils.analyses'], 'Analyses SQL et graphiques')

    cnx = depot.connexion()
    try:
        with cnx.cursor() as cur:
            cur.execute("""
                SELECT b.batch_number, b.status, b.rows_accepted, b.rows_rejected,
                       b.contracts_accepted, b.rejection_rate, b.alerte_qualite
                FROM ingestion_batches b ORDER BY b.batch_id
            """)
            journaux = cur.fetchall()
            cur.execute('SELECT count(*), COALESCE(sum(line_amount), 0) FROM v_lignes_retenues')
            lignes, montant = cur.fetchone()
            cur.execute('SELECT count(*) FROM contracts')
            contrats = cur.fetchone()[0]
        cnx.rollback()
    finally:
        cnx.close()

    print('\n=== Bilan ===')
    print(f'Base : {init_base._nom_base(init_base.config.url_base())}')
    print(f'{contrats} contrats stockés, {lignes} lignes retenues, {montant} MAD')
    print('| Lot | Statut | Lignes acceptées | Rejetées | Contrats | Taux de rejet | Alerte |')
    print('|---|---|---:|---:|---:|---:|---|')
    for numero, statut, acceptees, rejetees, contrats_lot, taux, alerte in journaux:
        print(f'| {numero} | {statut} | {acceptees} | {rejetees} | {contrats_lot} | '
              f'{taux} % | {"oui" if alerte else "non"} |')
    print('\nRapports : rapports/ — Quarantaine : quarantaine/ — Résultats : resultats/')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
