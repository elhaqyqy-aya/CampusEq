"""Test de bout en bout : générateur + surveilleur, trois lots successifs.

Ce test prouve la prise en charge automatique demandée par le sujet : le
surveilleur traite trois lots publiés par le générateur sans redémarrage, puis
un second passage reconnaît les trois lots comme déjà chargés.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests import base

RACINE = Path(__file__).resolve().parent.parent


def _executer(arguments: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    return subprocess.run([sys.executable, *arguments], cwd=str(RACINE), env=env,
                          capture_output=True, text=True, encoding='utf-8', timeout=300)


class TestSurveillanceContinue(base.BasePipeline):
    def test_trois_lots_pris_en_charge_sans_redemarrage(self):
        flux = self.lots / 'flux'
        generation = _executer(['generer.py', '--sortie', str(flux), '--contrats', '5',
                                '--lots', '3', '--profil', 'mixte', '--intervalle', '0',
                                '--graine', '7'])
        self.assertEqual(generation.returncode, 0, generation.stderr[-2000:])
        self.assertEqual(len(list(flux.glob('lot_*'))), 3)

        surveillance = _executer(['surveiller.py', '--entree', str(flux), '--une-fois',
                                  '--intervalle', '1'])
        self.assertEqual(surveillance.returncode, 0, surveillance.stderr[-3000:])
        rapports = [ligne for ligne in surveillance.stdout.splitlines()
                    if "'status': 'CHARGE'" in ligne]
        self.assertEqual(len(rapports), 3, surveillance.stdout)

        self.assertEqual(len(self.journal('CHARGE')), 3)
        fichiers = sorted(self.rapports.glob('rapport_lot_*.json'))
        self.assertEqual(len(fichiers), 3)
        for fichier in fichiers:
            contenu = json.loads(fichier.read_text(encoding='utf-8'))
            self.assertEqual(contenu['statut'], 'CHARGE')
            self.assertGreater(contenu['compteurs']['lignes_ajoutees_en_base'], 0)

        contrats_avant = self.compter('contracts')
        rejeu = _executer(['surveiller.py', '--entree', str(flux), '--une-fois',
                           '--intervalle', '1'])
        self.assertEqual(rejeu.returncode, 0, rejeu.stderr[-3000:])
        self.assertEqual(rejeu.stdout.count("'status': 'DEJA_CHARGE'"), 3, rejeu.stdout)
        self.assertEqual(self.compter('contracts'), contrats_avant)

    def test_structure_invalide_est_un_echec_visible(self):
        # Un lot dont le CSV a été modifié après publication : le manifeste ne
        # correspond plus, le surveilleur doit échouer (code de sortie non nul).
        flux = self.lots / 'flux_casse'
        dossier = flux / 'lot_000001'
        dossier.mkdir(parents=True)
        (dossier / 'locations.csv').write_text('a,b\n1,2\n', encoding='utf-8')
        (dossier / 'referentiels.json').write_text('{}', encoding='utf-8')
        (dossier / 'manifest.json').write_text(json.dumps({
            'schema_version': 'campusequip-v2', 'campaign_id': 'x', 'batch_number': 1,
            'rows': 1, 'files': {'locations.csv': '0' * 64, 'referentiels.json': '0' * 64},
        }), encoding='utf-8')
        (dossier / 'READY').write_text('campusequip-v2\n', encoding='utf-8')

        resultat = _executer(['surveiller.py', '--entree', str(flux), '--une-fois',
                              '--intervalle', '1'])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn('ECHEC', resultat.stdout)
        self.assertEqual(self.compter('contracts'), 0)


if __name__ == '__main__':
    unittest.main()
