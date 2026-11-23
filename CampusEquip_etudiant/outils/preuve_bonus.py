"""Exécute les requêtes bonus (catégories récursives, précalcul) et garde les preuves.

    python -m outils.preuve_bonus

Écrit `preuves/bonus_sql.md` : un tableau par requête, le temps d'exécution et la
preuve d'égalité entre le calcul à la demande et la vue matérialisée.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402
from outils.analyses import decouper, executer, texte  # noqa: E402

FICHIERS = (RACINE / 'bonus' / '02_categories_recursives.sql',
            RACINE / 'bonus' / '03_precalcul.sql')


def tableau(colonnes: list[str], lignes: list[tuple], maximum: int = 20) -> list[str]:
    sortie = ['| ' + ' | '.join(colonnes) + ' |',
              '|' + '|'.join('---' for _ in colonnes) + '|']
    for ligne in lignes[:maximum]:
        sortie.append('| ' + ' | '.join(texte(valeur) for valeur in ligne) + ' |')
    if len(lignes) > maximum:
        sortie.append(f'| … ({len(lignes) - maximum} lignes de plus) |' +
                      ' |' * (len(colonnes) - 1))
    return sortie


def main() -> int:
    sortie = RACINE / 'preuves'
    sortie.mkdir(parents=True, exist_ok=True)
    cnx = depot.connexion()
    lignes_md = ['# Bonus 2 — catégories récursives et précalcul', '',
                 'Toutes les requêtes sont exécutées sur la base de démonstration, '
                 'après rafraîchissement de la vue matérialisée.', '']
    try:
        with cnx.cursor() as cur:
            cur.execute('REFRESH MATERIALIZED VIEW mv_montant_jour_campus')
        cnx.commit()

        for fichier in FICHIERS:
            lignes_md += [f'## `{fichier.name}`', '']
            for nom, requete in decouper(fichier):
                debut = time.perf_counter()
                colonnes, resultat = executer(cnx, requete)
                duree = (time.perf_counter() - debut) * 1000
                cnx.rollback()
                lignes_md += [f'### {nom} — {len(resultat)} ligne(s) en {duree:.1f} ms', '']
                lignes_md += tableau(colonnes, resultat)
                lignes_md.append('')

        # Preuve d'égalité : l'écart doit être vide.
        colonnes, ecarts = executer(cnx, decouper(FICHIERS[1])[0][1])
        cnx.rollback()
        total_precalcule, total_demande, cellules = executer(
            cnx, decouper(FICHIERS[1])[1][1])[1][0]
        cnx.rollback()
        lignes_md += [
            '## Preuve d\'égalité', '',
            f"- Cellules précalculées : **{cellules}**",
            f"- Total précalculé : **{total_precalcule} MAD**",
            f"- Total recalculé à la demande : **{total_demande} MAD**",
            f"- Écarts détectés : **{len(ecarts)}**",
            '',
            ('Les deux chemins donnent le même résultat. Le précalcul sert à '
             'afficher vite ; le calcul à la demande sert à vérifier.'
             if not ecarts and total_precalcule == total_demande else
             '**Écart détecté** : la vue matérialisée doit être rafraîchie.'),
            '',
        ]
        (sortie / 'bonus_sql.md').write_text('\n'.join(lignes_md) + '\n', encoding='utf-8')
        print('\n'.join(lignes_md[-8:]))
        print('preuves écrites dans', sortie / 'bonus_sql.md')
        return 0 if not ecarts and total_precalcule == total_demande else 1
    finally:
        cnx.close()


if __name__ == '__main__':
    raise SystemExit(main())
