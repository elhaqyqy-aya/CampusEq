from __future__ import annotations

import unittest
from contextlib import nullcontext
from datetime import date, datetime
from unittest.mock import patch

from dashboard import donnees
from dashboard.app import app


class IoTLabPageTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.filtres = donnees.Filtres(date(2025, 1, 1), date(2025, 12, 31), None)
        self.contexte = {
            'filtres': self.filtres,
            'liens': {},
            'campus_liste': [],
            'campus_courant': None,
            'sante': {'version': 'test', 'base': 'campusequip_test'},
            'aujourdhui': datetime(2025, 1, 1),
        }

    @patch('dashboard.app.contexte')
    @patch('dashboard.app.filtres_courants')
    @patch('dashboard.app.curseur', return_value=nullcontext(object()))
    def test_iot_lab_page_exposes_workbench_and_discloses_execution_model(
        self, _curseur, filtres_courants, contexte,
    ):
        filtres_courants.return_value = self.filtres
        contexte.return_value = self.contexte

        response = self.client.get('/iot-lab')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="iot-lab"', response.data)
        self.assertIn(b'id="iot-board"', response.data)
        self.assertIn(b'id="iot-code"', response.data)
        self.assertIn(b'ne compile pas le firmware', response.data)
        html = response.get_data(as_text=True)
        self.assertIn('href="/iot-lab"', html)
        self.assertIn('/static/iot_lab/app.js?v=iot-lab-v8', html)


if __name__ == '__main__':
    unittest.main()
