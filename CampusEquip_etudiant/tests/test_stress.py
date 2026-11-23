from __future__ import annotations

import argparse
import csv
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import generer
from dashboard import app as dashboard_app
from outils.stress import parse_debits
from tests import base


class TestGenerationStress(unittest.TestCase):
    def test_paliers_separes_et_valides(self):
        self.assertEqual(parse_debits('10, 100,1000,10000'), [10, 100, 1000, 10000])
        for texte in ('', '0,10', '-1', '10,10', 'abc'):
            with self.subTest(texte=texte), self.assertRaises(argparse.ArgumentTypeError):
                parse_debits(texte)

    def test_lot_de_charge_contient_exactement_le_nombre_demande(self):
        with tempfile.TemporaryDirectory() as temporaire:
            flux = Path(temporaire)
            etat = {
                'contracts': 10, 'contract_stride': 10, 'seed': 42,
                'profile': 'mixte', 'next_batch': 1,
                'campaign_id': str(uuid.uuid4()),
            }
            premier, lignes_premier = generer.make_batch(
                flux, etat, event_count=4, target_events_per_second=4,
                inject_missing=True)
            second, lignes_second = generer.make_batch(
                flux, etat, event_count=3, target_events_per_second=3)

            self.assertEqual((lignes_premier, lignes_second), (4, 3))
            for dossier, nombre in ((premier, 4), (second, 3)):
                manifeste = json.loads(
                    (dossier / 'manifest.json').read_text(encoding='utf-8'))
                with (dossier / 'locations.csv').open(
                        encoding='utf-8', newline='') as fichier:
                    lignes = list(csv.DictReader(fichier))
                self.assertEqual(manifeste['rows'], nombre)
                self.assertEqual(manifeste['events_requested'], nombre)
                self.assertEqual(
                    manifeste['target_events_per_second'], nombre)
                self.assertEqual(len(lignes), nombre)
                if dossier == premier:
                    self.assertEqual(manifeste['missing_fields_injected'], 1)
                    self.assertEqual(
                        sum(not ligne['unit_rate'] for ligne in lignes), 1)
            with (premier / 'locations.csv').open(
                    encoding='utf-8', newline='') as fichier:
                ids_premier = {
                    int(ligne['contract_id']) for ligne in csv.DictReader(fichier)}
            with (second / 'locations.csv').open(
                    encoding='utf-8', newline='') as fichier:
                ids_second = {
                    int(ligne['contract_id']) for ligne in csv.DictReader(fichier)}
            self.assertFalse(ids_premier & ids_second)

    def test_generateur_habituel_garde_son_manifest_et_ses_lignes(self):
        with tempfile.TemporaryDirectory() as temporaire:
            flux = Path(temporaire)
            etat = {
                'contracts': 10, 'seed': 42, 'profile': 'propre',
                'next_batch': 1, 'campaign_id': str(uuid.uuid4()),
            }
            dossier, nombre = generer.make_batch(flux, etat)
            manifeste = json.loads(
                (dossier / 'manifest.json').read_text(encoding='utf-8'))
            with (dossier / 'locations.csv').open(
                    encoding='utf-8', newline='') as fichier:
                lignes = list(csv.DictReader(fichier))
            self.assertEqual(nombre, len(lignes))
            self.assertEqual(manifeste['contracts_requested'], 10)
            self.assertNotIn('events_requested', manifeste)
            self.assertNotIn('target_events_per_second', manifeste)

    def test_debit_invalide_ne_reserve_pas_de_numero(self):
        with tempfile.TemporaryDirectory() as temporaire:
            flux = Path(temporaire)
            etat = {
                'contracts': 2, 'seed': 1, 'profile': 'propre',
                'next_batch': 1, 'campaign_id': str(uuid.uuid4()),
            }
            with self.assertRaises(ValueError):
                generer.make_batch(flux, etat, event_count=0)
            self.assertEqual(etat['next_batch'], 1)
            self.assertFalse((flux / 'generator-state.json').exists())


class TestStressDashboard(base.BasePipeline):
    def test_page_api_et_execution_isolee(self):
        client = dashboard_app.app.test_client()
        page = client.get('/stress')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Stress test', page.data)
        self.assertIn(b'10 000', page.data)

        invalide = client.post('/api/stress/start', json={
            'debits': [50], 'duree': 1,
        })
        self.assertEqual(invalide.status_code, 400)

        demarrage = client.post('/api/stress/start', json={
            'debits': [10], 'duree': 1,
        })
        self.assertEqual(demarrage.status_code, 202, demarrage.get_json())
        execution = demarrage.get_json()['execution']
        limite = time.monotonic() + 20
        while time.monotonic() < limite:
            etat = client.get(f"/api/stress/{execution['id']}").get_json()['execution']
            if etat['statut'] in {'termine', 'arrete', 'echec'}:
                break
            time.sleep(0.05)

        self.assertEqual(etat['statut'], 'termine', etat)
        self.assertEqual(etat['mesures']['evenements_generes'], 10)
        self.assertEqual(etat['mesures']['evenements_recus'], 10)
        self.assertEqual(etat['mesures']['evenements_perdus_non_recus'], 0)
        self.assertTrue(Path(etat['rapport']).is_file())
        rapport = client.get(f"/api/stress/{execution['id']}/rapport")
        self.assertEqual(rapport.status_code, 200)
        self.assertEqual(rapport.mimetype, 'application/json')
        rapport.close()
        Path(etat['rapport']).unlink(missing_ok=True)

        self.assertEqual(self.compter('contracts'), 0)
        schemas_restants = self.lignes(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'ce_stress_%%'")
        self.assertEqual(schemas_restants, [])


if __name__ == '__main__':
    unittest.main()
