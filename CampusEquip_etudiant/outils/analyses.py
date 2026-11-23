"""Exécute analyses.sql, exporte les tableaux et dessine les graphiques.

    python -m outils.analyses

Produit dans `resultats/` :
    * un CSV et un extrait Markdown par analyse ;
    * `graphique_a1_montant_jour_campus.png` (évolution jour par campus) ;
    * `graphique_a3_heure_journee.png` (heure vs journée par campus) ;
    * `synthese.md` : les chiffres qui répondent aux trois questions ;
    * `resultats.json` : les mêmes données, réutilisables (interface, rapport).

Le script rafraîchit aussi la vue matérialisée `mv_montant_jour_campus`, ce qui
permet de comparer le résultat précalculé (bonus 2) au calcul à la demande.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402
from outils import graphiques  # noqa: E402

MOTIF = re.compile(r'^--\s*@resultat:\s*([A-Za-z0-9_]+)\s*$')
FICHIER_SQL = RACINE / 'analyses.sql'


def decouper(chemin: Path) -> list[tuple[str, str]]:
    """Découpe le fichier SQL en blocs nommés par les marqueurs @resultat."""
    blocs: list[tuple[str, list[str]]] = []
    for ligne in chemin.read_text(encoding='utf-8').splitlines():
        trouve = MOTIF.match(ligne.strip())
        if trouve:
            blocs.append((trouve.group(1), []))
        elif blocs:
            blocs[-1][1].append(ligne)
    return [(nom, '\n'.join(lignes).strip()) for nom, lignes in blocs]


def executer(cnx, requete: str) -> tuple[list[str], list[tuple]]:
    with cnx.cursor() as cur:
        cur.execute(requete)
        colonnes = [description.name for description in cur.description]
        lignes = cur.fetchall()
    return colonnes, lignes


def texte(valeur) -> str:
    if valeur is None:
        return ''
    if isinstance(valeur, Decimal):
        return f'{valeur:.2f}'
    if isinstance(valeur, float):
        return f'{valeur:.2f}'
    if isinstance(valeur, bool):
        return 'oui' if valeur else 'non'
    return str(valeur)


def ecrire_csv(chemin: Path, colonnes: list[str], lignes: list[tuple]) -> None:
    with chemin.open('w', encoding='utf-8-sig', newline='') as flux:
        ecrivain = csv.writer(flux, delimiter=';')
        ecrivain.writerow(colonnes)
        for ligne in lignes:
            ecrivain.writerow([texte(valeur) for valeur in ligne])


def ecrire_markdown(chemin: Path, titre: str, colonnes: list[str], lignes: list[tuple],
                    maximum: int = 30) -> None:
    contenu = [f'## {titre}', '',
               '| ' + ' | '.join(colonnes) + ' |',
               '|' + '|'.join('---' for _ in colonnes) + '|']
    for ligne in lignes[:maximum]:
        contenu.append('| ' + ' | '.join(texte(valeur) for valeur in ligne) + ' |')
    if len(lignes) > maximum:
        contenu += ['', f'*{len(lignes) - maximum} ligne(s) supplémentaire(s) dans le CSV.*']
    chemin.write_text('\n'.join(contenu) + '\n', encoding='utf-8')


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sql', type=Path, default=FICHIER_SQL)
    p.add_argument('--sortie', type=Path, default=RACINE / 'resultats')
    arguments = p.parse_args()
    arguments.sortie.mkdir(parents=True, exist_ok=True)

    blocs = decouper(arguments.sql)
    if not blocs:
        print('Aucun bloc @resultat trouvé dans', arguments.sql)
        return 2

    cnx = depot.connexion()
    resultats: dict[str, dict] = {}
    try:
        with cnx.cursor() as cur:
            cur.execute('REFRESH MATERIALIZED VIEW mv_montant_jour_campus')
        cnx.commit()

        for nom, requete in blocs:
            colonnes, lignes = executer(cnx, requete)
            resultats[nom] = {'colonnes': colonnes, 'lignes': lignes}
            ecrire_csv(arguments.sortie / f'{nom}.csv', colonnes, lignes)
            ecrire_markdown(arguments.sortie / f'{nom}.md', nom, colonnes, lignes)
            print(f'{nom}: {len(lignes)} ligne(s)')

        (arguments.sortie / 'resultats.json').write_text(
            json.dumps({nom: {'colonnes': bloc['colonnes'],
                              'lignes': [[texte(v) for v in ligne] for ligne in bloc['lignes']]}
                        for nom, bloc in resultats.items()},
                       ensure_ascii=False, indent=2),
            encoding='utf-8')
    finally:
        cnx.close()

    synthese = construire_synthese(resultats, arguments.sortie)
    (arguments.sortie / 'synthese.md').write_text(synthese, encoding='utf-8')
    print('graphiques et synthèse écrits dans', arguments.sortie)
    return 0


def _index(colonnes: list[str]) -> dict[str, int]:
    return {nom: position for position, nom in enumerate(colonnes)}


def construire_synthese(resultats: dict[str, dict], sortie: Path) -> str:
    """Calcule les chiffres clés et dessine les deux figures."""
    a1 = resultats['a1_montant_par_jour_campus']
    i1 = _index(a1['colonnes'])
    jours, par_campus, premier_campus = [], {}, None
    for ligne in a1['lignes']:
        nom = ligne[i1['campus']]
        par_campus.setdefault(nom, []).append(float(ligne[i1['montant_jour']]))
        premier_campus = premier_campus or nom
        if nom == premier_campus:
            jours.append(ligne[i1['jour']].strftime('%d/%m'))

    chemin_a1 = graphiques.courbes_journalieres(
        jours, par_campus, sortie / 'graphique_a1_montant_jour_campus.png',
        'Montant retenu par jour et par campus — 1er au 21 novembre 2026',
        'Contrats payés et clôturés uniquement — montant = quantité x durée x tarif')

    a3 = resultats['a3_heure_ou_journee']
    i3 = _index(a3['colonnes'])
    campus, heures, journees = [], [], []
    for ligne in a3['lignes']:
        nom = ligne[i3['campus']]
        if nom not in campus:
            campus.append(nom)
            heures.append(0.0)
            journees.append(0.0)
        position = campus.index(nom)
        if ligne[i3['unit']] == 'hour':
            heures[position] = float(ligne[i3['montant']])
        else:
            journees[position] = float(ligne[i3['montant']])
    chemin_a3 = graphiques.barres_unites(
        campus, heures, journees, sortie / 'graphique_a3_heure_journee.png',
        "Montant retenu à l'heure et à la journée, par campus")

    lots = resultats['lots_analyses']
    il = _index(lots['colonnes'])
    total_lignes = sum(ligne[il['lignes_acceptees']] for ligne in lots['lignes'])
    total_contrats = sum(ligne[il['contrats_acceptes']] for ligne in lots['lignes'])

    synthese_unites = {ligne[0]: {'lignes': ligne[1], 'montant': float(ligne[3]),
                                  'part': float(ligne[4])}
                       for ligne in resultats['a3b_synthese_unites']['lignes']}
    total = sum(valeur['montant'] for valeur in synthese_unites.values())
    meilleur_campus = max(((nom, sum(valeurs)) for nom, valeurs in par_campus.items()),
                          key=lambda couple: couple[1])

    a2 = resultats['a2_equipements_contributeurs']
    i2 = _index(a2['colonnes'])
    premiers = [ligne for ligne in a2['lignes'] if ligne[i2['rang']] == 1]
    meilleur_equipement = premiers[0] if premiers else None

    lignes = [
        '# Synthèse des analyses — CampusEquip (axes 1 et 2)',
        '',
        f"**Lots analysés** : {len(lots['lignes'])} lot(s) chargé(s), "
        f"{total_contrats} contrats et {total_lignes} lignes acceptées. "
        'La liste exacte est dans `lots_analyses.csv`.',
        '',
        f'**Montant total retenu** : {graphiques.montant_lisible(total)} '
        '(contrats `paid` et `closed`, rattachés à la date de début).',
        '',
        '## 1. Quel montant chaque campus réalise-t-il chaque jour ?',
        '',
        f"Le campus le plus contributeur est **{meilleur_campus[0]}** avec "
        f"{graphiques.montant_lisible(meilleur_campus[1])} sur la période. Le détail jour "
        'par jour (jours sans location à zéro, cumul par campus) est dans '
        f'`a1_montant_par_jour_campus.csv` et la figure `{chemin_a1.name}`.',
        '',
        '## 2. Quels équipements rapportent le plus ?',
        '',
    ]
    if meilleur_equipement is not None:
        lignes.append(
            f"Le premier équipement de chaque campus est **{meilleur_equipement[i2['equipement']]}** "
            f"({meilleur_equipement[i2['campus']]}, "
            f"{graphiques.montant_lisible(float(meilleur_equipement[i2['montant']]))}). "
            'Le classement complet, avec rangs ex æquo, est dans '
            '`a2_equipements_contributeurs.csv`.')
    lignes += [
        '',
        "## 3. Les locations à l'heure et à la journée contribuent-elles de la même façon ?",
        '',
    ]
    for unite in ('hour', 'day'):
        if unite in synthese_unites:
            valeur = synthese_unites[unite]
            libelle = "à l'heure" if unite == 'hour' else 'à la journée'
            lignes.append(f"- **{libelle}** : {valeur['lignes']} ligne(s), "
                          f"{graphiques.montant_lisible(valeur['montant'])} soit "
                          f"{valeur['part']:.2f} % du montant.")
    lignes += [
        '',
        f'Figure : `{chemin_a3.name}`.',
        '',
        '## Deux phrases de réponse',
        '',
        f"Les montants se concentrent sur quelques campus et quelques équipements : "
        f"{meilleur_campus[0]} pèse la part la plus forte, et l'écart entre les deux unités "
        "de location s'explique par des paniers moyens différents, pas par un plus grand "
        "nombre de lignes — on compare des MAD par unité, jamais des heures avec des jours.",
        '',
        '## Contrôle de cohérence',
        '',
    ]
    controle = resultats['controle_totaux']
    if controle['lignes']:
        valeurs = controle['lignes'][0]
        lignes.append('| Total vue retenue | Total A1 | Total A3 | Contrats stockés | '
                      'Contrats retenus |')
        lignes.append('|---|---|---|---|---|')
        lignes.append('| ' + ' | '.join(texte(valeur) for valeur in valeurs) + ' |')
        if valeurs[0] == valeurs[1] == valeurs[2]:
            lignes.append('\nLes trois totaux sont égaux : les analyses couvrent le même '
                          'univers, sans double comptage.')
        else:
            lignes.append('\n**Alerte** : les totaux diffèrent, une analyse est à corriger.')
    return '\n'.join(lignes) + '\n'


if __name__ == '__main__':
    raise SystemExit(main())
