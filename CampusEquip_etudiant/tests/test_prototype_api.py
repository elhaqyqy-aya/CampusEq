from __future__ import annotations

import unittest
from contextlib import nullcontext
from unittest.mock import patch

from dashboard.app import app


class PrototypeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch('dashboard.app.curseur', return_value=nullcontext(object()))
    @patch('dashboard.prototype.lire_instantane')
    def test_snapshot_is_a_read_only_get(self, lire_instantane, _curseur):
        lire_instantane.return_value = {
            'summary': {'campuses': 2, 'equipment_types': 8, 'contracts': 10,
                        'accepted_contracts': 7},
            'services': {'postgresql': {'status': 'connected'}},
        }

        response = self.client.get('/api/prototype/snapshot')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['ok'])
        self.assertEqual(response.json['summary']['contracts'], 10)
        lire_instantane.assert_called_once()

    def test_snapshot_does_not_accept_writes(self):
        response = self.client.post('/api/prototype/snapshot', json={'status': 'paid'})

        self.assertEqual(response.status_code, 405)

    @patch('axes_3_4.pipeline.enregistrer_retour_interactif')
    def test_return_event_is_submitted_to_the_pipeline(self, enregistrer):
        enregistrer.return_value = {
            'event_id': 'return-1',
            'contract_id': 12,
            'ingestion': {'inserted': 1, 'rejected': 0, 'batch_no': 1,
                          'status': 'events_written'},
            'incident_projection': {'status': 'connected'},
            'source_path': '/tmp/campaign/lot-000001',
        }

        response = self.client.post(
            '/api/prototype/events',
            json={
                'contract_id': 12,
                'event_id': 'return-1',
                'observed_at': '2026-11-16T01:00:00Z',
                'condition': 'Good',
                'notes': 'Demo return',
            },
            headers={'Origin': 'http://localhost'},
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json['ok'])
        self.assertEqual(response.json['ingestion']['inserted'], 1)
        enregistrer.assert_called_once_with(
            12, 'return-1', 'Good', 'Demo return', '2026-11-16T01:00:00Z',
        )

    def test_return_event_rejects_invalid_contract_ids(self):
        response = self.client.post(
            '/api/prototype/events',
            json={
                'contract_id': True,
                'event_id': 'return-1',
                'condition': 'Good',
            },
            headers={'Origin': 'http://localhost'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json['ok'])

    def test_return_event_rejects_cross_origin_requests(self):
        response = self.client.post(
            '/api/prototype/events',
            json={
                'contract_id': 12,
                'event_id': 'return-1',
                'condition': 'Good',
            },
            headers={'Origin': 'http://attacker.example'},
        )

        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
