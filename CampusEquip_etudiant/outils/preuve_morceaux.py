"""Bonus 3 (suite) : preuve que la lecture par morceaux prend les mêmes décisions.

    python -m outils.preuve_morceaux

Le script génère un lot volumineux avec le générateur du kit, fait tourner :
  1. la lecture complète (référence) ;
  2. la lecture par morceaux de 100, 1 000 et 10 000 lignes ;
puis compare les décisions ligne à ligne, les compteurs, la durée et le pic
mémoire. Le rapport est écrit dans `preuves/lecture_morceaux.md`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bonus.lecture_morceaux import analyser_par_morceaux, empreinte_decisions  # noqa: E402
from etudiant import traitement  # noqa: E402

TRAVAIL = RACINE / '.tests_tmp' / 'volumineux'


def generer(contrats: int, graine: int) -> Path:
    if TRAVAIL.exists():
        shutil.rmtree(TRAVAIL, ignore_errors=True)
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    commande = [sys.executable, 'generer.py', '--sortie', str(TRAVAIL), '--contrats',
                str(contrats), '--lots', '1', '--profil', 'mixte', '--intervalle', '0',
                '--graine', str(graine)]
    resultat = subprocess.run(commande, cwd=str(RACINE), capture_output=True, text=True,
                              encoding='utf-8')
    if resultat.returncode != 0:
        raise SystemExit(resultat.stderr[-2000:])
    return TRAVAIL / 'lot_000001'


def mesurer(fonction):
    """Exécute une fonction et renvoie (résultat, durée en s, pic mémoire en Mio)."""
    tracemalloc.start()
    debut = time.perf_counter()
    resultat = fonction()
    duree = time.perf_counter() - debut
    _, pic = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return resultat, duree, pic / (1024 * 1024)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--contrats', type=int, default=3000)
    p.add_argument('--graine', type=int, default=11)
    p.add_argument('--sortie', type=Path, default=RACINE / 'preuves')
    arguments = p.parse_args()
    arguments.sortie.mkdir(parents=True, exist_ok=True)

    dossier = generer(arguments.contrats, arguments.graine)
    manifeste = json.loads((dossier / 'manifest.json').read_text(encoding='utf-8'))
    print(f"lot généré : {manifeste['rows']} lignes, "
          f"{manifeste['contracts_requested']} contrats demandés")

    complet, duree_complet, pic_complet = mesurer(
        lambda: traitement.preparer_lot(dossier, manifeste).analyse)
    reference = empreinte_decisions(complet)
    print(f'lecture complète : {len(complet.lignes)} lignes décidées, '
          f'{duree_complet:.2f} s, {pic_complet:.1f} Mio')

    mesures = [('complète', 1, duree_complet, pic_complet, len(reference), True)]
    for taille in (100, 1000, 10000):
        def travail(taille=taille):
            return analyser_par_morceaux(dossier, manifeste, taille)

        (analyse, stats), duree, pic = mesurer(travail)
        identique = empreinte_decisions(analyse) == reference
        mesures.append((f'{taille} lignes', stats['morceaux'], duree, pic,
                        len(analyse.lignes), identique))
        print(f"morceaux de {taille:>6} : {stats['morceaux']:>3} morceaux, "
              f"{duree:.2f} s, {pic:.1f} Mio, identique={identique}")

    identiques = all(mesure[5] for mesure in mesures[1:])
    lignes = [
        '# Bonus 3 — lecture par morceaux', '',
        f"Lot de test : **{manifeste['rows']} lignes**, profil `{manifeste['profile']}`, "
        f"généré par `generer.py --contrats {arguments.contrats} --lots 1 "
        f"--graine {arguments.graine}`.", '',
        '| Mode de lecture | Morceaux | Durée | Pic mémoire | Lignes décidées | '
        'Décisions identiques |',
        '|---|---:|---:|---:|---:|---|',
    ]
    for nom, morceaux, duree, pic, nb_lignes, identique in mesures:
        lignes.append(f'| {nom} | {morceaux} | {duree:.2f} s | {pic:.1f} Mio | '
                      f'{nb_lignes} | {"oui" if identique else "NON"} |')
    lignes += [
        '',
        f"**Résultat : {'les quatre lectures prennent exactement les mêmes décisions' if identiques else 'ÉCART DÉTECTÉ'}** "
        '(même verdict, mêmes motifs, mêmes anomalies, mêmes montants, aux mêmes '
        'positions).',
        '',
        '## Pourquoi les contrats ne sont pas coupés',
        '',
        '`bonus/lecture_morceaux.py` ne décide rien à la fin d\'un morceau : il empile '
        'les lignes contrôlées, puis appelle une seule fois '
        '`regles.finaliser_analyse`, qui vérifie la cohérence de chaque contrat et '
        'calcule les montants. Un contrat dont les lignes tombent dans deux morceaux '
        'est donc traité exactement comme en lecture complète.',
        '',
        '## Limite honnête',
        '',
        'La mémoire reste proportionnelle au nombre de lignes décidées : le script '
        'garde une décision compacte par ligne, mais libère les lignes brutes du CSV '
        'après chaque morceau. Pour un lot qui ne tiendrait pas en mémoire, l\'étape '
        'suivante serait d\'écrire ces décisions dans une table temporaire PostgreSQL '
        'au fil de l\'eau, puis de les joindre pour la cohérence des contrats.',
        '',
    ]
    (arguments.sortie / 'lecture_morceaux.md').write_text('\n'.join(lignes) + '\n',
                                                          encoding='utf-8')
    print('rapport écrit dans', arguments.sortie / 'lecture_morceaux.md')
    return 0 if identiques else 1


if __name__ == '__main__':
    raise SystemExit(main())
