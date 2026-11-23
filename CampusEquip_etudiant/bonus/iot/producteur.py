"""Bonus IoT — producteur GPS simulé (aucune position personnelle réelle).

Écrit des lots d'observations dans un dossier de flux, au format JSONL :

    iot_000001/observations.jsonl
    iot_000001/READY

Chaque observation :
    {"device_id": "gps-01", "event_id": "evt-000012", "equipment_id": 7,
     "observed_at": "2026-11-04T09:15:00+00:00", "latitude": 33.5731,
     "longitude": -7.5898}

`--panne` simule un incident du boîtier :
    tronque        une ligne JSON est coupée : le lot doit être refusé en bloc ;
    contradictoire deux observations de même clé avec des coordonnées différentes ;
    absent         le marqueur READY n'est pas écrit : le lot n'est pas complet.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Villes des campus du kit : positions approximatives, équipements fictifs.
LIEUX = [(33.5731, -7.5898), (34.0209, -6.8416), (34.0331, -5.0003),
         (31.6295, -7.9811), (35.7595, -5.8340), (30.4278, -9.5981)]


def observation(rng: random.Random, numero: int, equipements: int) -> dict:
    latitude, longitude = rng.choice(LIEUX)
    return {
        'device_id': f'gps-{rng.randint(1, 3):02d}',
        'event_id': f'evt-{numero:06d}',
        'equipment_id': rng.randint(1, equipements),
        'observed_at': (datetime(2026, 11, 4, tzinfo=timezone.utc)
                        + timedelta(minutes=numero * 3)).isoformat(),
        'latitude': round(latitude + rng.uniform(-0.004, 0.004), 6),
        'longitude': round(longitude + rng.uniform(-0.004, 0.004), 6),
    }


def ecrire_lot(sortie: Path, numero: int, nombre: int, graine: int, equipements: int,
               panne: str | None = None) -> Path:
    rng = random.Random(f'{graine}:{numero}')
    en_cours = sortie / f'.iot_{numero:06d}.en_cours'
    en_cours.mkdir(parents=True, exist_ok=True)
    observations = [observation(rng, numero * 1000 + index, equipements)
                    for index in range(nombre)]
    if panne == 'contradictoire' and observations:
        copie = dict(observations[0])
        copie['latitude'] = round(copie['latitude'] + 0.5, 6)
        observations.append(copie)
    lignes = [json.dumps(item, ensure_ascii=False) for item in observations]
    if panne == 'tronque' and lignes:
        lignes[-1] = lignes[-1][: len(lignes[-1]) // 2]     # JSON incomplet
    (en_cours / 'observations.jsonl').write_text('\n'.join(lignes) + '\n', encoding='utf-8')
    if panne != 'absent':
        (en_cours / 'READY').write_text('iot-v1\n', encoding='utf-8')
    final = sortie / f'iot_{numero:06d}'
    en_cours.rename(final)
    return final


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sortie', type=Path, default=Path('flux_iot'))
    p.add_argument('--observations', type=int, default=200)
    p.add_argument('--lots', type=int, default=2)
    p.add_argument('--intervalle', type=float, default=1)
    p.add_argument('--graine', type=int, default=5)
    p.add_argument('--equipements', type=int, default=120)
    p.add_argument('--panne', choices=['tronque', 'contradictoire', 'absent'])
    a = p.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    for numero in range(1, a.lots + 1):
        dossier = ecrire_lot(a.sortie, numero, a.observations, a.graine, a.equipements, a.panne)
        print(f'{dossier}: {a.observations} observation(s) publiée(s)'
              + (f' (panne simulée : {a.panne})' if a.panne else ''), flush=True)
        if numero < a.lots and a.intervalle:
            time.sleep(a.intervalle)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
