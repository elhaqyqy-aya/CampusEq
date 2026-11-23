"""Fabrique de petits lots de test, écrits à la main et explicables ligne à ligne.

Chaque lot produit contient exactement les quatre fichiers d'un lot réel
(`locations.csv`, `referentiels.json`, `manifest.json`, `READY`) et des
empreintes SHA-256 correctes : le pipeline les traite comme un vrai lot.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

COLONNES = ['contract_id', 'client_id', 'site_id', 'start_date', 'status',
            'line_no', 'equipment_id', 'quantity', 'unit', 'duration', 'unit_rate']

CAMPAGNE = 'campagne-test-0001'

# Deux campus, quatre guichets, dix clients, quatre catégories, quatre équipements.
# Les catégories sont volontairement hiérarchiques : 3 et 4 sont filles de 1.
REFERENTIELS = {
    'schema_version': 'campusequip-v2',
    'campuses': [
        {'campus_id': 1, 'name': 'Campus Atlas'},
        {'campus_id': 2, 'name': 'Campus Océan'},
    ],
    'sites': [
        {'site_id': 1, 'campus_id': 1, 'name': 'Campus Atlas / guichet 1'},
        {'site_id': 2, 'campus_id': 1, 'name': 'Campus Atlas / guichet 2'},
        {'site_id': 3, 'campus_id': 2, 'name': 'Campus Océan / guichet 1'},
        {'site_id': 4, 'campus_id': 2, 'name': 'Campus Océan / guichet 2'},
    ],
    'clients': [{'client_id': identifiant, 'name': f'Association {identifiant:02d}'}
                for identifiant in range(1, 11)],
    'categories': [
        {'category_id': 1, 'name': 'Audiovisuel', 'parent_id': None},
        {'category_id': 2, 'name': 'Mobilier', 'parent_id': None},
        {'category_id': 3, 'name': 'Image', 'parent_id': 1},
        {'category_id': 4, 'name': 'Son', 'parent_id': 1},
    ],
    'equipment': [
        {'equipment_id': 1, 'name': 'Vidéoprojecteur', 'category_id': 3},
        {'equipment_id': 2, 'name': 'Enceinte', 'category_id': 4},
        {'equipment_id': 3, 'name': 'Table pliante', 'category_id': 2},
        {'equipment_id': 4, 'name': 'Écran de projection', 'category_id': 3},
    ],
}


def ligne(**champs) -> dict:
    """Une ligne valide par défaut ; chaque test ne surcharge que son cas."""
    valeurs = {
        'contract_id': 1,
        'client_id': 1,
        'site_id': 1,
        'start_date': '2026-11-02',
        'status': 'paid',
        'line_no': 1,
        'equipment_id': 1,
        'quantity': 1,
        'unit': 'hour',
        'duration': 2,
        'unit_rate': '10.00',
    }
    inconnues = set(champs) - set(COLONNES)
    if inconnues:
        raise KeyError(f'colonne inconnue : {sorted(inconnues)}')
    valeurs.update(champs)
    return valeurs


def _ecrire_csv(chemin: Path, entetes: list[str], lignes: list) -> None:
    with chemin.open('w', newline='', encoding='utf-8') as flux:
        ecrivain = csv.writer(flux)
        ecrivain.writerow(entetes)
        for contenu in lignes:
            if isinstance(contenu, dict):
                ecrivain.writerow([contenu.get(colonne, '') for colonne in entetes])
            else:
                ecrivain.writerow(list(contenu))


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def ecrire_lot(dossier, lignes: list, *, campagne: str = CAMPAGNE, lot: int = 1,
               entetes: list[str] | None = None,
               referentiels: dict | None = None,
               profil: str = 'propre',
               manifeste: dict | None = None,
               ready: bool = True,
               schema_version: str = 'campusequip-v2') -> tuple[Path, dict]:
    """Écrit un lot complet et renvoie (dossier, manifeste lisible)."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    entetes = list(entetes or COLONNES)
    _ecrire_csv(dossier / 'locations.csv', entetes, lignes)
    (dossier / 'referentiels.json').write_text(
        json.dumps(referentiels or REFERENTIELS, ensure_ascii=False, indent=2),
        encoding='utf-8')

    contenu = {
        'schema_version': schema_version,
        'campaign_id': campagne,
        'batch_number': lot,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'contracts_requested': len({ligne['contract_id'] for ligne in lignes
                                    if isinstance(ligne, dict)}),
        'rows': len(lignes),
        'profile': profil,
        'files': {
            'locations.csv': _sha256(dossier / 'locations.csv'),
            'referentiels.json': _sha256(dossier / 'referentiels.json'),
        },
    }
    if manifeste:
        contenu.update(manifeste)
    (dossier / 'manifest.json').write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2), encoding='utf-8')
    if ready:
        (dossier / 'READY').write_text('campusequip-v2\n', encoding='utf-8')
    return dossier, contenu


def lire_manifeste(dossier) -> dict:
    return json.loads((Path(dossier) / 'manifest.json').read_text(encoding='utf-8'))
