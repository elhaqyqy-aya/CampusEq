"""Persistance et moteur de télémétrie pour la flotte GPS de démonstration."""
from __future__ import annotations

import math
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

from etudiant import config

_SCHEMA_PATH = Path(__file__).with_name('gps_simulator_schema.sql')
_schema_lock = threading.Lock()
_schema_ready = False
_EARTH_RADIUS_M = 6_371_000
_MAX_STEP_SECONDS = 3.0
_HISTORY_LIMIT = 100

# Polylignes de rues marocaines approximées sur des coordonnées réelles.
# L'interpolation suit leur longueur géodésique, sans téléportation aléatoire.
ROUTES = {
    'maarif': [
        (33.58952, -7.62074), (33.58969, -7.62205), (33.58991, -7.62450),
        (33.59017, -7.62718), (33.59044, -7.62984), (33.59072, -7.63255),
        (33.59099, -7.63525), (33.59133, -7.63800), (33.59210, -7.64000),
        (33.59400, -7.63880), (33.59550, -7.63550), (33.59500, -7.63100),
        (33.59350, -7.62600), (33.59130, -7.62200), (33.58952, -7.62074),
    ],
    'rabat-centre': [
        (34.02010, -6.83660), (34.02070, -6.83430), (34.02130, -6.83180),
        (34.02210, -6.82920), (34.02340, -6.82740), (34.02500, -6.82820),
        (34.02600, -6.83040), (34.02520, -6.83300), (34.02370, -6.83520),
        (34.02200, -6.83650), (34.02010, -6.83660),
    ],
    'marrakech-medina': [
        (31.62810, -7.99320), (31.62710, -7.99110), (31.62610, -7.98890),
        (31.62450, -7.98760), (31.62250, -7.98820), (31.62130, -7.99010),
        (31.62240, -7.99240), (31.62440, -7.99420), (31.62630, -7.99400),
        (31.62810, -7.99320),
    ],
    'casablanca-corniche': [
        (33.60410, -7.64910), (33.60540, -7.64650), (33.60670, -7.64380),
        (33.60810, -7.64100), (33.60910, -7.63810), (33.60800, -7.63560),
        (33.60620, -7.63710), (33.60470, -7.64000), (33.60340, -7.64320),
        (33.60410, -7.64910),
    ],
}

DEVICES = (
    {
        'device_id': 'GPS-001', 'name': 'Utilitaire Maarif', 'route_key': 'maarif',
        'base_speed_kmh': 28.0, 'battery_pct': 87, 'signal_strength': 4,
        'status': 'online', 'altitude_m': 56.0,
    },
    {
        'device_id': 'GPS-002', 'name': 'Navette Rabat', 'route_key': 'rabat-centre',
        'base_speed_kmh': 34.0, 'battery_pct': 64, 'signal_strength': 3,
        'status': 'online', 'altitude_m': 76.0,
    },
    {
        'device_id': 'GPS-003', 'name': 'Fourgon Médina', 'route_key': 'marrakech-medina',
        'base_speed_kmh': 19.0, 'battery_pct': 23, 'signal_strength': 2,
        'status': 'weak', 'altitude_m': 465.0,
    },
    {
        'device_id': 'GPS-004', 'name': 'Intervention Corniche', 'route_key': 'casablanca-corniche',
        'base_speed_kmh': 42.0, 'battery_pct': 92, 'signal_strength': 4,
        'status': 'online', 'altitude_m': 18.0,
    },
    {
        'device_id': 'GPS-005', 'name': 'Véhicule de réserve', 'route_key': 'rabat-centre',
        'base_speed_kmh': 0.0, 'battery_pct': 41, 'signal_strength': 0,
        'status': 'offline', 'altitude_m': 77.0,
    },
)
_DEVICE_BY_ID = {device['device_id']: device for device in DEVICES}

DEFAULT_GEOFENCES = (
    {
        'slug': 'maarif-central', 'name': 'Périmètre Maarif',
        'latitude': 33.58970, 'longitude': -7.62265, 'radius_m': 85,
    },
    {
        'slug': 'rabat-agdal', 'name': 'Zone Agdal · Rabat',
        'latitude': 34.02300, 'longitude': -6.83090, 'radius_m': 180,
    },
)


class GpsInputError(ValueError):
    """Entrée invalide envoyée à l'API du simulateur GPS."""


def _connect():
    return psycopg2.connect(**config.parametres_connexion())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, haversine)))


def _bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    delta_lon = lon2 - lon1
    y = math.sin(delta_lon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    return math.degrees(math.atan2(y, x)) % 360


def _route_length(route: list[tuple[float, float]]) -> float:
    return sum(_distance_m(a, b) for a, b in zip(route, route[1:]))


def _route_position(route: list[tuple[float, float]], progress_m: float) -> tuple[float, float, float]:
    lengths = [_distance_m(a, b) for a, b in zip(route, route[1:])]
    total = sum(lengths)
    remaining = progress_m % total
    for index, length in enumerate(lengths):
        if remaining <= length or index == len(lengths) - 1:
            fraction = min(1.0, remaining / length) if length else 0.0
            start = route[index]
            finish = route[index + 1]
            latitude = start[0] + (finish[0] - start[0]) * fraction
            longitude = start[1] + (finish[1] - start[1]) * fraction
            return latitude, longitude, _bearing_deg(start, finish)
        remaining -= length
    return route[0][0], route[0][1], _bearing_deg(route[0], route[1])


def _ensure_schema(connection) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        with connection.cursor() as cur:
            cur.execute(_SCHEMA_PATH.read_text(encoding='utf-8'))
            _seed(cur)
        connection.commit()
        _schema_ready = True


def _seed(cur) -> None:
    cur.execute("""
        INSERT INTO gps_sim.simulation_state (singleton, status, speed_multiplier)
        VALUES (true, 'paused', 1)
        ON CONFLICT (singleton) DO NOTHING
    """)
    for device in DEVICES:
        route = ROUTES[device['route_key']]
        latitude, longitude, heading = _route_position(route, 0)
        cur.execute("""
            INSERT INTO gps_sim.devices (
                device_id, name, route_key, progress_m, base_speed_kmh,
                initial_battery, battery_pct, signal_strength, status,
                latitude, longitude, speed_kmh, heading_deg, altitude_m, last_update_at
            ) VALUES (
                %(device_id)s, %(name)s, %(route_key)s, 0, %(base_speed_kmh)s,
                %(battery_pct)s, %(battery_pct)s, %(signal_strength)s, %(status)s,
                %(latitude)s, %(longitude)s, 0, %(heading)s, %(altitude_m)s, now()
            )
            ON CONFLICT (device_id) DO NOTHING
            RETURNING device_id
        """, {**device, 'latitude': latitude, 'longitude': longitude, 'heading': heading})
        if cur.fetchone():
            _insert_telemetry(cur, device['device_id'], {
                **device, 'latitude': latitude, 'longitude': longitude,
                'speed_kmh': 0.0, 'heading_deg': heading,
            })
    for fence in DEFAULT_GEOFENCES:
        cur.execute("""
            INSERT INTO gps_sim.geofences (slug, name, center_latitude, center_longitude, radius_m)
            VALUES (%(slug)s, %(name)s, %(latitude)s, %(longitude)s, %(radius_m)s)
            ON CONFLICT (slug) DO NOTHING
        """, fence)


def _insert_telemetry(cur, device_id: str, values: dict, recorded_at: datetime | None = None) -> None:
    cur.execute("""
        INSERT INTO gps_sim.telemetry (
            device_id, latitude, longitude, speed_kmh, heading_deg, altitude_m,
            battery_pct, signal_strength, status, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
    """, (
        device_id, values['latitude'], values['longitude'], values['speed_kmh'],
        values['heading_deg'], values['altitude_m'], values['battery_pct'],
        values['signal_strength'], values['status'], recorded_at,
    ))


def _snapshot(cur) -> dict:
    cur.execute("""
        SELECT device_id, name, route_key, progress_m, base_speed_kmh, battery_pct,
               signal_strength, status, latitude, longitude, speed_kmh, heading_deg,
               altitude_m, last_update_at
        FROM gps_sim.devices
        ORDER BY device_id
    """)
    devices = [dict(row) for row in cur.fetchall()]
    for device in devices:
        device['last_update_at'] = device['last_update_at'].isoformat()
        device['route'] = ROUTES[device['route_key']]

    cur.execute("""
        SELECT device_id, latitude, longitude, speed_kmh, heading_deg, altitude_m,
               battery_pct, signal_strength, status, recorded_at
        FROM (
            SELECT t.*,
                   row_number() OVER (PARTITION BY device_id ORDER BY recorded_at DESC, id DESC) AS position
            FROM gps_sim.telemetry t
        ) recent
        WHERE position <= %s
        ORDER BY device_id, recorded_at
    """, (_HISTORY_LIMIT,))
    history = {}
    for row in cur.fetchall():
        point = dict(row)
        point['recorded_at'] = point['recorded_at'].isoformat()
        history.setdefault(point['device_id'], []).append(point)

    cur.execute("""
        SELECT id, slug, name, center_latitude, center_longitude, radius_m, enabled, created_at
        FROM gps_sim.geofences
        WHERE enabled
        ORDER BY id
    """)
    geofences = [dict(row) for row in cur.fetchall()]
    for fence in geofences:
        fence['created_at'] = fence['created_at'].isoformat()

    cur.execute("""
        SELECT id, geofence_id, geofence_name, device_id, event_type, latitude,
               longitude, occurred_at
        FROM gps_sim.geofence_events
        ORDER BY occurred_at DESC, id DESC
        LIMIT 30
    """)
    events = [dict(row) for row in cur.fetchall()]
    for event in events:
        event['occurred_at'] = event['occurred_at'].isoformat()

    cur.execute("""
        SELECT status, speed_multiplier, last_tick_at, updated_at
        FROM gps_sim.simulation_state
        WHERE singleton = true
    """)
    simulation = dict(cur.fetchone())
    simulation['last_tick_at'] = simulation['last_tick_at'].isoformat() if simulation['last_tick_at'] else None
    simulation['updated_at'] = simulation['updated_at'].isoformat()
    return {
        'devices': devices,
        'history': history,
        'geofences': geofences,
        'events': events,
        'simulation': simulation,
    }


def _run(operation):
    connection = _connect()
    try:
        _ensure_schema(connection)
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cur:
                return operation(cur)
    finally:
        connection.close()


def snapshot() -> dict:
    return _run(_snapshot)


def _store_geofence_transition(cur, device: dict, fence: dict, previous_inside: bool, current_inside: bool) -> None:
    if previous_inside == current_inside:
        return
    event_type = 'enter' if current_inside else 'exit'
    cur.execute("""
        INSERT INTO gps_sim.geofence_events (
            geofence_id, geofence_name, device_id, event_type, latitude, longitude
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        fence['id'], fence['name'], device['device_id'], event_type,
        device['latitude'], device['longitude'],
    ))


def _route_geofence_transitions(
    route: list[tuple[float, float]],
    start_progress: float,
    end_progress: float,
    center: tuple[float, float],
    radius_m: float,
) -> list[tuple[str, float, float]]:
    start_point = _route_position(route, start_progress)[:2]
    inside = _distance_m(start_point, center) <= radius_m
    transitions = []
    distance = end_progress - start_progress
    samples = max(1, math.ceil(distance / 25))
    previous_progress = start_progress
    for sample_index in range(1, samples + 1):
        sample_progress = start_progress + distance * sample_index / samples
        point = _route_position(route, sample_progress)[:2]
        sample_inside = _distance_m(point, center) <= radius_m
        if sample_inside != inside:
            low, high = previous_progress, sample_progress
            for _ in range(14):
                middle = (low + high) / 2
                middle_point = _route_position(route, middle)[:2]
                middle_inside = _distance_m(middle_point, center) <= radius_m
                if middle_inside == inside:
                    low = middle
                else:
                    high = middle
            latitude, longitude, _ = _route_position(route, high)
            transitions.append(('enter' if sample_inside else 'exit', latitude, longitude))
            inside = sample_inside
        previous_progress = sample_progress
    return transitions


def step() -> dict:
    def operation(cur):
        cur.execute("""
            SELECT status, speed_multiplier, last_tick_at, last_cleanup_at
            FROM gps_sim.simulation_state
            WHERE singleton = true
            FOR UPDATE
        """)
        simulation = cur.fetchone()
        now = _now()
        if simulation['status'] != 'running':
            return _snapshot(cur)

        elapsed = (now - simulation['last_tick_at']).total_seconds() if simulation['last_tick_at'] else 0
        elapsed = min(_MAX_STEP_SECONDS, max(0.0, elapsed))
        simulation_seconds = elapsed * float(simulation['speed_multiplier'])
        cur.execute("""
            SELECT id, name, center_latitude, center_longitude, radius_m
            FROM gps_sim.geofences
            WHERE enabled
        """)
        fences = cur.fetchall()
        cur.execute("SELECT * FROM gps_sim.devices ORDER BY device_id")
        devices = cur.fetchall()
        for device in devices:
            if device['status'] == 'offline':
                continue
            previous = (device['latitude'], device['longitude'])
            route = ROUTES[device['route_key']]
            progress = float(device['progress_m']) + float(device['base_speed_kmh']) * simulation_seconds / 3.6
            latitude, longitude, heading = _route_position(route, progress)
            distance_along_route = progress % _route_length(route)
            altitude = _DEVICE_BY_ID[device['device_id']]['altitude_m'] + 0.5 * math.sin(distance_along_route / 350)
            battery = max(0.0, float(device['battery_pct']) - simulation_seconds * .002)
            current = {
                **dict(device),
                'progress_m': progress,
                'latitude': latitude,
                'longitude': longitude,
                'speed_kmh': float(device['base_speed_kmh']),
                'heading_deg': heading,
                'altitude_m': altitude,
                'battery_pct': battery,
            }
            telemetry_due = (now - device['last_telemetry_at']).total_seconds() >= 5
            cur.execute("""
                UPDATE gps_sim.devices
                SET progress_m = %s, latitude = %s, longitude = %s, speed_kmh = %s,
                    heading_deg = %s, altitude_m = %s, battery_pct = %s, last_update_at = %s,
                    last_telemetry_at = CASE WHEN %s THEN %s ELSE last_telemetry_at END
                WHERE device_id = %s
            """, (
                progress, latitude, longitude, current['speed_kmh'], heading,
                altitude, battery, now, telemetry_due, now, device['device_id'],
            ))
            for fence in fences:
                center = (fence['center_latitude'], fence['center_longitude'])
                previous_inside = _distance_m(previous, center) <= fence['radius_m']
                for event_type, event_latitude, event_longitude in _route_geofence_transitions(
                    route, float(device['progress_m']), progress, center, fence['radius_m'],
                ):
                    event_device = {**current, 'latitude': event_latitude, 'longitude': event_longitude}
                    _store_geofence_transition(
                        cur, event_device, fence,
                        previous_inside, event_type == 'enter',
                    )
                    previous_inside = event_type == 'enter'
            if telemetry_due:
                _insert_telemetry(cur, device['device_id'], current, now)

        cur.execute("""
            UPDATE gps_sim.simulation_state
            SET last_tick_at = %s, updated_at = %s
            WHERE singleton = true
        """, (now, now))
        if (now - simulation['last_cleanup_at']).total_seconds() >= 3600:
            cur.execute(
                "DELETE FROM gps_sim.telemetry WHERE recorded_at < %s - interval '30 days'",
                (now,),
            )
            cur.execute("""
                UPDATE gps_sim.simulation_state
                SET last_cleanup_at = %s
                WHERE singleton = true
            """, (now,))
        return _snapshot(cur)

    return _run(operation)


def control(action: str, speed_multiplier: float | None = None) -> dict:
    if not isinstance(action, str) or action not in {'start', 'pause', 'resume', 'reset', 'speed'}:
        raise GpsInputError('Commande de simulation inconnue.')
    if action == 'speed':
        if (isinstance(speed_multiplier, bool) or not isinstance(speed_multiplier, (int, float))
                or speed_multiplier not in {.5, 1, 2, 4, 8}):
            raise GpsInputError('La vitesse doit être 0,5×, 1×, 2×, 4× ou 8×.')

    def operation(cur):
        now = _now()
        if action in {'start', 'resume'}:
            cur.execute("""
                UPDATE gps_sim.simulation_state
                SET status = 'running', last_tick_at = %s, updated_at = %s
                WHERE singleton = true
            """, (now, now))
        elif action == 'pause':
            cur.execute("""
                UPDATE gps_sim.simulation_state
                SET status = 'paused', last_tick_at = NULL, updated_at = %s
                WHERE singleton = true
            """, (now,))
        elif action == 'speed':
            cur.execute("""
                UPDATE gps_sim.simulation_state
                SET speed_multiplier = %s, last_tick_at = CASE WHEN status = 'running' THEN %s ELSE last_tick_at END,
                    updated_at = %s
                WHERE singleton = true
            """, (speed_multiplier, now, now))
        else:
            cur.execute("DELETE FROM gps_sim.telemetry")
            for device in DEVICES:
                route = ROUTES[device['route_key']]
                latitude, longitude, heading = _route_position(route, 0)
                cur.execute("""
                    UPDATE gps_sim.devices
                    SET progress_m = 0, latitude = %s, longitude = %s, speed_kmh = 0,
                        heading_deg = %s, altitude_m = %s, battery_pct = initial_battery,
                        signal_strength = %s, status = %s, last_update_at = %s,
                        last_telemetry_at = %s
                    WHERE device_id = %s
                """, (
                    latitude, longitude, heading, device['altitude_m'], device['signal_strength'],
                    device['status'], now, now, device['device_id'],
                ))
            cur.execute("""
                UPDATE gps_sim.simulation_state
                SET status = 'paused', speed_multiplier = 1, last_tick_at = NULL, updated_at = %s
                WHERE singleton = true
            """, (now,))
            cur.execute("""
                INSERT INTO gps_sim.telemetry (
                    device_id, latitude, longitude, speed_kmh, heading_deg, altitude_m,
                    battery_pct, signal_strength, status, recorded_at
                )
                SELECT device_id, latitude, longitude, speed_kmh, heading_deg, altitude_m,
                       battery_pct, signal_strength, status, %s
                FROM gps_sim.devices
            """, (now,))
        return _snapshot(cur)

    return _run(operation)


def add_geofence(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise GpsInputError('Le corps de la requête doit être un objet JSON.')
    name = payload.get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise GpsInputError('Le nom de la zone doit contenir entre 1 et 80 caractères.')
    try:
        latitude = float(payload['latitude'])
        longitude = float(payload['longitude'])
        raw_radius = payload['radius_m']
        radius = int(raw_radius)
    except (KeyError, TypeError, ValueError) as error:
        raise GpsInputError('Centre ou rayon de géofence invalide.') from error
    if isinstance(raw_radius, bool) or float(raw_radius) != radius:
        raise GpsInputError('Le rayon doit être un nombre entier de mètres.')
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise GpsInputError('La latitude doit être comprise entre −90° et 90°.')
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise GpsInputError('La longitude doit être comprise entre −180° et 180°.')
    if not 50 <= radius <= 10000:
        raise GpsInputError('Le rayon doit être compris entre 50 et 10 000 mètres.')
    slug = uuid.uuid4().hex

    def operation(cur):
        cur.execute("SELECT count(*) AS total FROM gps_sim.geofences WHERE enabled")
        if cur.fetchone()['total'] >= 25:
            raise GpsInputError('La limite de 25 géofences actives est atteinte.')
        cur.execute("""
            INSERT INTO gps_sim.geofences (slug, name, center_latitude, center_longitude, radius_m)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, slug, name, center_latitude, center_longitude, radius_m, enabled, created_at
        """, (slug, name.strip(), latitude, longitude, radius))
        fence = dict(cur.fetchone())
        fence['created_at'] = fence['created_at'].isoformat()
        return fence

    return _run(operation)


def delete_geofence(geofence_id: int) -> bool:
    def operation(cur):
        cur.execute("DELETE FROM gps_sim.geofences WHERE id = %s RETURNING id", (geofence_id,))
        return cur.fetchone() is not None
    return _run(operation)


def route_length_for(route_key: str) -> float:
    return _route_length(ROUTES[route_key])


def position_for(route_key: str, progress_m: float) -> tuple[float, float, float]:
    return _route_position(ROUTES[route_key], progress_m)


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    return _distance_m(a, b)
