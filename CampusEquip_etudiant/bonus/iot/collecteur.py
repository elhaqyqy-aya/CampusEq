"""Bonus IoT — collecteur d'observations GPS simulées.

    python -m bonus.iot.collecteur --entree flux_iot --une-fois

Contrôles (avant toute écriture) :
  * équipement connu dans `equipments` ;
  * instant ISO 8601 avec fuseau, exprimé en UTC ;
  * latitude entre -90 et 90, longitude entre -180 et 180 ;
  * clé (device_id, event_id) : un rejeu identique n'ajoute rien, un contenu
    contradictoire est rejeté avec un motif.

Chaque fichier est chargé dans UNE transaction avec sa signature SHA-256 :
un fichier rejoué est reconnu par le journal `iot_lots`, pas par la mémoire du
programme. Un fichier illisible est refusé en bloc et reste un échec visible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402

RULES_VERSION = 'campusequip-iot-v1'
TABLE_SCHEMA = Path(__file__).with_name('schema_iot.sql')


def signature_fichier(chemin: Path) -> str:
    matiere = f'{RULES_VERSION}|{hashlib.sha256(Path(chemin).read_bytes()).hexdigest()}'
    return hashlib.sha256(matiere.encode('utf-8')).hexdigest()


def _instant(valeur) -> datetime:
    if not isinstance(valeur, str):
        raise ValueError('instant attendu en texte ISO 8601')
    texte = valeur.replace('Z', '+00:00')
    instant = datetime.fromisoformat(texte)
    if instant.tzinfo is None:
        raise ValueError('fuseau horaire absent (UTC attendu)')
    if instant.utcoffset() != timedelta(0):
        raise ValueError('instant non exprimé en UTC')
    return instant


def _decimal(valeur, libelle: str, minimum: float, maximum: float) -> Decimal:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, str)):
        raise ValueError(f'{libelle} doit être un nombre')
    nombre = Decimal(str(valeur))
    if not nombre.is_finite():
        raise ValueError(f'{libelle} non fini')
    if not Decimal(str(minimum)) <= nombre <= Decimal(str(maximum)):
        raise ValueError(f'{libelle} hors bornes [{minimum}, {maximum}]')
    return nombre


def controler(observation, equipements: set[int]) -> tuple[dict, list[str]]:
    """Contrôle une observation ; renvoie (valeurs typées, motifs)."""
    if not isinstance(observation, dict):
        return {}, ['OBSERVATION_MAL_FORMEE: objet JSON attendu']
    motifs: list[str] = []
    valeurs: dict = {}

    for cle in ('device_id', 'event_id', 'equipment_id', 'observed_at', 'latitude',
                'longitude'):
        if observation.get(cle) in (None, ''):
            motifs.append(f'CHAMP_ABSENT: {cle}')

    for cle in ('device_id', 'event_id'):
        valeur = observation.get(cle)
        if valeur not in (None, '') and not isinstance(valeur, str):
            motifs.append(f'{cle.upper()}_INVALIDE: texte attendu')

    equipment_id = observation.get('equipment_id')
    if equipment_id is not None:
        if isinstance(equipment_id, bool) or not isinstance(equipment_id, int) \
                or equipment_id <= 0:
            motifs.append('EQUIPMENT_ID_INVALIDE: entier positif attendu')
        elif equipment_id not in equipements:
            motifs.append(f'EQUIPEMENT_INCONNU: equipment_id {equipment_id} absent du référentiel')
        else:
            valeurs['equipment_id'] = equipment_id

    try:
        valeurs['observed_at'] = _instant(observation.get('observed_at'))
    except (ValueError, TypeError) as erreur:
        motifs.append(f'INSTANT_INVALIDE: {erreur}')

    for cle, minimum, maximum in (('latitude', -90, 90), ('longitude', -180, 180)):
        try:
            valeurs[cle] = _decimal(observation.get(cle), cle, minimum, maximum)
        except (ValueError, TypeError) as erreur:
            motifs.append(f'{cle.upper()}_INVALIDE: {erreur}')

    return valeurs, motifs


def _cle(observation) -> tuple[str, str]:
    return str(observation.get('device_id', '')), str(observation.get('event_id', ''))


def _meme_contenu(existant, valeurs: dict) -> bool:
    return (existant['equipment_id'] == valeurs['equipment_id']
            and existant['observed_at'] == valeurs['observed_at']
            and Decimal(existant['latitude']) == valeurs['latitude']
            and Decimal(existant['longitude']) == valeurs['longitude'])


def traiter_fichier(cnx, dossier: Path, fichier: Path) -> dict:
    """Charge un fichier d'observations dans une seule transaction."""
    signature = signature_fichier(fichier)
    resultat = {'fichier': dossier.name, 'signature': signature}

    with cnx.cursor() as cur:
        cur.execute('SELECT batch_id, inserees FROM iot_lots WHERE signature = %s', (signature,))
        deja = cur.fetchone()
    cnx.rollback()
    if deja:
        return {**resultat, 'statut': 'DEJA_CHARGE', 'inserees': 0,
                'batch_id': deja[0], 'rejeu_total_precedent': deja[1]}

    with cnx.cursor() as cur:
        cur.execute('SELECT equipment_id FROM equipments')
        equipements = {ligne[0] for ligne in cur.fetchall()}
    cnx.rollback()

    lignes = fichier.read_text(encoding='utf-8').splitlines()
    observations, rejets, motifs_fichier = [], [], None
    vues: dict[tuple, dict] = {}
    rejeu = 0

    for position, ligne in enumerate(lignes, start=1):
        if not ligne.strip():
            continue
        try:
            observation = json.loads(ligne)
        except json.JSONDecodeError as erreur:
            motifs_fichier = f'JSON_INVALIDE ligne {position} : {erreur.msg}'
            break
        valeurs, motifs = controler(observation, equipements)
        if motifs:
            rejets.append((position, _cle(observation), motifs, observation))
            continue
        cle = _cle(observation)
        if cle in vues:
            if _meme_contenu(vues[cle], valeurs):
                rejeu += 1
            else:
                rejets.append((position, cle,
                               ['CONFLIT_OBSERVATION: même clé, contenu différent'],
                               observation))
            continue
        vues[cle] = valeurs

    try:
        if motifs_fichier:
            raise ValueError(motifs_fichier)

        with cnx.cursor() as cur:
            cles = list(vues)
            existants = {}
            if cles:
                cur.execute(
                    """
                    SELECT device_id, event_id, equipment_id, observed_at, latitude, longitude
                    FROM iot_observations
                    WHERE (device_id, event_id) IN (
                        SELECT * FROM unnest(%s::text[], %s::text[])
                    )
                    """, ([cle[0] for cle in cles], [cle[1] for cle in cles]))
                for ligne in cur.fetchall():
                    existants[(ligne[0], ligne[1])] = {
                        'equipment_id': ligne[2], 'observed_at': ligne[3],
                        'latitude': ligne[4], 'longitude': ligne[5]}

            a_inserer = []
            for cle, valeurs in vues.items():
                if cle in existants:
                    if _meme_contenu(existants[cle], valeurs):
                        rejeu += 1
                        continue
                    rejets.append((0, cle,
                                   ['CONFLIT_OBSERVATION: observation déjà connue avec '
                                    'un contenu différent'], {'device_id': cle[0],
                                                              'event_id': cle[1]}))
                    continue
                a_inserer.append((cle[0], cle[1], valeurs['equipment_id'],
                                  valeurs['observed_at'], valeurs['latitude'],
                                  valeurs['longitude'], fichier.name))

            cur.execute(
                """
                INSERT INTO iot_lots (fichier, signature, statut, observations_recues,
                                      acceptees, rejetees, rejeu, inserees)
                VALUES (%s, %s, 'CHARGE', %s, %s, %s, %s, %s) RETURNING batch_id
                """,
                (fichier.name, signature, len(lignes), len(a_inserer), len(rejets), rejeu,
                 len(a_inserer)))
            batch_id = cur.fetchone()[0]

            if a_inserer:
                from psycopg2.extras import execute_values
                execute_values(
                    cur,
                    'INSERT INTO iot_observations (device_id, event_id, equipment_id, '
                    'observed_at, latitude, longitude, source_file) VALUES %s '
                    'ON CONFLICT (device_id, event_id) DO NOTHING', a_inserer)

            for position, cle, motifs, brut in rejets:
                cur.execute(
                    'INSERT INTO iot_rejets (batch_id, position, device_id, event_id, motifs, brut) '
                    'VALUES (%s, %s, %s, %s, %s, %s)',
                    (batch_id, position, cle[0], cle[1], motifs, json.dumps(brut, default=str)))
        cnx.commit()
        return {**resultat, 'statut': 'CHARGE', 'batch_id': batch_id,
                'observations_recues': len(lignes), 'inserees': len(a_inserer),
                'rejetees': len(rejets), 'rejeu': rejeu}
    except Exception as erreur:
        cnx.rollback()
        with cnx.cursor() as cur:
            cur.execute(
                """
                INSERT INTO iot_lots (fichier, signature, statut, observations_recues,
                                      acceptees, rejetees, rejeu, inserees, motif)
                VALUES (%s, %s, 'REJETE_STRUCTURE', %s, 0, %s, 0, 0, %s)
                """, (fichier.name, signature, len(lignes), len(rejets), str(erreur)))
        cnx.commit()
        return {**resultat, 'statut': 'REJETE_STRUCTURE', 'motif': str(erreur),
                'inserees': 0}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--entree', type=Path, default=Path('flux_iot'))
    p.add_argument('--une-fois', action='store_true')
    a = p.parse_args()

    cnx = depot.connexion()
    try:
        depot.executer_script(cnx, TABLE_SCHEMA)
        echec = False
        for dossier in sorted(a.entree.glob('iot_*')):
            fichier = dossier / 'observations.jsonl'
            if not dossier.is_dir() or not (dossier / 'READY').is_file() \
                    or not fichier.is_file():
                continue
            resultat = traiter_fichier(cnx, a.entree, fichier)
            print(dossier.name, json.dumps(resultat, ensure_ascii=False), flush=True)
            if resultat['statut'] == 'REJETE_STRUCTURE':
                echec = True
        return 1 if echec else 0
    finally:
        cnx.close()


if __name__ == '__main__':
    raise SystemExit(main())
