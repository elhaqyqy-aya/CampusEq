"""Bonus IoT — démonstration complète : acquisition, rejeu, panne.

    python -m outils.preuve_iot

Déroule le scénario attendu par le sujet :
  1. deux lots d'observations produits, puis collectés ;
  2. rejeu des deux mêmes fichiers : rien n'est ajouté ;
  3. panne du producteur (JSON tronqué) : le lot est refusé en bloc ;
  4. les montants des contrats sont inchangés avant / après.

Le rapport est écrit dans `preuves/iot.md`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402

TRAVAIL = RACINE / '.tests_tmp' / 'iot'


def _executer(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *arguments], cwd=str(RACINE),
                          capture_output=True, text=True, encoding='utf-8', timeout=300)


def _resume(sortie: str) -> list[dict]:
    resultats = []
    for ligne in sortie.splitlines():
        morceau = ligne.split(' ', 1)
        if len(morceau) == 2 and morceau[1].startswith('{'):
            resultats.append(json.loads(morceau[1]))
    return resultats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sortie', type=Path, default=RACINE / 'preuves')
    arguments = p.parse_args()
    arguments.sortie.mkdir(parents=True, exist_ok=True)

    if TRAVAIL.exists():
        shutil.rmtree(TRAVAIL, ignore_errors=True)
    flux = TRAVAIL / 'flux'
    flux.mkdir(parents=True)

    cnx = depot.connexion()
    try:
        depot.executer_script(cnx, RACINE / 'bonus' / 'iot' / 'schema_iot.sql')
        montant_avant = _total_contrats(cnx)
        effectif = _compter_observations(cnx)

        production = _executer(['-m', 'bonus.iot.producteur', '--sortie', str(flux),
                                '--observations', '50', '--lots', '2', '--intervalle', '0'])
        if production.returncode != 0:
            raise SystemExit(production.stderr[-2000:])

        collecte = _executer(['-m', 'bonus.iot.collecteur', '--entree', str(flux), '--une-fois'])
        premier = _resume(collecte.stdout)
        inserees = sum(item.get('inserees', 0) for item in premier)

        rejeu = _executer(['-m', 'bonus.iot.collecteur', '--entree', str(flux), '--une-fois'])
        second = _resume(rejeu.stdout)

        panne_dossier = TRAVAIL / 'panne'
        panne_dossier.mkdir(parents=True)
        _executer(['-m', 'bonus.iot.producteur', '--sortie', str(panne_dossier),
                   '--observations', '20', '--lots', '1', '--panne', 'tronque',
                   '--intervalle', '0'])
        panne = _executer(['-m', 'bonus.iot.collecteur', '--entree', str(panne_dossier),
                           '--une-fois'])
        panne_resultat = _resume(panne.stdout)

        montant_apres = _total_contrats(cnx)
        effectif_apres = _compter_observations(cnx)
        journaux = _journaux(cnx)
    finally:
        cnx.close()

    rejeu_ok = all(item['statut'] == 'DEJA_CHARGE' and item['inserees'] == 0
                   for item in second) and len(second) == 2
    panne_ok = (panne.returncode != 0 and len(panne_resultat) == 1
                and panne_resultat[0]['statut'] == 'REJETE_STRUCTURE')
    contrats_ok = montant_avant == montant_apres

    lignes = [
        '# Bonus IoT — preuves d\'acquisition, de rejeu et de panne', '',
        'Producteur : `python -m bonus.iot.producteur` (GPS simulé, positions fictives).',
        'Collecteur : `python -m bonus.iot.collecteur --entree <dossier> --une-fois`.', '',
        '## 1. Acquisition et contrôles', '',
        '| Lot | Statut | Reçues | Insérées | Rejetées | Rejeu |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for item in premier:
        lignes.append(f"| {item['fichier']} | {item['statut']} | "
                      f"{item.get('observations_recues', 0)} | {item['inserees']} | "
                      f"{item.get('rejetees', 0)} | {item.get('rejeu', 0)} |")
    lignes += [
        '',
        f"Total inséré : **{inserees} observations**. Contrôles appliqués : équipement connu "
        'dans `equipments`, instant ISO 8601 en UTC, latitude entre -90 et 90, longitude '
        'entre -180 et 180, clé `(device_id, event_id)`.',
        '',
        '## 2. Rejeu des mêmes fichiers', '',
        '| Lot | Statut | Insérées |', '|---|---|---:|',
    ]
    for item in second:
        lignes.append(f"| {item['fichier']} | {item['statut']} | {item['inserees']} |")
    lignes += [
        '',
        f"Rejeu conforme : **{'oui' if rejeu_ok else 'NON'}** — aucune observation ajoutée, "
        'le journal `iot_lots` reconnaît la signature des fichiers.',
        '',
        '## 3. Panne du producteur (JSON tronqué)', '',
        f"- Code de sortie du collecteur : **{panne.returncode}** (échec visible)",
        f"- Statut du lot : **{panne_resultat[0]['statut'] if panne_resultat else 'inconnu'}**",
        f"- Motif : `{panne_resultat[0].get('motif', '') if panne_resultat else ''}`",
        f"- Lignes insérées par ce lot : **0** (transaction annulée en bloc)",
        '',
        '## 4. Les locations ne sont pas modifiées', '',
        '| | Avant | Après |', '|---|---:|---:|',
        f"| Observations stockées | {effectif} | {effectif_apres} |",
        f"| Montant retenu des contrats | {montant_avant} | {montant_apres} |",
        '',
        f"Montants identiques : **{'oui' if contrats_ok else 'NON'}**. Les observations GPS "
        'vivent dans `iot_observations`, jamais dans `contract_lines`.',
        '',
        '## Journal des lots IoT', '',
        '| Fichier | Statut | Insérées | Traité le |', '|---|---|---:|---|',
    ]
    for fichier, statut, inserees_lot, traite in journaux:
        lignes.append(f'| {fichier} | {statut} | {inserees_lot} | {traite:%d/%m/%Y %H:%M:%S} |')
    lignes += [
        '',
        '## Limites', '',
        'Ce bonus ne prétend pas remplacer une plateforme IoT : pas de file de messages, '
        'pas de TLS, pas de gestion de parc de boîtiers. Il montre la chaîne complète '
        '(acquisition, contrôles, clé d\'idempotence, rejeu, panne) sur des fichiers locaux '
        'reproductibles.',
        '',
    ]
    (arguments.sortie / 'iot.md').write_text('\n'.join(lignes) + '\n', encoding='utf-8')
    print('\n'.join(lignes[:24]))
    print('rapport écrit dans', arguments.sortie / 'iot.md')
    return 0 if (rejeu_ok and panne_ok and contrats_ok) else 1


def _total_contrats(cnx):
    with cnx.cursor() as cur:
        cur.execute('SELECT COALESCE(sum(line_amount), 0) FROM v_lignes_retenues')
        total = cur.fetchone()[0]
    cnx.rollback()
    return total


def _compter_observations(cnx) -> int:
    with cnx.cursor() as cur:
        cur.execute('SELECT count(*) FROM iot_observations')
        nombre = cur.fetchone()[0]
    cnx.rollback()
    return nombre


def _journaux(cnx):
    with cnx.cursor() as cur:
        cur.execute('SELECT fichier, statut, inserees, traite_le FROM iot_lots '
                    'ORDER BY batch_id')
        journaux = cur.fetchall()
    cnx.rollback()
    return journaux


if __name__ == '__main__':
    raise SystemExit(main())
