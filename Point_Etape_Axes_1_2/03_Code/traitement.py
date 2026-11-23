"""Traitement d'un lot CampusEquip : lire, contrôler, charger, rapporter.

`traiter_lot` est le point d'entrée appelé par `surveiller.py`. Il ne devine
jamais un statut : il renvoie exactement CHARGE, DEJA_CHARGE ou
REJETE_STRUCTURE, et laisse remonter toute panne de chargement pour que
l'échec reste visible.

Ordre des décisions (celui du cours) :
    structure du lot -> normalisation -> répétitions exactes -> lignes ->
    cohérence du contrat -> quarantaine -> transaction PostgreSQL.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import config, depot, regles

FICHIERS_ATTENDUS = {'locations.csv', 'referentiels.json'}
FICHIERS_OBLIGATOIRES = ('locations.csv', 'referentiels.json', 'manifest.json', 'READY')


# ---------------------------------------------------------------------------
# Lecture et contrôle de structure
# ---------------------------------------------------------------------------
def empreinte_fichier(chemin: Path) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def numero_lot(manifeste: dict, dossier: Path) -> int:
    """Numéro de lot du manifeste, à défaut celui du nom de dossier."""
    try:
        return int(manifeste['batch_number'])
    except (KeyError, TypeError, ValueError):
        chiffres = ''.join(caractere for caractere in dossier.name if caractere.isdigit())
        return int(chiffres) if chiffres else 0


def lire_entetes(chemin: Path) -> list[str]:
    """Lit seulement la première ligne du CSV et vérifie l'en-tête."""
    try:
        with Path(chemin).open(encoding='utf-8-sig', newline='') as flux:
            lecteur = csv.reader(flux)
            entetes = next(lecteur, None)
    except UnicodeDecodeError as erreur:
        raise regles.StructureInvalide(f'{Path(chemin).name} n\'est pas en UTF-8 : {erreur}') from None
    if entetes is None:
        raise regles.StructureInvalide('locations.csv est vide (aucun en-tête)')
    entetes = [colonne.strip('\ufeff') if index == 0 else colonne
               for index, colonne in enumerate(entetes)]
    if tuple(entetes) != regles.COLONNES:
        raise regles.StructureInvalide(
            'en-tête refusé : colonnes absentes, supplémentaires ou dans le mauvais ordre '
            f'({entetes} au lieu de {list(regles.COLONNES)})')
    return entetes


def verifier_structure(dossier: Path, manifeste: dict) -> dict:
    """Contrôles de structure qui ne lisent pas les lignes du CSV.

    Utilisé par la lecture complète ET par la lecture par morceaux : les deux
    chemins acceptent donc exactement les mêmes lots.
    """
    dossier = Path(dossier)
    if not isinstance(manifeste, dict):
        raise regles.StructureInvalide('manifest.json illisible')
    for nom in FICHIERS_OBLIGATOIRES:
        if not (dossier / nom).is_file():
            raise regles.StructureInvalide(f'fichier obligatoire absent : {nom}')

    if manifeste.get('schema_version') != regles.SCHEMA_VERSION:
        raise regles.StructureInvalide(
            f"schema_version attendu {regles.SCHEMA_VERSION}, "
            f"reçu {manifeste.get('schema_version')!r}")

    fichiers = manifeste.get('files')
    if not isinstance(fichiers, dict) or set(fichiers) != FICHIERS_ATTENDUS:
        raise regles.StructureInvalide(
            'le manifeste doit décrire exactement locations.csv et referentiels.json')

    campagne = manifeste.get('campaign_id')
    if not isinstance(campagne, str) or not campagne.strip():
        raise regles.StructureInvalide('campaign_id absent du manifeste')
    numero = numero_lot(manifeste, dossier)
    if numero <= 0:
        raise regles.StructureInvalide('batch_number absent ou invalide')

    empreintes = {}
    for nom in sorted(FICHIERS_ATTENDUS):
        reelle = empreinte_fichier(dossier / nom)
        if reelle != fichiers[nom]:
            raise regles.StructureInvalide(
                f'empreinte SHA-256 incorrecte pour {nom} : '
                'le fichier a changé depuis le manifeste')
        empreintes[nom] = reelle

    try:
        document = json.loads((dossier / 'referentiels.json').read_text(encoding='utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise regles.StructureInvalide(f'referentiels.json illisible : {erreur}') from None
    referentiels = regles.Referentiels.depuis_json(document)

    entetes = lire_entetes(dossier / 'locations.csv')

    return {'entetes': entetes, 'referentiels': referentiels, 'empreintes': empreintes,
            'campagne': campagne, 'numero': numero,
            'signature': regles.signature_lot(empreintes['locations.csv'],
                                             empreintes['referentiels.json']),
            'referentiel_signature': referentiels.empreinte(),
            'chemin_csv': dossier / 'locations.csv'}


def lire_sources(dossier: Path, manifeste: dict) -> dict:
    """Vérifie la structure du lot et renvoie ses sources intactes.

    Toute anomalie de structure lève StructureInvalide : le lot est alors refusé
    AVANT la moindre écriture métier.
    """
    structure = verifier_structure(dossier, manifeste)
    try:
        with structure['chemin_csv'].open(encoding='utf-8-sig', newline='') as flux:
            lecteur = csv.reader(flux)
            next(lecteur)
            lignes_brutes = [ligne for ligne in lecteur]
    except UnicodeDecodeError as erreur:
        raise regles.StructureInvalide(f'locations.csv n\'est pas en UTF-8 : {erreur}') from None

    attendu = manifeste.get('rows')
    if isinstance(attendu, int) and attendu != len(lignes_brutes):
        raise regles.StructureInvalide(
            f'le manifeste annonce {attendu} lignes, le fichier en contient {len(lignes_brutes)}')

    return {**structure, 'lignes': lignes_brutes}


# ---------------------------------------------------------------------------
# Préparation d'un lot (partie pure, testable sans base)
# ---------------------------------------------------------------------------
def preparer_lot(dossier: Path, manifeste: dict) -> depot.LotACharger:
    sources = lire_sources(dossier, manifeste)
    analyse = regles.analyser_lot(sources['entetes'], sources['lignes'],
                                  sources['referentiels'])
    return depot.LotACharger(
        dossier_source=str(Path(dossier).resolve()),
        campaign_id=sources['campagne'],
        batch_number=sources['numero'],
        schema_version=regles.SCHEMA_VERSION,
        profil=manifeste.get('profile'),
        signature=sources['signature'],
        locations_sha256=sources['empreintes']['locations.csv'],
        referentiels_sha256=sources['empreintes']['referentiels.json'],
        referentiel_signature=sources['referentiel_signature'],
        analyse=analyse,
        referentiels=sources['referentiels'],
    )


# ---------------------------------------------------------------------------
# Rapports
# ---------------------------------------------------------------------------
def _horodatage() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%f')


def _compteurs(analyse: regles.AnalyseLot, lignes_ajoutees: int) -> dict:
    return {
        'lignes_recues': analyse.lignes_recues,
        'doublons_retires': len(analyse.doublons),
        'lignes_apres_dedoublonnage': analyse.lignes_apres_dedoublonnage,
        'lignes_acceptees': len(analyse.acceptees),
        'lignes_rejetees': len(analyse.rejetees),
        'contrats_recus': analyse.contrats_recus,
        'contrats_acceptes': analyse.contrats_acceptes,
        'contrats_rejetes': analyse.contrats_rejetes,
        'anomalies': len(analyse.anomalies),
        'taux_rejet_pct': float(analyse.taux_rejet),
        'alerte_qualite': bool(analyse.alerte),
        'lignes_ajoutees_en_base': lignes_ajoutees,
    }


def _detail_rejets(analyse: regles.AnalyseLot) -> list[dict]:
    return [{'position': ligne.position,
             'contract_id': ligne.contrat_cle,
             'line_no': (ligne.norm or {}).get('line_no'),
             'motifs': list(ligne.motifs),
             'valeurs_brutes': ligne.valeurs_brutes_json()}
            for ligne in analyse.rejetees]


def _detail_anomalies(analyse: regles.AnalyseLot) -> list[dict]:
    details = []
    for ligne in analyse.anomalies:
        for anomalie in ligne.anomalies:
            details.append({'position': ligne.position,
                            'contract_id': ligne.contrat_cle,
                            'line_no': (ligne.norm or {}).get('line_no'),
                            'code': anomalie.split(':', 1)[0],
                            'detail': anomalie})
    return details


def ecrire_rapport(rapport: dict, sorties: config.Sorties) -> Path:
    base = f"lot_{rapport['lot']:06d}_{_horodatage()}"
    chemin = sorties.rapports / f'rapport_{base}.json'
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2, default=str) + '\n',
                      encoding='utf-8')
    (sorties.rapports / f'rapport_{base}.md').write_text(_rapport_markdown(rapport),
                                                         encoding='utf-8')
    with (sorties.rapports / 'index_rapports.jsonl').open('a', encoding='utf-8') as journal:
        journal.write(json.dumps({cle: rapport.get(cle) for cle in
                                  ('horodatage', 'lot', 'statut', 'batch_id', 'compteurs',
                                   'motif_rejet_structure', 'duree_ms')},
                                 ensure_ascii=False, default=str) + '\n')
    return chemin


def _rapport_markdown(rapport: dict) -> str:
    compteur = rapport['compteurs']
    lignes = [
        f"# Rapport de traitement — lot {rapport['lot']:06d}",
        '',
        f"- **Statut** : `{rapport['statut']}`",
        f"- **Campagne** : `{rapport['campagne']}`",
        f"- **Dossier source** : `{rapport['dossier']}`",
        f"- **Profil** : {rapport.get('profil') or 'inconnu'}",
        f"- **Signature** : `{rapport.get('signature')}`",
        f"- **Version des règles** : {rapport['rules_version']}",
        f"- **Batch en base** : {rapport.get('batch_id')}",
        f"- **Durée** : {rapport['duree_ms']} ms",
        '',
    ]
    if rapport.get('motif_rejet_structure'):
        lignes += [f"> **Lot refusé avant écriture métier** : {rapport['motif_rejet_structure']}", '']
    lignes += [
        '## Compteurs',
        '',
        '| Indicateur | Valeur |',
        '|---|---:|',
        f"| Lignes reçues | {compteur['lignes_recues']} |",
        f"| Répétitions exactes retirées | {compteur['doublons_retires']} |",
        f"| Lignes après dédoublonnage | {compteur['lignes_apres_dedoublonnage']} |",
        f"| Lignes acceptées par les contrôles | {compteur['lignes_acceptees']} |",
        f"| Lignes rejetées (quarantaine) | {compteur['lignes_rejetees']} |",
        f"| Contrats acceptés | {compteur['contrats_acceptes']} |",
        f"| Contrats rejetés | {compteur['contrats_rejetes']} |",
        f"| Anomalies signalées (lignes acceptées) | {compteur['anomalies']} |",
        f"| Taux de rejet | {compteur['taux_rejet_pct']:.2f} % |",
        f"| Alerte qualité (> 20 %) | {'oui' if compteur['alerte_qualite'] else 'non'} |",
        f"| Lignes réellement ajoutées en base | {compteur['lignes_ajoutees_en_base']} |",
        '',
    ]
    if compteur['doublons_retires'] == 0 and compteur['lignes_recues'] != \
            compteur['lignes_apres_dedoublonnage']:
        lignes.append('*Incohérence de comptage à vérifier.*')
    lignes += ['## Rejets (quarantaine)', '']
    if rapport['rejets']:
        lignes += ['| Ligne | Contrat | Ligne n° | Motifs |', '|---:|---|---:|---|']
        for rejet in rapport['rejets'][:40]:
            motifs = ' ; '.join(rejet['motifs']).replace('|', '/')
            lignes.append(f"| {rejet['position']} | {rejet['contract_id']} | "
                          f"{rejet['line_no'] or ''} | {motifs} |")
        if len(rapport['rejets']) > 40:
            lignes.append(f"| … | | | {len(rapport['rejets']) - 40} rejets supplémentaires "
                          f"(voir le JSON) |")
    else:
        lignes.append('Aucun rejet.')
    lignes += ['', '## Anomalies signalées', '']
    if rapport['anomalies']:
        lignes += ['| Ligne | Contrat | Ligne n° | Code | Détail |', '|---:|---|---:|---|---|']
        for anomalie in rapport['anomalies'][:20]:
            lignes.append(f"| {anomalie['position']} | {anomalie['contract_id']} | "
                          f"{anomalie['line_no'] or ''} | {anomalie['code']} | "
                          f"{anomalie['detail']} |")
    else:
        lignes.append('Aucune anomalie.')
    lignes += ['',
               f"Fichier de quarantaine : `{rapport.get('quarantaine')}`",
               '']
    return '\n'.join(lignes)


def ecrire_quarantaine(rapport: dict, analyse: regles.AnalyseLot | None,
                       sorties: config.Sorties) -> Path:
    chemin = sorties.quarantaine / f"lot_{rapport['lot']:06d}_{_horodatage()}.jsonl"
    with chemin.open('w', encoding='utf-8') as flux:
        if analyse is not None:
            for rejet in _detail_rejets(analyse):
                flux.write(json.dumps({'lot': rapport['lot'],
                                       'campagne': rapport['campagne'],
                                       'signature': rapport.get('signature'),
                                       **rejet}, ensure_ascii=False, default=str) + '\n')
    return chemin


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def traiter_lot(dossier, manifeste, connexion_factory: Callable | None = None,
                sorties: config.Sorties | None = None) -> dict:
    """Traite un lot complet et renvoie un statut documenté.

    Renvoie {'status': 'CHARGE' | 'DEJA_CHARGE' | 'REJETE_STRUCTURE', ...}.
    Toute panne de chargement lève une exception après avoir écrit un rapport
    d'échec : elle ne doit jamais être présentée comme un succès.
    """
    debut = time.perf_counter()
    dossier = Path(dossier)
    sorties = sorties or config.Sorties.par_defaut()
    ouvrir_connexion = connexion_factory or depot.connexion
    lot = None
    analyse = None

    try:
        lot = preparer_lot(dossier, manifeste)
        analyse = lot.analyse
    except regles.StructureInvalide as erreur:
        return _refuser_structure(
            dossier, manifeste, erreur, sorties, debut, ouvrir_connexion)

    rapport = {
        'horodatage': datetime.now(timezone.utc).isoformat(),
        'statut': None,
        'lot': lot.batch_number,
        'campagne': lot.campaign_id,
        'dossier': str(dossier.resolve()),
        'profil': lot.profil,
        'signature': lot.signature,
        'empreintes': {'locations.csv': lot.locations_sha256,
                       'referentiels.json': lot.referentiels_sha256},
        'referentiel_signature': lot.referentiel_signature,
        'rules_version': regles.RULES_VERSION,
        'schema_version': lot.schema_version,
        'batch_id': None,
        'duree_ms': 0,
        'motif_rejet_structure': None,
        'compteurs': _compteurs(analyse, 0),
        'rejets': _detail_rejets(analyse),
        'anomalies': _detail_anomalies(analyse),
        'quarantaine': None,
    }

    cnx = None
    try:
        cnx = ouvrir_connexion()
        resultat = depot.charger_lot(cnx, lot)
    except depot.RefusStructure as refus:
        if cnx is not None:
            batch_id = depot.enregistrer_refus(cnx, lot, refus.code, refus.detail)
        else:
            batch_id = None
        rapport.update(statut='REJETE_STRUCTURE', batch_id=batch_id,
                       motif_rejet_structure=f'{refus.code}: {refus.detail}',
                       compteurs=_compteurs(analyse, 0))
        rapport['quarantaine'] = str(ecrire_quarantaine(rapport, analyse, sorties))
        rapport['duree_ms'] = round((time.perf_counter() - debut) * 1000, 1)
        chemin = ecrire_rapport(rapport, sorties)
        return {**resume(rapport), 'rapport': str(chemin)}
    except Exception as erreur:
        rapport.update(statut='ECHEC', motif_rejet_structure=f'{type(erreur).__name__}: {erreur}',
                       trace=f'{type(erreur).__name__}: {erreur}',
                       trace_complete=traceback.format_exc(),
                       compteurs=_compteurs(analyse, 0))
        rapport['duree_ms'] = round((time.perf_counter() - debut) * 1000, 1)
        rapport['quarantaine'] = str(ecrire_quarantaine(rapport, analyse, sorties))
        ecrire_rapport(rapport, sorties)
        raise
    finally:
        if cnx is not None:
            cnx.close()

    if resultat.statut == 'CHARGE':
        rapport.update(statut='CHARGE', batch_id=resultat.batch_id,
                       compteurs=_compteurs(analyse, resultat.lignes_ajoutees))
    else:
        existant = resultat.existant
        rapport.update(statut='DEJA_CHARGE', batch_id=resultat.batch_id,
                       compteurs={**_compteurs(analyse, 0),
                                  'lignes_ajoutees_en_base': 0},
                       deja_charge_le=str(existant.get('charge_le')),
                       deja_lignes_acceptees=existant.get('rows_accepted'))

    rapport['quarantaine'] = str(ecrire_quarantaine(rapport, analyse, sorties))
    rapport['duree_ms'] = round((time.perf_counter() - debut) * 1000, 1)
    chemin = ecrire_rapport(rapport, sorties)
    return {**resume(rapport), 'rapport': str(chemin)}


def _refuser_structure(dossier: Path, manifeste: dict, erreur: Exception,
                       sorties: config.Sorties, debut: float,
                       connexion_factory: Callable | None = None) -> dict:
    """Refus avant écriture métier : on trace le refus, on ne charge rien."""
    manifeste = manifeste if isinstance(manifeste, dict) else {}
    numero = numero_lot(manifeste, dossier)
    analyse = regles.AnalyseLot(lignes=[], doublons=[], lignes_recues=0,
                                contrats_recus=0, contrats_acceptes=0, contrats_rejetes=0)
    lot = depot.LotACharger(
        dossier_source=str(Path(dossier).resolve()),
        campaign_id=str(manifeste.get('campaign_id') or 'inconnue'),
        batch_number=numero,
        schema_version=str(manifeste.get('schema_version') or 'inconnue'),
        profil=manifeste.get('profile'),
        signature=None,
        locations_sha256='',
        referentiels_sha256='',
        referentiel_signature=None,
        analyse=analyse,
        referentiels=None,
    )
    rapport = {
        'horodatage': datetime.now(timezone.utc).isoformat(),
        'statut': 'REJETE_STRUCTURE',
        'lot': numero,
        'campagne': lot.campaign_id,
        'dossier': str(Path(dossier).resolve()),
        'profil': lot.profil,
        'signature': None,
        'empreintes': {},
        'referentiel_signature': None,
        'rules_version': regles.RULES_VERSION,
        'schema_version': lot.schema_version,
        'batch_id': None,
        'duree_ms': 0,
        'motif_rejet_structure': f'STRUCTURE_INVALIDE: {erreur}',
        'compteurs': _compteurs(analyse, 0),
        'rejets': [],
        'anomalies': [],
        'quarantaine': None,
    }
    cnx = None
    try:
        cnx = (connexion_factory or depot.connexion)()
        rapport['batch_id'] = depot.enregistrer_refus(
            cnx, lot, 'STRUCTURE_INVALIDE', str(erreur))
    except Exception as panne:
        rapport['journal_indisponible'] = f'{type(panne).__name__}: {panne}'
    finally:
        if cnx is not None:
            cnx.close()

    rapport['quarantaine'] = str(ecrire_quarantaine(rapport, None, sorties))
    rapport['duree_ms'] = round((time.perf_counter() - debut) * 1000, 1)
    chemin = ecrire_rapport(rapport, sorties)
    return {**resume(rapport), 'rapport': str(chemin)}


def resume(rapport: dict) -> dict:
    """Vue compacte renvoyée au surveilleur (le détail est dans le rapport)."""
    compteur = rapport['compteurs']
    return {
        'status': rapport['statut'],
        'lot': rapport['lot'],
        'batch_id': rapport['batch_id'],
        'lignes_recues': compteur['lignes_recues'],
        'doublons_retires': compteur['doublons_retires'],
        'lignes_acceptees': compteur['lignes_acceptees'],
        'lignes_rejetees': compteur['lignes_rejetees'],
        'contrats_acceptes': compteur['contrats_acceptes'],
        'contrats_rejetes': compteur['contrats_rejetes'],
        'anomalies': compteur['anomalies'],
        'taux_rejet': compteur['taux_rejet_pct'],
        'alerte_qualite': compteur['alerte_qualite'],
        'lignes_ajoutees_en_base': compteur['lignes_ajoutees_en_base'],
        'motif': rapport.get('motif_rejet_structure'),
    }
