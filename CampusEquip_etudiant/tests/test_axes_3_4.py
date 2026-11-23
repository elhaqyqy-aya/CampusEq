from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from axes_3_4 import events
from axes_3_4.cache import redis_store
from axes_3_4 import pipeline


class EventValidationTests(unittest.TestCase):
    def test_normalizes_ids_and_type_and_preserves_utc_source(self):
        source = {
            'device_id': ' gps_01 ',
            'event_id': ' e-1 ',
            'contract_id': 2001,
            'event_type': ' INCIDENT ',
            'observed_at': '2026-11-01T10:00:00Z',
            'payload': {'detail': 'x'},
        }
        event, instant = events.normaliser_evenement(source)
        self.assertEqual(event['device_id'], 'gps_01')
        self.assertEqual(event['event_type'], 'incident')
        self.assertEqual(event['observed_at'], source['observed_at'])
        self.assertEqual(instant.isoformat(), '2026-11-01T10:00:00+00:00')

    def test_rejects_bool_contract_id_and_invalid_calendar_date(self):
        base = {
            'device_id': 'gps-1', 'event_id': 'e-1', 'contract_id': True,
            'event_type': 'return', 'observed_at': '2026-11-01T10:00:00Z', 'payload': {},
        }
        with self.assertRaisesRegex(events.EvenementInvalide, 'CONTRACT_ID'):
            events.normaliser_evenement(base)
        base['contract_id'] = 1
        base['observed_at'] = '2026-02-30T10:00:00Z'
        with self.assertRaisesRegex(events.EvenementInvalide, 'OBSERVED_AT'):
            events.normaliser_evenement(base)

    def test_position_requires_exact_finite_bounded_coordinates(self):
        base = {
            'device_id': 'gps-1', 'event_id': 'e-1', 'contract_id': 1,
            'event_type': 'position', 'observed_at': '2026-11-01T10:00:00Z',
            'payload': {'latitude': 90.01, 'longitude': 0},
        }
        with self.assertRaisesRegex(events.EvenementInvalide, 'COORDONNEES'):
            events.normaliser_evenement(base)
        base['payload'] = {'latitude': True, 'longitude': 0}
        with self.assertRaisesRegex(events.EvenementInvalide, 'COORDONNEES'):
            events.normaliser_evenement(base)
        base['payload'] = {'latitude': 1, 'longitude': 2, 'altitude': 3}
        with self.assertRaisesRegex(events.EvenementInvalide, 'COORDONNEES'):
            events.normaliser_evenement(base)

    def test_reference_check_is_individual_and_boolean_is_not_a_contract(self):
        known = {
            'device_id': 'gps-1', 'event_id': 'e-1', 'contract_id': 2001,
            'event_type': 'return', 'observed_at': '2026-11-01T10:00:00Z', 'payload': {},
        }
        unknown = dict(known, contract_id=9999)
        invalid = dict(known, contract_id=True)
        lines = events.convertir_lignes([(1, known), (2, unknown), (3, invalid)], {2001})
        self.assertIn('event', lines[0])
        self.assertEqual(lines[1]['reason'], 'CONTRAT_NON_ACCEPTE')
        self.assertEqual(lines[2]['reason'], 'CONTRACT_ID_INVALIDE')

    def test_duplicate_identity_comparison_ignores_json_key_order(self):
        one = {'b': 2, 'a': 1}
        two = {'a': 1, 'b': 2}
        self.assertEqual(events.json_canonique(one), events.json_canonique(two))

    def test_latest_state_excludes_positions_and_breaks_ties_by_ids_descending(self):
        values = [
            {'contract_id': 20, 'event_type': 'incident', 'observed_at': '2026-11-01T10:00:00Z',
             'device_id': 'dev-a', 'event_id': 'evt-z'},
            {'contract_id': 20, 'event_type': 'return', 'observed_at': '2026-11-01T10:00:00Z',
             'device_id': 'dev-b', 'event_id': 'evt-a'},
            {'contract_id': 20, 'event_type': 'position', 'observed_at': '2026-11-01T10:00:01Z',
             'device_id': 'dev-z', 'event_id': 'evt-z'},
        ]
        result = events.derniere_activite(values)
        self.assertEqual(result[20]['event_type'], 'return')
        self.assertEqual(redis_store.cle_montant(date(2026, 11, 1)),
                         'campusequip:axe34:montant:2026-11-01')


class EventBatchTests(unittest.TestCase):
    def _create_batch(self, parent: Path, tamper: bool = False) -> Path:
        campaign_id = 'campaign-test'
        contracts_sha = 'a' * 64
        (parent / 'campagne.json').write_text(json.dumps({
            'campaign_id': campaign_id, 'contrats_sha256': contracts_sha,
        }), encoding='utf-8')
        dossier = parent / 'lot-000001'
        dossier.mkdir()
        line = json.dumps({
            'device_id': 'gps-1', 'event_id': 'evt-1', 'contract_id': 2001,
            'event_type': 'return', 'observed_at': '2026-11-01T10:00:00Z', 'payload': {},
        }, sort_keys=True) + '\n'
        (dossier / 'evenements.jsonl').write_text(line, encoding='utf-8')
        digest = hashlib.sha256((dossier / 'evenements.jsonl').read_bytes()).hexdigest()
        (dossier / 'manifest.json').write_text(json.dumps({
            'schema_version': 'campusequip-events-1',
            'campaign_id': campaign_id,
            'batch_no': 1,
            'profile': 'propre',
            'rows': 1,
            'files': {'evenements.jsonl': '0' * 64 if tamper else digest},
            'contracts_sha256': contracts_sha,
        }), encoding='utf-8')
        (dossier / 'READY').write_text('', encoding='utf-8')
        return dossier

    def test_published_lot_hash_and_manifest_are_verified_before_processing(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = self._create_batch(Path(temporaire))
            manifeste, sha, lignes = events.lire_lot(dossier)
            self.assertEqual(manifeste['batch_no'], 1)
            self.assertEqual(len(sha), 64)
            self.assertEqual(len(lignes), 1)

    def test_wrong_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = self._create_batch(Path(temporaire), tamper=True)
            with self.assertRaisesRegex(events.LotEvenementsInvalide, 'empreinte'):
                events.lire_lot(dossier)

    def test_unhashable_profile_is_reported_as_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = self._create_batch(Path(temporaire))
            manifeste_path = dossier / 'manifest.json'
            manifeste = json.loads(manifeste_path.read_text(encoding='utf-8'))
            manifeste['profile'] = []
            manifeste_path.write_text(json.dumps(manifeste), encoding='utf-8')
            with self.assertRaisesRegex(events.LotEvenementsInvalide, 'profile'):
                events.lire_lot(dossier)

    def test_malformed_json_line_is_retained_as_individual_rejection(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = self._create_batch(Path(temporaire))
            source = dossier / 'evenements.jsonl'
            source.write_text('{broken json}\n', encoding='utf-8')
            manifeste_path = dossier / 'manifest.json'
            manifeste = json.loads(manifeste_path.read_text(encoding='utf-8'))
            manifeste['files']['evenements.jsonl'] = hashlib.sha256(
                source.read_bytes()).hexdigest()
            manifeste_path.write_text(json.dumps(manifeste), encoding='utf-8')
            _, _, lignes = events.lire_lot(dossier)
            rejet = events.convertir_lignes(lignes, {2001})[0]
            self.assertEqual(rejet['reason'], 'JSON_INVALIDE')
            self.assertEqual(rejet['line'], 1)

    def test_pending_folder_cannot_be_consumed(self):
        with tempfile.TemporaryDirectory() as temporaire:
            parent = Path(temporaire)
            dossier = self._create_batch(parent)
            pending = parent / '.pending-copy'
            dossier.rename(pending)
            with self.assertRaisesRegex(events.LotEvenementsInvalide, 'READY'):
                events.lire_lot(pending)

    def test_interactive_return_publishes_a_valid_pipeline_batch(self):
        with tempfile.TemporaryDirectory() as temporaire:
            root = Path(temporaire)

            def exporter(chemin):
                chemin.parent.mkdir(parents=True, exist_ok=True)
                chemin.write_text('contract_id\n2001\n', encoding='utf-8')
                return {'sha256': events.empreinte(chemin)}

            def traiter(dossier):
                manifeste, _, lignes = events.lire_lot(dossier)
                self.assertEqual(manifeste['profile'], 'propre')
                self.assertEqual(len(lignes), 1)
                evenement = lignes[0][1]
                self.assertEqual(evenement['contract_id'], 2001)
                self.assertEqual(evenement['event_type'], 'return')
                self.assertEqual(evenement['observed_at'], '2026-11-16T01:00:00Z')
                return {'inserted': 1, 'status': 'events_written'}

            with (
                patch.dict('os.environ', {'CAMPUSEQUIP_UI_EVENTS_DIR': temporaire}),
                patch('axes_3_4.pipeline.exporter_contrats', side_effect=exporter),
                patch('axes_3_4.pipeline.mongodb.traiter_lot', side_effect=traiter),
                patch('axes_3_4.pipeline.redis_store.reconstruire_incidents',
                      return_value={'incidents': 0}),
            ):
                resultat = pipeline.enregistrer_retour_interactif(
                    2001, 'return-ui-1', 'Good', 'Demo', '2026-11-16T01:00:00Z',
                )

            self.assertEqual(resultat['ingestion']['inserted'], 1)
            self.assertEqual(resultat['incident_projection']['status'], 'connected')
            self.assertTrue(Path(resultat['source_path'], 'READY').is_file())


if __name__ == '__main__':
    unittest.main()
