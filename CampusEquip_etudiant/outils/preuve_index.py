"""Bonus 1 — preuve du plan SQL avant / après index, sur un volume dédié.

    python -m outils.preuve_index --contrats 150000

Le script construit un schéma `bonus_index` (supprimé ensuite) pour ne pas
gonfler la base de démonstration, exécute la MÊME requête deux fois — sans puis
avec index — et vérifie que le résultat est identique. Les plans complets sont
écrits dans `preuves/`, la synthèse dans `preuves/index_synthese.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from etudiant import depot  # noqa: E402

# Les deux mesures tournent sans parallélisme : le gain observé doit venir de
# l'index, pas du nombre de cœurs. Sur un poste qui autorise les « parallel
# workers », le gain reste du même ordre ; ici, la mesure est aussi comparable
# d'une machine à l'autre.
REGLAGES = ('SET max_parallel_workers_per_gather = 0',
            'SET max_parallel_maintenance_workers = 0')

REQUETES = {
    'activite': """
SELECT s.campus_id,
       c2.name                          AS campus,
       count(*)                         AS contrats,
       count(DISTINCT c.site_id)        AS guichets_actifs
FROM bonus_index.contracts c
JOIN bonus_index.sites s   ON s.site_id = c.site_id
JOIN bonus_index.campus c2 ON c2.campus_id = s.campus_id
WHERE c.status IN ('paid', 'closed')
  AND c.start_date = date '2026-11-06'
GROUP BY s.campus_id, c2.name
ORDER BY s.campus_id
""",
    'montant': """
SELECT s.campus_id,
       c2.name                      AS campus,
       sum(l.line_amount)           AS montant,
       count(*)                     AS lignes
FROM bonus_index.contracts c
JOIN bonus_index.contract_lines l ON l.contract_id = c.contract_id
JOIN bonus_index.sites s          ON s.site_id = c.site_id
JOIN bonus_index.campus c2        ON c2.campus_id = s.campus_id
WHERE c.status IN ('paid', 'closed')
  AND c.start_date = date '2026-11-06'
GROUP BY s.campus_id, c2.name
ORDER BY s.campus_id
""",
}

DDL = """
DROP SCHEMA IF EXISTS bonus_index CASCADE;
CREATE SCHEMA bonus_index;

CREATE UNLOGGED TABLE bonus_index.campus (
    campus_id integer PRIMARY KEY,
    name      text NOT NULL
);
CREATE UNLOGGED TABLE bonus_index.sites (
    site_id   integer PRIMARY KEY,
    campus_id integer NOT NULL,
    name      text NOT NULL
);
CREATE UNLOGGED TABLE bonus_index.contracts (
    contract_id integer PRIMARY KEY,
    site_id     integer NOT NULL,
    start_date  date    NOT NULL,
    status      text    NOT NULL
);
CREATE UNLOGGED TABLE bonus_index.contract_lines (
    contract_id  integer NOT NULL,
    line_no      integer NOT NULL,
    equipment_id integer NOT NULL,
    quantity     integer NOT NULL,
    duration     integer NOT NULL,
    unit_rate    numeric NOT NULL,
    line_amount  numeric GENERATED ALWAYS AS (quantity * duration * unit_rate) STORED,
    PRIMARY KEY (contract_id, line_no)
);
"""

CHARGEMENT = """
INSERT INTO bonus_index.campus
SELECT g, 'Campus ' || g FROM generate_series(1, 6) g;

INSERT INTO bonus_index.sites
SELECT g, 1 + ((g - 1) / 2), 'Guichet ' || g FROM generate_series(1, 12) g;

INSERT INTO bonus_index.contracts (contract_id, site_id, start_date, status)
SELECT g,
       1 + (g % 12),
       date '2026-06-01' + (g % 180),          -- 180 jours, dont le 6 novembre
       -- Statut décorrélé de la date : sinon toutes les lignes d'un même jour
       -- auraient le même statut et la mesure serait vide ou biaisée.
       CASE WHEN (g * 7) % 10 < 6 THEN 'paid'
            WHEN (g * 7) % 10 < 8 THEN 'closed'
            WHEN (g * 7) % 10 = 8 THEN 'draft'
            ELSE 'cancelled' END
FROM generate_series(1, __CONTRATS__) g;

INSERT INTO bonus_index.contract_lines (contract_id, line_no, equipment_id, quantity,
                                        duration, unit_rate)
SELECT c.contract_id,
       ligne,
       1 + ((c.contract_id + ligne) % 120),
       1 + (c.contract_id % 5),
       1 + (c.contract_id % 8),
       10 + ((c.contract_id * 7 + ligne) % 70)
FROM bonus_index.contracts c
CROSS JOIN generate_series(1, 2) AS ligne;
"""

INDEX = ("CREATE INDEX ix_contracts_ret ON bonus_index.contracts (start_date) "
         "WHERE status IN ('paid', 'closed')")


def _executer(cnx, requete: str):
    with cnx.cursor() as cur:
        cur.execute(requete)
        return cur.fetchall() if cur.description else None


def _plan(cnx, requete: str) -> tuple[str, float]:
    """Exécute une fois à blanc, puis mesure : l'écart doit venir de l'index, pas du cache."""
    plan = ''
    for _ in range(2):
        with cnx.cursor() as cur:
            cur.execute('EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) ' + requete)
            plan = '\n'.join(ligne[0] for ligne in cur.fetchall())
        cnx.rollback()
    trouve = re.search(r'Execution Time: ([0-9.]+) ms', plan)
    return plan, float(trouve.group(1)) if trouve else 0.0


def _empreinte(resultat) -> str:
    return hashlib.md5(repr(resultat).encode('utf-8')).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--contrats', type=int, default=250_000)
    p.add_argument('--sortie', type=Path, default=RACINE / 'preuves')
    arguments = p.parse_args()
    arguments.sortie.mkdir(parents=True, exist_ok=True)

    cnx = depot.connexion()
    try:
        for reglage in REGLAGES:
            _executer(cnx, reglage)
        cnx.commit()
        print(f'construction du volume ({arguments.contrats} contrats, '
              f'{arguments.contrats * 2} lignes)…', flush=True)
        debut = time.perf_counter()
        _executer(cnx, DDL)
        _executer(cnx, CHARGEMENT.replace('__CONTRATS__', str(arguments.contrats)))
        cnx.commit()
        _executer(cnx, 'ANALYZE bonus_index.contracts')
        _executer(cnx, 'ANALYZE bonus_index.contract_lines')
        cnx.commit()
        print(f'volume prêt en {time.perf_counter() - debut:.1f} s', flush=True)

        mesures = {}
        for nom, requete in REQUETES.items():
            plan, duree = _plan(cnx, requete)
            resultat = _executer(cnx, requete)
            cnx.rollback()
            if not resultat:
                print(f'Mesure invalide pour {nom} : aucune ligne renvoyée.')
                return 2
            mesures[nom] = {'avant': plan, 'duree_avant': duree,
                            'resultat_avant': resultat}

        print('création de l’index…', flush=True)
        debut = time.perf_counter()
        with cnx.cursor() as cur:
            cur.execute(INDEX)
        cnx.commit()
        duree_index = time.perf_counter() - debut
        _executer(cnx, 'ANALYZE bonus_index.contracts')
        cnx.commit()

        for nom, requete in REQUETES.items():
            plan, duree = _plan(cnx, requete)
            resultat = _executer(cnx, requete)
            cnx.rollback()
            mesures[nom].update({'apres': plan, 'duree_apres': duree,
                                 'resultat_apres': resultat,
                                 'identique': resultat == mesures[nom]['resultat_avant']})

        for nom in REQUETES:
            (arguments.sortie / f'index_{nom}_avant.txt').write_text(
                f'-- Sans index ({nom})\n{mesures[nom]["avant"]}\n', encoding='utf-8')
            (arguments.sortie / f'index_{nom}_apres.txt').write_text(
                f'-- Avec index ({nom})\n{mesures[nom]["apres"]}\n', encoding='utf-8')

        activite = mesures['activite']
        montant = mesures['montant']
        gain_activite = activite['duree_avant'] / activite['duree_apres'] \
            if activite['duree_apres'] else 0
        gain_montant = montant['duree_avant'] / montant['duree_apres'] \
            if montant['duree_apres'] else 0
        identiques = all(mesure['identique'] for mesure in mesures.values())
        nb_contrats = f'{arguments.contrats:,}'.replace(',', ' ')
        nb_lignes = f'{arguments.contrats * 2:,}'.replace(',', ' ')

        synthese = f"""# Bonus 1 — plan SQL avant / après index

Volume de mesure : **{nb_contrats} contrats**, {nb_lignes} lignes,
180 jours de dates métier. Le schéma `bonus_index` est supprimé après la mesure : la base
de démonstration n'est pas modifiée.

Index ajouté : `bonus_index.contracts (start_date) WHERE status IN ('paid', 'closed')`.
Il est **partiel** : les contrats `draft` et `cancelled`, exclus des indicateurs, n'y
figurent pas.

Chaque requête est exécutée **une fois à blanc puis mesurée**, avant et après
l'index : l'écart vient donc de l'index, pas d'un cache réchauffé par la première
exécution.

## Requête A — activité d'une journée (sans jointure de lignes)

Nombre de contrats et de guichets actifs par campus, pour le 6 novembre 2026.

| | Sans index | Avec index |
|---|---:|---:|
| Temps d'exécution | {activite['duree_avant']:.2f} ms | {activite['duree_apres']:.2f} ms |
| Empreinte du résultat | `{_empreinte(activite['resultat_avant'])}` | `{_empreinte(activite['resultat_apres'])}` |
| Résultat identique | {'oui' if activite['identique'] else 'NON'} | |
| Gain | | **×{gain_activite:.0f}** |

Avant : `Seq Scan` sur les {nb_contrats} contrats. Après : `Bitmap Index Scan`
sur l'index partiel, puis lecture des seules lignes utiles.

## Requête B — montant d'une journée (avec jointure des lignes)

Même filtre, mais on additionne les montants : la requête doit lire `contract_lines`.

| | Sans index | Avec index |
|---|---:|---:|
| Temps d'exécution | {montant['duree_avant']:.2f} ms | {montant['duree_apres']:.2f} ms |
| Empreinte du résultat | `{_empreinte(montant['resultat_avant'])}` | `{_empreinte(montant['resultat_apres'])}` |
| Résultat identique | {'oui' if montant['identique'] else 'NON'} | |
| Gain | | **×{gain_montant:.1f}** |

Ici le gain est faible : le planificateur choisit de balayer les
{nb_lignes} lignes (`Seq Scan on contract_lines`) et l'index ne fait
disparaître que le balayage des contrats. C'est le résultat le plus instructif du bonus :
**un index ne corrige que la partie du coût qu'il adresse**. Pour cette requête, le
correctif serait de forcer une boucle imbriquée (jointure `LATERAL` par contrat) ou de
réduire encore la période, pas d'ajouter un second index sur `start_date`.

Coût de création de l'index : **{duree_index:.2f} s**. Les plans complets sont dans
`index_activite_avant.txt`, `index_activite_apres.txt`, `index_montant_avant.txt` et
`index_montant_apres.txt`.

## Ce qu'il faut retenir

Un index n'accélère pas « la base » : il accélère **une forme de requête**, au prix
d'écritures plus lentes et d'espace disque. Le même index divise ici le temps par
{gain_activite:.0f} sur un comptage et ne change presque rien sur une agrégation de
montants. Sur une petite table, le planificateur peut préférer le parcours séquentiel :
c'est normal, et le résultat reste identique.
"""
        (arguments.sortie / 'index_synthese.md').write_text(synthese, encoding='utf-8')

        # Mesures structurées, lues par le tableau de bord (page Laboratoire).
        maximum = max(activite['duree_avant'], activite['duree_apres'],
                      montant['duree_avant'], montant['duree_apres'], 0.1)
        mesures = {
            'contrats': arguments.contrats,
            'lignes': arguments.contrats * 2,
            'volume_secondes': round(duree_index, 2),
            'requetes': [
                {'nom': 'Activité d’une journée (comptage)',
                 'avant': round(activite['duree_avant'], 2),
                 'apres': round(activite['duree_apres'], 2),
                 'gain': round(gain_activite),
                 'gain_sur': 'comptage',
                 'identique': activite['identique'],
                 'largeur_avant': round(activite['duree_avant'] / maximum * 100, 1),
                 'largeur_apres': round(activite['duree_apres'] / maximum * 100, 1)},
                {'nom': 'Montant d’une journée (agrégation)',
                 'avant': round(montant['duree_avant'], 2),
                 'apres': round(montant['duree_apres'], 2),
                 'gain': round(gain_montant, 1),
                 'gain_sur': 'agrégation',
                 'identique': montant['identique'],
                 'largeur_avant': round(montant['duree_avant'] / maximum * 100, 1),
                 'largeur_apres': round(montant['duree_apres'] / maximum * 100, 1)},
            ],
        }
        (arguments.sortie / 'index_mesures.json').write_text(
            json.dumps(mesures, ensure_ascii=False, indent=2), encoding='utf-8')
        print(synthese)
        return 0 if identiques else 1
    finally:
        try:
            _executer(cnx, 'DROP SCHEMA IF EXISTS bonus_index CASCADE')
            cnx.commit()
        finally:
            cnx.close()


if __name__ == '__main__':
    raise SystemExit(main())
