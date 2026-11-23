"""Validation complète : base neuve, démonstration, preuves, rapport, tests.

    python -m outils.valider

Enchaîne tout ce que le correcteur peut exécuter, dans l'ordre, et s'arrête au
premier échec. Sert de « recette » du projet : si ce script passe, les livrables
sont cohérents entre eux.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

ETAPES = (
    ('Base neuve et schéma', ['-m', 'outils.init_base', '--reinitialiser']),
    ('Démonstration (4 lots, rejeu, analyses)', ['-m', 'outils.demo',
                                                 '--sans-reinitialiser']),
    ('Preuve calcul à la main', ['-m', 'outils.preuve_calcul']),
    ('Preuve alerte', ['-m', 'outils.preuve_alerte']),
    ('Preuve bonus SQL', ['-m', 'outils.preuve_bonus']),
    ('Preuve lecture par morceaux', ['-m', 'outils.preuve_morceaux',
                                     '--contrats', '1500']),
    ('Preuve IoT', ['-m', 'outils.preuve_iot']),
    ('Rapport', ['-m', 'outils.rapport']),
)


def main() -> int:
    debut = time.perf_counter()
    for titre, arguments in ETAPES:
        print(f'\n=== {titre} ===', flush=True)
        resultat = subprocess.run([sys.executable, *arguments], cwd=str(RACINE),
                                  capture_output=True, text=True, encoding='utf-8',
                                  errors='replace')
        if resultat.returncode != 0:
            print(resultat.stdout[-3000:])
            print(resultat.stderr[-3000:], file=sys.stderr)
            return resultat.returncode
        print((resultat.stdout or '').strip().splitlines()[-1] if resultat.stdout
              else 'ok')

    print('\n=== Tests ===', flush=True)
    environnement = dict(os.environ)
    environnement.setdefault(
        'CAMPUSEQUIP_TEST_URL',
        'postgresql://postgres@127.0.0.1:5432/campusequip_test')
    environnement['PYTHONIOENCODING'] = 'utf-8'
    resultat = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                               '-t', '.'], cwd=str(RACINE), env=environnement,
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace')
    print(resultat.stderr.strip()[-400:])
    if resultat.returncode != 0:
        print(resultat.stdout[-2000:])
        return resultat.returncode

    print(f'\nRecette terminée en {time.perf_counter() - debut:.0f} s.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
