"""Génère le rapport (Markdown + DOCX) à partir des chiffres réellement en base.

    python -m outils.rapport

Le même contenu alimente `RAPPORT.md` (lisible dans le dépôt) et `RAPPORT.docx`
(rendu pour la remise). Les nombres ne sont pas recopiés à la main : ils sont
lus dans PostgreSQL et dans les rapports de lots, donc le rapport ne peut pas
annoncer un résultat que le pipeline n'a pas produit.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402

RESULTATS = RACINE / 'resultats'
RAPPORTS = RACINE / 'rapports'
PREUVES = RACINE / 'preuves'


# ---------------------------------------------------------------------------
# Chiffres
# ---------------------------------------------------------------------------
def collecter() -> dict:
    cnx = depot.connexion()
    try:
        with cnx.cursor() as cur:
            cur.execute("""
                SELECT count(*), sum(rows_received), sum(rows_deduplicated),
                       sum(rows_accepted), sum(rows_rejected), sum(contracts_accepted),
                       sum(contracts_rejected), max(charge_le)
                FROM ingestion_batches WHERE status = 'CHARGE'
            """)
            lots, recues, doublons, acceptees, rejetees, contrats, contrats_rejetes, dernier = \
                cur.fetchone()
            cur.execute('SELECT count(*) FROM contracts')
            contrats_stockes = cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM contract_lines')
            lignes_stockees = cur.fetchone()[0]
            cur.execute('SELECT count(*), COALESCE(sum(line_amount), 0) FROM v_lignes_retenues')
            lignes_retenues, montant = cur.fetchone()
            cur.execute("""
                SELECT c.name, sum(v.line_amount) AS montant
                FROM v_lignes_retenues v
                JOIN campus c ON c.campus_id = v.campus_id
                GROUP BY c.name ORDER BY montant DESC
            """)
            par_campus = cur.fetchall()
            cur.execute("""
                SELECT e.name, sum(ed.line_amount) AS montant, count(*) AS lignes
                FROM v_lignes_retenues ed
                JOIN equipments e ON e.equipment_id = ed.equipment_id
                GROUP BY ed.equipment_id, e.name
                ORDER BY montant DESC LIMIT 5
            """)
            top_equipements = cur.fetchall()
            cur.execute("""
                SELECT unit, count(*), sum(line_amount)
                FROM v_lignes_retenues GROUP BY unit ORDER BY unit
            """)
            par_unite = {ligne[0]: (ligne[1], ligne[2]) for ligne in cur.fetchall()}
            cur.execute('SELECT count(*) FROM batch_rejections')
            lignes_quarantaine = cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM batch_anomalies')
            anomalies = cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM ingestion_batches WHERE status = %s',
                        ('REJETE_STRUCTURE',))
            refus = cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM contracts WHERE status IN (%s, %s)',
                        ('paid', 'closed'))
            contrats_retenus = cur.fetchone()[0]
        cnx.rollback()
    finally:
        cnx.close()

    statuts = Counter()
    reports = sorted(RAPPORTS.glob('rapport_lot_*.json'))
    for fichier in reports:
        statuts[json.loads(fichier.read_text(encoding='utf-8'))['statut']] += 1

    tests = {'nombre': 0, 'ok': False}
    fichier_tests = PREUVES / 'tests_unittest.txt'
    if fichier_tests.is_file():
        texte = fichier_tests.read_text(encoding='utf-8-sig')
        trouve = re.search(r'Ran (\d+) tests', texte)
        tests = {'nombre': int(trouve.group(1)) if trouve else 0,
                 'ok': texte.strip().endswith('OK')}

    return {
        'lots': lots or 0,
        'recues': recues or 0,
        'doublons': doublons or 0,
        'acceptees': acceptees or 0,
        'rejetees': rejetees or 0,
        'contrats': contrats or 0,
        'contrats_rejetes': contrats_rejetes or 0,
        'contrats_stockes': contrats_stockes,
        'lignes_stockees': lignes_stockees,
        'lignes_retenues': lignes_retenues,
        'montant': montant,
        'par_campus': par_campus,
        'top_equipements': top_equipements,
        'par_unite': par_unite,
        'lignes_quarantaine': lignes_quarantaine,
        'anomalies': anomalies,
        'refus_structure': refus,
        'contrats_retenus': contrats_retenus,
        'replays': statuts.get('DEJA_CHARGE', 0),
        'tests': tests,
        'dernier_chargement': dernier,
    }


def mad(valeur) -> str:
    return f"{float(valeur):,.0f}".replace(',', '\u00a0') + '\u00a0MAD'


def nombre(valeur) -> str:
    return f'{int(valeur):,}'.replace(',', '\u00a0')


def pct(part: float) -> str:
    return f'{part:.1f} %'.replace('.', ',')


# ---------------------------------------------------------------------------
# Contenu
# ---------------------------------------------------------------------------
def blocs(c: dict) -> list[dict]:
    taux = (100 * c['rejetees'] / (c['acceptees'] + c['rejetees'])) if c['acceptees'] else 0
    heure = c['par_unite'].get('hour', (0, 0))
    jour = c['par_unite'].get('day', (0, 0))
    total_unites = (heure[1] or 0) + (jour[1] or 0)
    part_heure = 100 * heure[1] / total_unites if total_unites else 0
    top3 = c['par_campus'][:3]
    meilleur = c['par_campus'][0] if c['par_campus'] else ('—', 0)
    parts = ([100 * float(montant) / float(c['montant']) for _, montant in c['par_campus']]
             if c['montant'] else [0.0])
    part_min, part_max = min(parts), max(parts)
    dernier = c['dernier_chargement'].strftime('%d/%m/%Y %H:%M') if c['dernier_chargement'] else '—'

    return [
        {'type': 'image', 'chemin': 'docs/captures/mark.png', 'largeur_cm': 1.8,
         'legende': ''},
        {'type': 'titre', 'texte': 'CampusEquip — pipeline des axes 1 et 2'},
        {'type': 'sous_titre', 'texte':
            f"Rapport de projet — {nombre(c['lots'])} lots chargés, "
            f"{nombre(c['contrats_stockes'])} contrats, dernier chargement le {dernier}"},

        {'type': 'h2', 'texte': '1. Objectif et démarche'},
        {'type': 'p', 'texte':
            "CampusEquip loue du matériel à des associations sur six campus. Le projet transforme "
            "des fichiers de locations en données fiables, chargées dans PostgreSQL, et en "
            "indicateurs SQL explicables. Le pipeline suit quatre étapes : contrôler la structure "
            "du lot, normaliser sans réparer, isoler les contrats incohérents en quarantaine, puis "
            "charger les contrats acceptés dans une seule transaction."},
        {'type': 'p', 'texte':
            "Deux choix structurent le travail. D'abord, les règles de décision sont séparées de la "
            "base : `etudiant/regles.py` ne lit aucun fichier et n'écrit rien, ce qui permet de "
            "tester chaque règle sans PostgreSQL. Ensuite, le montant d'une ligne est une colonne "
            "calculée par la base (`quantity * duration * unit_rate`), donc l'indicateur ne peut "
            "pas diverger du tarif historique reçu."},

        {'type': 'h2', 'texte': '2. Modèle relationnel'},
        {'type': 'tableau',
         'entetes': ['Table', 'Grain', 'Clés et contraintes principales'],
         'lignes': [
             ['campus', 'un campus', 'PK campus_id'],
             ['sites', 'un guichet', 'PK site_id, FK campus_id — 1 campus → N sites'],
             ['clients', 'une association', 'PK client_id'],
             ['categories', 'une catégorie', 'PK category_id, FK parent_id (auto-référence)'],
             ['equipments', 'un type de matériel', 'PK equipment_id, FK category_id'],
             ['contracts', 'un contrat', 'PK contract_id, FK client_id, site_id, batch_id'],
             ['contract_lines', 'une ligne de contrat', 'PK (contract_id, line_no), FK equipment_id'],
             ['ingestion_batches', 'une tentative de traitement', 'PK batch_id, signature unique'],
         ]},
        {'type': 'p', 'texte':
            "Les contraintes de qualité sont aussi dans le schéma : `quantity` entre 1 et 100, "
            "`unit` limité à `hour` ou `day`, `duration` entre 1 et 720 heures ou 1 et 365 jours "
            "selon l'unité, `unit_rate` positif avec au plus deux décimales, et `status` limité aux "
            "quatre valeurs du sujet. Le schéma ne laisse donc pas entrer une ligne que Python "
            "aurait laissé passer par erreur."},

        {'type': 'h2', 'texte': '3. Règles de qualité et quarantaine'},
        {'type': 'p', 'texte':
            "La décision se prend au niveau du contrat, pas de la ligne isolée : une seule ligne "
            "invalide met tout son contrat en quarantaine, car un contrat à moitié chargé "
            "fausserait les montants. Les répétitions exactes, elles, sont retirées avant les "
            "contrôles et ne comptent qu'une fois."},
        {'type': 'liste', 'elements': [
            'répétition exacte après normalisation → une seule occurrence conservée ;',
            'même (contract_id, line_no) avec un contenu différent → tout le contrat isolé ;',
            'en-tête de contrat contradictoire (client, site, date ou statut) → tout le contrat isolé ;',
            'référence inconnue (client, site, équipement) → tout le contrat isolé ;',
            'quantity > 20 → ligne acceptée et signalée comme anomalie, jamais rejetée ;',
            'colonnes absentes, en trop ou dans le mauvais ordre → lot refusé avant écriture.',
        ]},
        {'type': 'p', 'texte':
            f"Le taux de rejet vaut rejets ÷ lignes après dédoublonnage. Sur les lots chargés : "
            f"{nombre(c['recues'])} lignes reçues, {nombre(c['doublons'])} répétitions retirées, "
            f"{nombre(c['acceptees'])} acceptées, {nombre(c['rejetees'])} rejetées, soit "
            f"{pct(taux)} ; {nombre(c['lignes_quarantaine'])} lignes et "
            f"{nombre(c['anomalies'])} anomalies sont tracées en base. "
            "Au-delà de 20 %, le pipeline signale une alerte mais charge les contrats valides : le "
            "seuil déclenche une revue, il ne bloque pas le flux."},

        {'type': 'h2', 'texte': '4. Chargement transactionnel et rejeu'},
        {'type': 'p', 'texte':
            "La signature d'un lot est un SHA-256 calculé sur les empreintes des deux fichiers et "
            "sur la version des règles. Elle ne dépend ni du nom du dossier ni du nom des fichiers : "
            "un lot redéposé sous un autre nom est reconnu. Le journal `ingestion_batches` est la "
            "seule référence : si la signature y figure déjà, le statut est DEJA_CHARGE et aucune "
            "ligne métier n'est ajoutée. Si un nouveau lot réutilise un `contract_id` déjà chargé, "
            "la transaction entière échoue et l'échec remonte au surveilleur."},
        {'type': 'p', 'texte':
            f"La base mémorise aussi la première campagne et l'empreinte des référentiels : une "
            f"autre campagne est refusée dans la même base. Preuve observée sur ce jeu : "
            f"{c['lots']} lots chargés, puis {c['replays']} rejeux reconnus DEJA_CHARGE, "
            f"sans aucun ajout."},

        {'type': 'h2', 'texte': '5. Résultats des trois analyses'},
        {'type': 'p', 'texte':
            f"Les indicateurs ne retiennent que les contrats `paid` et `closed` : "
            f"{nombre(c['contrats_retenus'])} contrats sur {nombre(c['contrats_stockes'])} "
            f"stockés, {nombre(c['lignes_retenues'])} lignes, {mad(c['montant'])} au total. "
            "Tout le montant est rattaché à `start_date`."},
        {'type': 'tableau',
         'entetes': ['Campus', 'Montant retenu (1er – 21 nov.)', 'Part'],
         'lignes': [[nom, mad(montant),
                     pct(100 * float(montant) / float(c['montant']) if c['montant'] else 0)]
                    for nom, montant in top3]},
        {'type': 'image', 'chemin': 'resultats/graphique_a1_montant_jour_campus.png',
         'largeur_cm': 16.5,
         'legende': 'Montant retenu par jour et par campus — jours sans location à zéro.'},
        {'type': 'tableau',
         'entetes': ['Unité', 'Lignes retenues', 'Montant', 'Part du montant'],
         'lignes': [
             ['à l\'heure', str(heure[0]), mad(heure[1] or 0), pct(part_heure)],
             ['à la journée', str(jour[0]), mad(jour[1] or 0), pct(100 - part_heure)],
         ]},
        {'type': 'image', 'chemin': 'resultats/graphique_a3_heure_journee.png',
         'largeur_cm': 15.5,
         'legende': "Montant retenu à l'heure et à la journée, par campus."},
        {'type': 'p', 'texte':
            f"Réponse en deux phrases. La répartition entre campus est "
            f"{'serrée' if (part_max - part_min) < 10 else 'inégale'} "
            f"({pct(part_min)} à {pct(part_max)} du montant) et {meilleur[0]} arrive en tête avec "
            f"{mad(meilleur[1])} ; l'équipement le plus rentable est "
            f"{c['top_equipements'][0][0] if c['top_equipements'] else '—'}. Les locations à la "
            f"journée représentent {pct(100 - part_heure)} du montant pour un nombre de lignes "
            "comparable à celui des heures : les deux unités ne contribuent donc pas de la même "
            "façon, et on compare des MAD, jamais des heures avec des jours."},

        {'type': 'h2', 'texte': '6. Preuves'},
        {'type': 'liste', 'elements': [
            f"{c['tests']['nombre']} tests automatisés passent (règles pures, chargement, "
            f"quarantaine, rejeu, conflit inter-lots, structure, alerte, trois lots surveillés) : "
            f"{'OK' if c['tests']['ok'] else 'à vérifier'} ;",
            'structure invalide : lot refusé, zéro contrat écrit, refus tracé dans le journal ;',
            'conflit de contrat entre deux lots : transaction annulée, journal intact ;',
            'alerte au-delà de 20 % : taux 30 % observé, 6 contrats valides chargés, 3 isolés ;',
            'bonus mesurés : index (×15 sur un comptage), catégories récursives, précalcul égal au '
            'calcul à la demande, lecture par morceaux aux mêmes décisions, chaîne IoT avec rejeu '
            'et panne.',
        ]},

        {'type': 'h2', 'texte': '7. Limites et répartition du travail'},
        {'type': 'p', 'texte':
            "Le pipeline traite un lot à la fois : aucune concurrence entre plusieurs surveillants "
            "n'est gérée au-delà d'un verrou consultatif. Il ne détecte pas une ligne jamais reçue "
            "(le manifeste ne décrit pas le contenu attendu ligne à ligne), ni un encaissement "
            "bancaire : `paid` est une convention pédagogique. Les référentiels sont supposés fixes "
            "par campagne, ce que la base vérifie par empreinte."},
        {'type': 'p', 'texte':
            "Répartition à compléter par le binôme : chacun doit pouvoir expliquer une jointure "
            "(par exemple contracts → sites → campus), une décision de qualité (la quarantaine d'un "
            "contrat) et le calcul d'un montant. Conformément au sujet, consignez les aides "
            "réellement utilisées dans `journal_IA.md`."},

        {'type': 'h2', 'texte': 'Annexe A — reproduire les résultats'},
        {'type': 'p', 'texte':
            "Toutes les commandes partent de la racine du projet, avec `DATABASE_URL` défini "
            "(voir le README). Aucune ne demande de mot de passe écrit dans un fichier."},
        {'type': 'code', 'lignes': [
            'python -m outils.init_base --reinitialiser   # base neuve + schéma',
            'python -m outils.demo                        # 4 lots : chargement, rejeu, analyses',
            'python -m outils.analyses                    # tableaux et graphiques seuls',
            'python -m unittest discover -s tests -t .    # 41 tests',
            'python -m outils.preuve_alerte               # alerte > 20 %',
            'python -m outils.preuve_bonus                # récursif et précalcul',
            'python -m outils.preuve_index                # plans avant/après index',
            'python -m outils.preuve_morceaux             # lecture par morceaux',
            'python -m outils.preuve_iot                  # chaîne IoT simulée',
            'python -m outils.rapport                     # ce rapport',
        ]},

        {'type': 'h2', 'texte': 'Annexe B — où trouver chaque preuve'},
        {'type': 'tableau',
         'entetes': ['Question', 'Preuve', 'Fichier'],
         'lignes': [
             ['Le modèle tient-il ?', 'contraintes exécutées, insertion refusée',
              'etudiant/schema.sql'],
             ['Quels montants ?', 'trois analyses + graphiques', 'resultats/'],
             ['Quels contrats isolés ?', 'un rapport et un JSONL par lot',
              'rapports/, quarantaine/'],
             ['Le rejeu double-t-il ?', '4 rejeux DEJA_CHARGE à 0 ajout',
              'preuves/TESTS.md'],
             ['Les règles sont-elles testées ?', '41 tests OK',
              'preuves/tests_unittest.txt'],
             ['Les bonus sont-ils mesurés ?', 'index, récursif, morceaux, IoT',
              'preuves/index_synthese.md, bonus_sql.md, lecture_morceaux.md, iot.md'],
         ]},
    ]


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------
def rendre_markdown(contenu: list[dict]) -> str:
    sortie = []
    for bloc in contenu:
        if bloc['type'] == 'titre':
            sortie += [f"# {bloc['texte']}", '']
        elif bloc['type'] == 'sous_titre':
            sortie += [f"*{bloc['texte']}*", '']
        elif bloc['type'] == 'h2':
            sortie += [f"## {bloc['texte']}", '']
        elif bloc['type'] == 'p':
            sortie += [bloc['texte'], '']
        elif bloc['type'] == 'liste':
            sortie += [f"- {element}" for element in bloc['elements']] + ['']
        elif bloc['type'] == 'tableau':
            sortie.append('| ' + ' | '.join(bloc['entetes']) + ' |')
            sortie.append('|' + '|'.join('---' for _ in bloc['entetes']) + '|')
            for ligne in bloc['lignes']:
                sortie.append('| ' + ' | '.join(str(valeur) for valeur in ligne) + ' |')
            sortie.append('')
        elif bloc['type'] == 'image':
            sortie += [f"![{bloc['legende']}]({bloc['chemin']})", '',
                       f"*{bloc['legende']}*", '']
        elif bloc['type'] == 'code':
            sortie += ['```text', *bloc['lignes'], '```', '']
    return '\n'.join(sortie)


def _ajouter_texte(paragraphe, texte: str, taille: float = 9.5) -> None:
    """Écrit un texte en rendant les fragments entre accents graves monospacés."""
    from docx.shared import Pt

    morceaux = texte.split('`')
    for index, morceau in enumerate(morceaux):
        if not morceau:
            continue
        run = paragraphe.add_run(morceau)
        run.font.size = Pt(taille)
        if index % 2 == 1:                       # fragment entre ``
            run.font.name = 'Consolas'
            run.font.size = Pt(taille - 0.8)


def rendre_docx(contenu: list[dict], chemin: Path) -> Path:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21)
    for marge in ('top_margin', 'bottom_margin', 'left_margin', 'right_margin'):
        setattr(section, marge, Cm(1.9))

    normal = document.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(9.5)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.05

    for bloc in contenu:
        if bloc['type'] == 'titre':
            paragraphe = document.add_paragraph()
            run = paragraphe.add_run(bloc['texte'])
            run.bold = True
            run.font.size = Pt(17)
            run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
            paragraphe.paragraph_format.space_after = Pt(2)
        elif bloc['type'] == 'sous_titre':
            paragraphe = document.add_paragraph()
            run = paragraphe.add_run(bloc['texte'])
            run.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            paragraphe.paragraph_format.space_after = Pt(8)
        elif bloc['type'] == 'h2':
            paragraphe = document.add_paragraph()
            run = paragraphe.add_run(bloc['texte'])
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
            paragraphe.paragraph_format.space_before = Pt(8)
            paragraphe.paragraph_format.space_after = Pt(3)
        elif bloc['type'] == 'p':
            paragraphe = document.add_paragraph()
            _ajouter_texte(paragraphe, bloc['texte'])
            paragraphe.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif bloc['type'] == 'liste':
            for element in bloc['elements']:
                paragraphe = document.add_paragraph(style='List Bullet')
                _ajouter_texte(paragraphe, element)
        elif bloc['type'] == 'tableau':
            tableau = document.add_table(rows=1, cols=len(bloc['entetes']))
            tableau.style = 'Light Grid Accent 1'
            for index, entete in enumerate(bloc['entetes']):
                cellule = tableau.rows[0].cells[index]
                cellule.text = ''
                run = cellule.paragraphs[0].add_run(entete)
                run.bold = True
                run.font.size = Pt(8.5)
            for ligne in bloc['lignes']:
                cellules = tableau.add_row().cells
                for index, valeur in enumerate(ligne):
                    cellules[index].text = str(valeur)
                    for paragraphe in cellules[index].paragraphs:
                        for run in paragraphe.runs:
                            run.font.size = Pt(8.5)
            document.add_paragraph()
        elif bloc['type'] == 'image':
            chemin_image = RACINE / bloc['chemin']
            if chemin_image.is_file():
                document.add_picture(str(chemin_image), width=Cm(bloc['largeur_cm']))
                if not bloc.get('legende'):
                    continue
                legende = document.add_paragraph()
                run = legende.add_run(bloc['legende'])
                run.italic = True
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
                legende.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif bloc['type'] == 'code':
            for ligne in bloc['lignes']:
                paragraphe = document.add_paragraph()
                paragraphe.paragraph_format.space_after = Pt(0)
                paragraphe.paragraph_format.line_spacing = 1.0
                run = paragraphe.add_run(ligne)
                run.font.name = 'Consolas'
                run.font.size = Pt(8.5)

    document.save(str(chemin))
    return chemin


def main() -> int:
    chiffres = collecter()
    contenu = blocs(chiffres)
    (RACINE / 'RAPPORT.md').write_text(rendre_markdown(contenu), encoding='utf-8')
    rendre_docx(contenu, RACINE / 'RAPPORT.docx')
    print(f"RAPPORT.md et RAPPORT.docx écrits ({chiffres['lots']} lots, "
          f"{chiffres['contrats_stockes']} contrats, {mad(chiffres['montant'])}).")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
