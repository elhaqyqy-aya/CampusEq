"""Preuve ciblée : alerte au-delà de 20 % de rejet, sans bloquer les contrats valides.

    python -m outils.preuve_alerte

Le profil `mixte` ne garantit pas de franchir le seuil de 20 % : le sujet demande
donc un petit cas construit exprès. Ce script le charge dans une base dédiée
(`campusequip_alerte`, jamais la base de démonstration) et conserve le rapport
JSON produit par le pipeline dans `preuves/alerte.md`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import config, depot, traitement  # noqa: E402
from tests import fabrique  # noqa: E402


def url_dediee() -> str:
    url = config.url_base()
    parties = urlsplit(url)
    return urlunsplit((parties.scheme, parties.netloc, '/campusequip_alerte',
                       parties.query, parties.fragment))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sortie', type=Path, default=RACINE / 'preuves')
    arguments = p.parse_args()
    arguments.sortie.mkdir(parents=True, exist_ok=True)

    url_origine = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url_dediee()
    from outils import init_base  # noqa: E402  (après la bascule d'URL)
    init_base.reinitialiser(url_dediee())
    cnx = depot.connexion()
    try:
        depot.schema(cnx)
    finally:
        cnx.close()

    dossier = RACINE / '.tests_tmp' / 'alerte' / 'lot_000001'
    lignes = [fabrique.ligne(contract_id=identifiant) for identifiant in range(1, 7)]
    lignes.append(fabrique.ligne(contract_id=1, line_no=2, quantity=25))
    lignes += [fabrique.ligne(contract_id=identifiant, quantity=-1)
               for identifiant in range(7, 10)]
    dossier.parent.mkdir(parents=True, exist_ok=True)
    dossier, manifeste = fabrique.ecrire_lot(dossier, lignes, lot=1,
                                             campagne='campagne-alerte')

    resultat = traitement.traiter_lot(dossier, manifeste)
    rapport = json.loads(Path(resultat['rapport']).read_text(encoding='utf-8'))

    cnx = depot.connexion()
    try:
        contrats = depot.compter(cnx, 'contracts')
        anomalies = depot.compter(cnx, 'batch_anomalies')
        rejets = depot.compter(cnx, 'batch_rejections')
    finally:
        cnx.close()

    # La base dédiée n'est pas conservée : on remet la connexion d'origine.
    if url_origine is None:
        os.environ.pop('DATABASE_URL', None)
    else:
        os.environ['DATABASE_URL'] = url_origine

    lignes_md = [
        '# Preuve — alerte au-delà de 20 % de rejet', '',
        'Cas construit exprès : 9 contrats, dont 3 avec une quantité négative ',
        '(contrats 7, 8, 9) et un contrat valide portant une anomalie de quantité 25.',
        '',
        '| Indicateur | Attendu | Observé |', '|---|---|---|',
        f"| Statut | CHARGE | {resultat['status']} |",
        f"| Lignes reçues | 10 | {resultat['lignes_recues']} |",
        f"| Doublons retirés | 0 | {resultat['doublons_retires']} |",
        f"| Lignes acceptées | 7 | {resultat['lignes_acceptees']} |",
        f"| Lignes rejetées | 3 | {resultat['lignes_rejetees']} |",
        f"| Taux de rejet | 30,00 % | {resultat['taux_rejet']:.2f} % |",
        f"| Alerte qualité | oui | {'oui' if resultat['alerte_qualite'] else 'NON'} |",
        f"| Contrats acceptés | 6 | {resultat['contrats_acceptes']} |",
        f"| Contrats rejetés | 3 | {resultat['contrats_rejetes']} |",
        f"| Lignes ajoutées en base | 7 | {resultat['lignes_ajoutees_en_base']} |",
        '',
        f"En base : **{contrats} contrats**, {rejets} ligne(s) en quarantaine, "
        f"{anomalies} anomalie(s) signalée(s).",
        '',
        '## Ce que la preuve démontre',
        '',
        "L'alerte n'interrompt pas le chargement : les 6 contrats valides sont en base, "
        "les 3 contrats invalides restent en quarantaine avec leurs motifs, et le taux "
        "de rejet (3 / 10 = 30 %) dépasse le seuil de 20 %. L'anomalie de quantité 25 "
        "reste une ligne acceptée et signalée : elle n'entre ni dans les rejets ni dans "
        'le taux.',
        '',
        '## Extrait du rapport produit',
        '',
        '```json',
        json.dumps({cle: rapport[cle] for cle in
                    ('statut', 'lot', 'campagne', 'compteurs', 'motif_rejet_structure')},
                   ensure_ascii=False, indent=2),
        '```',
        '',
        f"Rapport complet : `{resultat['rapport']}`. Base utilisée : `campusequip_alerte` "
        '(isolée de la base de démonstration).',
        '',
    ]
    (arguments.sortie / 'alerte.md').write_text('\n'.join(lignes_md) + '\n', encoding='utf-8')
    print('\n'.join(lignes_md[:18]))
    print('preuve écrite dans', arguments.sortie / 'alerte.md')
    return 0 if (resultat['status'] == 'CHARGE' and resultat['alerte_qualite']
                 and resultat['contrats_acceptes'] == 6) else 1


if __name__ == '__main__':
    raise SystemExit(main())
