"""Validation et persistance idempotente des événements terrain CampusEquip."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHAMPS_EVENEMENT = {
    'device_id', 'event_id', 'contract_id', 'event_type', 'observed_at', 'payload',
}
TYPES_EVENEMENT = {'withdrawal', 'return', 'incident', 'failure', 'position'}
IDENTIFIANT = re.compile(r'^[A-Za-z0-9_-]+$', re.ASCII)
HORODATAGE_UTC = re.compile(
    r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$',
    re.ASCII,
)


class LotEvenementsInvalide(ValueError):
    """Un lot ne respecte pas le contrat de publication du kit."""


class EvenementInvalide(ValueError):
    """Un événement individuel ne respecte pas son contrat."""


def _interdire_constante_json(valeur: str) -> None:
    raise ValueError(f'constante JSON non finie : {valeur}')


def empreinte(chemin: Path) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def lire_lot(dossier: Path) -> tuple[dict, str, list[tuple[int, Any]]]:
    """Vérifie tout le manifeste avant lecture ligne par ligne de la source."""
    dossier = Path(dossier)
    if dossier.name.startswith('.pending-') or not (dossier / 'READY').is_file():
        raise LotEvenementsInvalide('seul un lot publié portant READY peut être consommé')
    if not dossier.is_dir():
        raise LotEvenementsInvalide(f'dossier de lot absent : {dossier}')
    for nom in ('manifest.json', 'evenements.jsonl'):
        if not (dossier / nom).is_file():
            raise LotEvenementsInvalide(f'fichier obligatoire absent : {nom}')
    try:
        manifeste = json.loads((dossier / 'manifest.json').read_text(encoding='utf-8'))
        campagne = json.loads((dossier.parent / 'campagne.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise LotEvenementsInvalide(f'manifeste ou campagne illisible : {erreur}') from None
    if not isinstance(manifeste, dict) or not isinstance(campagne, dict):
        raise LotEvenementsInvalide('manifest.json et campagne.json doivent être des objets JSON')
    if manifeste.get('schema_version') != 'campusequip-events-1':
        raise LotEvenementsInvalide('schema_version non pris en charge')
    campagne_id = manifeste.get('campaign_id')
    numero = manifeste.get('batch_no')
    lignes_annoncees = manifeste.get('rows')
    if not isinstance(campagne_id, str) or not campagne_id.strip():
        raise LotEvenementsInvalide('campaign_id absent')
    if isinstance(numero, bool) or not isinstance(numero, int) or numero <= 0:
        raise LotEvenementsInvalide('batch_no doit être un entier positif')
    if isinstance(lignes_annoncees, bool) or not isinstance(lignes_annoncees, int) or lignes_annoncees < 0:
        raise LotEvenementsInvalide('rows doit être un entier positif ou nul')
    profil = manifeste.get('profile')
    if not isinstance(profil, str) or profil not in {'propre', 'mixte'}:
        raise LotEvenementsInvalide('profile doit être propre ou mixte')
    fichiers = manifeste.get('files')
    if not isinstance(fichiers, dict) or set(fichiers) != {'evenements.jsonl'}:
        raise LotEvenementsInvalide('le manifeste doit décrire exactement evenements.jsonl')
    sha_contrats = manifeste.get('contracts_sha256')
    if not isinstance(sha_contrats, str) or not re.fullmatch(r'[0-9a-f]{64}', sha_contrats):
        raise LotEvenementsInvalide('contracts_sha256 absent ou invalide')
    if campagne.get('campaign_id') != campagne_id:
        raise LotEvenementsInvalide('campaign_id différent entre la campagne et le manifeste')
    if campagne.get('contrats_sha256') != sha_contrats:
        raise LotEvenementsInvalide('empreinte de l’export de contrats différente de la campagne')

    chemin_source = dossier / 'evenements.jsonl'
    sha_source = empreinte(chemin_source)
    if fichiers['evenements.jsonl'] != sha_source:
        raise LotEvenementsInvalide('empreinte SHA-256 incorrecte pour evenements.jsonl')
    try:
        contenu = chemin_source.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as erreur:
        raise LotEvenementsInvalide(f'evenements.jsonl illisible : {erreur}') from None
    lignes = contenu.splitlines()
    if len(lignes) != lignes_annoncees:
        raise LotEvenementsInvalide(
            f'le manifeste annonce {lignes_annoncees} lignes, le fichier en contient {len(lignes)}')
    source = []
    for numero_ligne, ligne in enumerate(lignes, 1):
        try:
            valeur = json.loads(ligne, parse_constant=_interdire_constante_json)
        except (json.JSONDecodeError, ValueError) as erreur:
            source.append((numero_ligne, {'_ligne_brute': ligne, '_erreur_json': str(erreur)}))
        else:
            source.append((numero_ligne, valeur))
    return manifeste, sha_source, source


def normaliser_evenement(valeur: Any) -> tuple[dict, datetime]:
    """Valide et normalise un document sans dépendance à une base de données."""
    if not isinstance(valeur, dict) or set(valeur) != CHAMPS_EVENEMENT:
        raise EvenementInvalide('CHAMPS_INVALIDES')
    champs = dict(valeur)
    for nom in ('device_id', 'event_id', 'event_type'):
        if not isinstance(champs[nom], str):
            raise EvenementInvalide(f'{nom.upper()}_INVALIDE')
        champs[nom] = champs[nom].strip()
    for nom in ('device_id', 'event_id'):
        if not champs[nom] or not IDENTIFIANT.fullmatch(champs[nom]):
            raise EvenementInvalide(f'{nom.upper()}_INVALIDE')
    champs['event_type'] = champs['event_type'].lower()
    if champs['event_type'] not in TYPES_EVENEMENT:
        raise EvenementInvalide('TYPE_EVENEMENT_INVALIDE')
    contract_id = champs['contract_id']
    if isinstance(contract_id, bool) or not isinstance(contract_id, int) or contract_id <= 0:
        raise EvenementInvalide('CONTRACT_ID_INVALIDE')
    horodatage = champs['observed_at']
    if not isinstance(horodatage, str) or not HORODATAGE_UTC.fullmatch(horodatage):
        raise EvenementInvalide('OBSERVED_AT_INVALIDE')
    try:
        instant = datetime.strptime(horodatage, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        raise EvenementInvalide('OBSERVED_AT_INVALIDE') from None
    payload = champs['payload']
    if not isinstance(payload, dict):
        raise EvenementInvalide('PAYLOAD_INVALIDE')
    if champs['event_type'] == 'position':
        if set(payload) != {'latitude', 'longitude'}:
            raise EvenementInvalide('COORDONNEES_INVALIDES')
        for cle, minimum, maximum in (
            ('latitude', -90, 90), ('longitude', -180, 180),
        ):
            coordonnee = payload[cle]
            if (isinstance(coordonnee, bool) or not isinstance(coordonnee, (int, float))
                    or not math.isfinite(coordonnee) or not minimum <= coordonnee <= maximum):
                raise EvenementInvalide('COORDONNEES_INVALIDES')
    try:
        json.dumps(champs, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError):
        raise EvenementInvalide('PAYLOAD_INVALIDE') from None
    return champs, instant


def json_canonique(valeur: dict) -> str:
    return json.dumps(valeur, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False)


def convertir_lignes(source: list[tuple[int, Any]], contrats_acceptes: set[int]) -> list[dict]:
    """Valide individuellement les lignes et conserve leur numéro et leur motif."""
    resultat = []
    for ligne, valeur in source:
        if isinstance(valeur, dict) and '_erreur_json' in valeur:
            resultat.append({'line': ligne, 'raw': valeur, 'reason': 'JSON_INVALIDE'})
            continue
        try:
            evenement, instant = normaliser_evenement(valeur)
            if evenement['contract_id'] not in contrats_acceptes:
                raise EvenementInvalide('CONTRAT_NON_ACCEPTE')
        except EvenementInvalide as erreur:
            resultat.append({'line': ligne, 'raw': valeur, 'reason': str(erreur)})
        else:
            resultat.append({'line': ligne, 'event': evenement, 'observed_at_date': instant})
    return resultat


def derniere_activite(evenements: list[dict]) -> dict[int, dict]:
    """Retourne le dernier événement non-position par contrat, ordre déterministe inclus."""
    derniers: dict[int, tuple[tuple, dict]] = {}
    for evenement in evenements:
        if evenement['event_type'] == 'position':
            continue
        instant = datetime.strptime(evenement['observed_at'], '%Y-%m-%dT%H:%M:%SZ')
        cle = (instant, evenement['device_id'], evenement['event_id'])
        identifiant = evenement['contract_id']
        if identifiant not in derniers or cle > derniers[identifiant][0]:
            derniers[identifiant] = (cle, evenement)
    return {identifiant: valeur[1] for identifiant, valeur in derniers.items()}


def horodatage_depuis_document(document: dict) -> datetime:
    """Lit l'instant UTC de MongoDB, en conservant le format source contrôlé."""
    valeur = document.get('observed_at_date')
    if isinstance(valeur, datetime):
        return valeur.replace(tzinfo=timezone.utc) if valeur.tzinfo is None else valeur.astimezone(timezone.utc)
    return datetime.strptime(document['normalized']['observed_at'], '%Y-%m-%dT%H:%M:%SZ').replace(
        tzinfo=timezone.utc)
