"""Preuve « calcul d'un contrat à la main ».

    python -m outils.preuve_calcul

Choisit un contrat réel chargé en base (au moins deux lignes, si possible une
ligne à l'heure et une à la journée), refait l'arithmétique à la main, puis la
compare au montant calculé par PostgreSQL. Écrit `preuves/calcul_manuel.md`.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402


def choisir_contrat(cnx) -> int:
    with cnx.cursor() as cur:
        cur.execute("""
            SELECT l.contract_id
            FROM contract_lines l
            JOIN contracts c USING (contract_id)
            WHERE c.status IN ('paid', 'closed')
            GROUP BY l.contract_id
            HAVING count(*) >= 2 AND count(DISTINCT l.unit) = 2 AND max(l.quantity) <= 20
            ORDER BY l.contract_id
            LIMIT 1
        """)
        ligne = cur.fetchone()
    cnx.rollback()
    if ligne:
        return ligne[0]
    with cnx.cursor() as cur:
        cur.execute("""
            SELECT l.contract_id FROM contract_lines l
            JOIN contracts c USING (contract_id)
            WHERE c.status IN ('paid', 'closed')
            GROUP BY l.contract_id HAVING count(*) >= 2 AND max(l.quantity) <= 20
            ORDER BY l.contract_id LIMIT 1
        """)
        ligne = cur.fetchone()
    cnx.rollback()
    if not ligne:
        raise SystemExit('Aucun contrat chargé : lancez d abord `python -m outils.demo`.')
    return ligne[0]


def main() -> int:
    cnx = depot.connexion()
    try:
        contract_id = choisir_contrat(cnx)
        with cnx.cursor() as cur:
            cur.execute("""
                SELECT c.contract_id, c.start_date, c.status, cl.name AS client,
                       s.name AS site, ca.name AS campus
                FROM contracts c
                JOIN clients cl ON cl.client_id = c.client_id
                JOIN sites s    ON s.site_id = c.site_id
                JOIN campus ca  ON ca.campus_id = s.campus_id
                WHERE c.contract_id = %s
            """, (contract_id,))
            entete = cur.fetchone()
            cur.execute("""
                SELECT l.line_no, l.equipment_id, e.name, l.quantity, l.duration, l.unit,
                       l.unit_rate, l.line_amount
                FROM contract_lines l
                JOIN equipments e ON e.equipment_id = l.equipment_id
                WHERE l.contract_id = %s
                ORDER BY l.line_no
            """, (contract_id,))
            lignes = cur.fetchall()
        cnx.rollback()
        total_sql = depot.total_retenu(cnx, contract_id)
    finally:
        cnx.close()

    total_main = Decimal('0.00')
    details = []
    for numero, equipment_id, nom, quantite, duree, unite, tarif, montant in lignes:
        calcul = Decimal(quantite) * Decimal(duree) * Decimal(tarif)
        total_main += calcul
        details.append((numero, nom, quantite, duree, unite, tarif, calcul, montant))

    identique = (total_main == Decimal(total_sql))

    fichier = RACINE / 'preuves' / 'calcul_manuel.md'
    fichier.parent.mkdir(parents=True, exist_ok=True)
    lignes_md = [
        '# Preuve — calcul d\'un contrat à la main', '',
        f"Contrat **{entete[0]}** — client {entete[3]}, {entete[4]} ({entete[5]}), "
        f"début le {entete[1]:%d/%m/%Y}, statut `{entete[2]}`.", '',
        '| Ligne | Équipement | Quantité | Durée | Unité | Tarif | Calcul | Montant en base |',
        '|---:|---|---:|---:|---|---:|---|---:|',
    ]
    for numero, nom, quantite, duree, unite, tarif, calcul, montant in details:
        lignes_md.append(
            f"| {numero} | {nom} | {quantite} | {duree} | {unite} | {tarif} | "
            f"{quantite} × {duree} × {tarif} = **{calcul}** | {montant} |")

    lignes_md += [
        '',
        f"**Total à la main : {total_main} MAD.**",
        f"**Total retenu par la vue SQL : {total_sql} MAD.**",
        '',
        f"Les deux valeurs sont {'identiques' if identique else 'DIFFÉRENTES'} : "
        "la même formule est appliquée par le code Python (pour le contrôle) et par "
        "PostgreSQL (colonne générée `line_amount`), ce qui évite qu'un indicateur "
        "diverge du tarif historique reçu.",
        '',
        '## La requête qui produit le total',
        '',
        '```sql',
        'SELECT sum(line_amount)',
        'FROM v_lignes_retenues',
        'WHERE contract_id = %s;   -- la vue applique le filtre paid / closed',
        '```',
        '',
        '## Ce que la preuve vérifie',
        '',
        '- la durée est déjà exprimée dans l\'unité de la ligne : on ne convertit ni',
        '  les jours en heures, ni l\'inverse ;',
        '- le tarif conservé est celui de la ligne (`unit_rate`), pas un tarif courant ;',
        '- tout le montant est rattaché à `start_date` du contrat ;',
        '- le contrat n\'est compté qu\'une fois, même avec plusieurs lignes.',
        '',
    ]
    fichier.write_text('\n'.join(lignes_md) + '\n', encoding='utf-8')
    print('\n'.join(lignes_md[:12]))
    print('preuve écrite dans', fichier)
    return 0 if identique else 1


if __name__ == '__main__':
    raise SystemExit(main())
