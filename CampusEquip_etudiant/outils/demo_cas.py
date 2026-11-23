"""Cas limites à montrer en démonstration, sans abîmer les fichiers du kit.

    python -m outils.demo_cas --cas structure
        Construit un lot dont l'en-tête est incorrect et le traite :
        REJETE_STRUCTURE attendu, aucune écriture métier.

    python -m outils.demo_cas --cas conflit
        Construit un lot qui réutilise un contract_id déjà chargé :
        la transaction doit échouer, le journal précédent rester intact.

Les lots sont écrits dans `.demo/` (recréé à chaque appel) et jamais dans
`exemples/`, qui reste la copie intacte du kit.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot, traitement  # noqa: E402
from tests import fabrique  # noqa: E402

TRAVAIL = RACINE / '.demo'
FLUX = RACINE / 'flux_demo'


def referentiels_du_flux() -> dict:
    """Réutilise les référentiels de la campagne de démonstration si elle existe."""
    for manifeste in sorted(FLUX.glob('lot_*/referentiels.json')):
        return json.loads(manifeste.read_text(encoding='utf-8'))
    return fabrique.REFERENTIELS


def cas_structure() -> int:
    dossier = TRAVAIL / 'structure' / 'lot_000001'
    if dossier.parent.exists():
        shutil.rmtree(dossier.parent)
    entetes = list(fabrique.COLONNES)
    entetes[1], entetes[2] = entetes[2], entetes[1]        # client_id <-> site_id
    dossier, manifeste = fabrique.ecrire_lot(
        dossier,
        [['2001', '3', '12', '2026-11-02', 'paid', '1', '8', '2', 'hour', '3', '25.00']],
        entetes=entetes, lot=990, campagne='campagne-demo-structure')
    print(f'Lot écrit : {dossier}')
    print('En-tête envoyé :', ','.join(entetes))
    resultat = traitement.traiter_lot(dossier, manifeste)
    print('Résultat :', {cle: resultat[cle] for cle in
                         ('status', 'lignes_ajoutees_en_base', 'motif')})
    return 0 if resultat['status'] == 'REJETE_STRUCTURE' else 1


def cas_conflit() -> int:
    cnx = depot.connexion()
    try:
        with cnx.cursor() as cur:
            cur.execute("SELECT valeur FROM lab_config WHERE cle = 'campaign_id'")
            ligne = cur.fetchone()
            campagne = ligne[0] if ligne else 'campagne-demo-conflit'
            cur.execute("""
                SELECT c.contract_id, c.client_id, c.site_id, c.start_date, c.status,
                       l.equipment_id, l.quantity, l.unit, l.duration, l.unit_rate
                FROM contracts c
                JOIN contract_lines l USING (contract_id)
                ORDER BY c.contract_id, l.line_no
                LIMIT 1
            """)
            existant = cur.fetchone()
        cnx.rollback()
    finally:
        cnx.close()
    if existant is None:
        print('Aucun contrat en base : lancez python -m outils.demo d’abord.')
        return 2

    (contract_id, client_id, site_id, start_date, status, equipment_id, quantity,
     unite, duree, tarif) = existant
    dossier = TRAVAIL / 'conflit' / 'lot_000002'
    if dossier.parent.exists():
        shutil.rmtree(dossier.parent)
    dossier, manifeste = fabrique.ecrire_lot(
        dossier,
        [fabrique.ligne(contract_id=contract_id, client_id=client_id, site_id=site_id,
                        start_date=start_date.isoformat(), status=status,
                        line_no=1, equipment_id=equipment_id, quantity=quantity,
                        unit=unite, duration=duree + 1, unit_rate=str(tarif))],
        lot=991, campagne=campagne, referentiels=referentiels_du_flux())
    print(f'Lot écrit : {dossier}')
    print(f'Il réutilise le contrat déjà chargé {contract_id}, dans la campagne de la base.')
    try:
        traitement.traiter_lot(dossier, manifeste)
    except depot.ConflitContrat as erreur:
        print('Conflit attendu :', erreur)
        print('Transaction annulée, journal du lot précédent intact.')
        return 0
    print('Aucun conflit détecté : le test n’est pas concluant.')
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--cas', choices=['structure', 'conflit'], default='structure')
    arguments = p.parse_args()
    return cas_structure() if arguments.cas == 'structure' else cas_conflit()


if __name__ == '__main__':
    raise SystemExit(main())
