from __future__ import annotations

import csv
from itertools import islice
from pathlib import Path

from etudiant import regles, traitement

MORCEAU_PAR_DEFAUT = 1000


def lignes_par_morceaux(chemin: Path, taille: int):
    """Génère (position_de_depart, morceau) sans jamais charger tout le fichier."""
    with Path(chemin).open(encoding='utf-8-sig', newline='') as flux:
        lecteur = csv.reader(flux)
        next(lecteur, None)                      # en-tête déjà vérifié
        position = 2                             # première ligne de données
        while True:
            morceau = list(islice(lecteur, taille))
            if not morceau:
                break
            yield position, morceau
            position += len(morceau)


def analyser_par_morceaux(dossier, manifeste: dict,
                          taille: int = MORCEAU_PAR_DEFAUT) -> tuple[regles.AnalyseLot, dict]:
    """Applique les mêmes règles que la lecture complète, tranche par tranche."""
    if taille < 1:
        raise ValueError('taille de morceau >= 1')
    structure = traitement.verifier_structure(dossier, manifeste)
    referentiels = structure['referentiels']

    vues: set[tuple] = set()
    uniques: list[regles.Ligne] = []
    doublons: list[regles.Ligne] = []
    malformees: list[regles.Ligne] = []
    recues = 0
    morceaux = 0

    for depart, morceau in lignes_par_morceaux(structure['chemin_csv'], taille):
        morceaux += 1
        for decalage, champs in enumerate(morceau):
            ligne = regles.construire_ligne(depart + decalage, champs, referentiels)
            recues += 1
            if ligne.norm is None:
                malformees.append(ligne)
                continue
            cle = regles.cle_dedoublonnage(ligne.norm)
            if cle in vues:
                doublons.append(ligne)
            else:
                vues.add(cle)
                uniques.append(ligne)
        del morceau                              # les lignes brutes sont libérées

    attendu = manifeste.get('rows')
    if isinstance(attendu, int) and attendu != recues:
        raise regles.StructureInvalide(
            f'le manifeste annonce {attendu} lignes, le fichier en contient {recues}')

    analyse = regles.finaliser_analyse(uniques, malformees, doublons, recues)
    return analyse, {'morceaux': morceaux, 'lignes': recues, 'taille': taille}


def empreinte_decisions(analyse: regles.AnalyseLot) -> tuple:
    """Signature des décisions : position, verdict, motifs, anomalies, montant."""
    return tuple(
        (ligne.position,
         ligne.acceptee,
         tuple(ligne.motifs),
         tuple(ligne.anomalies),
         f'{ligne.montant:.2f}' if ligne.montant is not None else None)
        for ligne in analyse.lignes)
