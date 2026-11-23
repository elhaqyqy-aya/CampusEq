from __future__ import annotations

import unittest
from contextlib import nullcontext
from datetime import date, datetime
from unittest.mock import patch

from dashboard import donnees, gps_simulator
from dashboard.app import app


class GpsSimulatorRouteTests(unittest.TestCase):
    def test_route_interpolation_moves_by_distance_and_wraps(self):
        route_key = 'maarif'
        route_length = gps_simulator.route_length_for(route_key)
        start = gps_simulator.position_for(route_key, 0)
        moved = gps_simulator.position_for(route_key, 100)
        wrapped = gps_simulator.position_for(route_key, route_length + 100)

        self.assertAlmostEqual(gps_simulator.distance_m(start[:2], moved[:2]), 100, delta=1)
        self.assertAlmostEqual(moved[0], wrapped[0], places=7)
        self.assertAlmostEqual(moved[1], wrapped[1], places=7)
        self.assertGreaterEqual(moved[2], 0)
        self.assertLess(moved[2], 360)

    def test_geofence_sweep_records_entry_and_exit_between_large_ticks(self):
        route = gps_simulator.ROUTES['maarif']
        center = gps_simulator.position_for('maarif', 100)[:2]

        transitions = gps_simulator._route_geofence_transitions(
            route, 0, 200, center, 60,
        )

        self.assertEqual([event[0] for event in transitions], ['enter', 'exit'])

    def test_seeded_fleet_uses_valid_geographic_routes(self):
        self.assertEqual(
            {device['device_id'] for device in gps_simulator.DEVICES},
            {f'GPS-{number:03d}' for number in range(1, 6)},
        )
        for route_key, route in gps_simulator.ROUTES.items():
            self.assertGreater(gps_simulator.route_length_for(route_key), 500)
            for latitude, longitude in route:
                self.assertGreaterEqual(latitude, -90)
                self.assertLessEqual(latitude, 90)
                self.assertGreaterEqual(longitude, -180)
                self.assertLessEqual(longitude, 180)

    def test_control_rejects_unknown_actions_and_unlisted_speeds(self):
        for action, speed in (([], None), ('speed', '2'), ('speed', 3), ('launch', None)):
            with self.subTest(action=action, speed=speed):
                with self.assertRaises(gps_simulator.GpsInputError):
                    gps_simulator.control(action, speed)

    def test_geofence_input_validation_happens_before_database_access(self):
        for payload in (
            None,
            {'name': 'Zone', 'latitude': float('nan'), 'longitude': 1, 'radius_m': 100},
            {'name': '', 'latitude': 1, 'longitude': 1, 'radius_m': 100},
            {'name': 'Zone', 'latitude': 1, 'longitude': 1, 'radius_m': 49},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(gps_simulator.GpsInputError):
                    gps_simulator.add_geofence(payload)


class GpsSimulatorApiTests(unittest.TestCase):
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
    def test_gps_page_has_fleet_dashboard_and_gps_navigation(
        self, _curseur, filtres_courants, contexte,
    ):
        filtres_courants.return_value = self.filtres
        contexte.return_value = self.contexte

        response = self.client.get('/gps')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="gps-dashboard"', response.data)
        self.assertIn(b'id="gps-map"', response.data)
        self.assertIn(b'id="gps-device-rows"', response.data)
        self.assertIn(b'href="/gps"', response.data)
        self.assertIn(b'/static/gps_simulator/app.js?v=gps-v2', response.data)

    @patch('dashboard.app.gps_simulator.snapshot', return_value={
        'devices': [], 'history': {}, 'geofences': [], 'events': [],
        'simulation': {'status': 'paused', 'speed_multiplier': 1},
    })
    def test_snapshot_api_returns_simulated_fleet_shape(self, snapshot):
        response = self.client.get('/api/gps/snapshot')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['ok'])
        self.assertIn('simulation', response.json)
        snapshot.assert_called_once_with()

    @patch('dashboard.app.gps_simulator.control')
    def test_control_api_rejects_invalid_json_and_cross_origin_requests(self, control):
        no_json = self.client.post('/api/gps/control', data='{}')
        cross_origin = self.client.post(
            '/api/gps/control', json={'action': 'start'},
            headers={'Origin': 'https://other.example'},
        )

        self.assertEqual(no_json.status_code, 415)
        self.assertEqual(cross_origin.status_code, 403)
        control.assert_not_called()

    @patch('dashboard.app.gps_simulator.add_geofence', side_effect=gps_simulator.GpsInputError('centre invalide'))
    def test_geofence_api_reports_validation_errors(self, _add_geofence):
        response = self.client.post('/api/gps/geofences', json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn('centre invalide', response.json['erreur'])


if __name__ == '__main__':
    unittest.main()
