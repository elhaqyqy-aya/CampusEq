"""Accès aux données du tableau de bord.

Les requêtes analytiques sont en lecture seule : elles ne peuvent jamais
modifier une donnée métier. La session PostgreSQL est ouverte avec
`readonly=True` et les requêtes ne lisent que les vues et tables du projet. Le
banc de charge utilise des connexions distinctes vers un schéma temporaire.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass(frozen=True)
class Filtres:
    debut: date
    fin: date
    campus_id: int | None = None

    def parametres(self) -> dict:
        return {'debut': self.debut, 'fin': self.fin, 'campus': self.campus_id}


def connexion(parametres: dict) -> psycopg2.extensions.connection:
    cnx = psycopg2.connect(**parametres)
    cnx.set_session(readonly=True)          # aucune écriture possible
    return cnx


def _une(cur, requete: str, parametres: dict | None = None):
    cur.execute(requete, parametres or {})
    return cur.fetchone()


def _toutes(cur, requete: str, parametres: dict | None = None):
    cur.execute(requete, parametres or {})
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Contexte
# ---------------------------------------------------------------------------
def bornes(cur) -> tuple[date, date]:
    ligne = _une(cur, 'SELECT min(start_date), max(start_date) FROM contracts')
    if ligne and ligne['min'] and ligne['max']:
        return ligne['min'], ligne['max']
    return date(2026, 11, 1), date(2026, 11, 21)


def campus(cur) -> list[dict]:
    return _toutes(cur, 'SELECT campus_id, name FROM campus ORDER BY campus_id')


def sante(cur) -> dict:
    ligne = _une(cur, """
        SELECT current_database() AS base,
               current_setting('server_version') AS version,
               (SELECT count(*) FROM contracts) AS contrats,
               (SELECT count(*) FROM ingestion_batches WHERE status = 'CHARGE') AS lots
    """)
    return dict(ligne)


# ---------------------------------------------------------------------------
# Indicateurs
# ---------------------------------------------------------------------------
def kpis(cur, filtres: Filtres) -> dict:
    params = filtres.parametres()
    retenues = _une(cur, """
        SELECT COALESCE(sum(line_amount), 0) AS montant,
               count(*)                     AS lignes,
               count(DISTINCT contract_id)  AS contrats,
               count(DISTINCT campus_id)    AS campus_actifs
        FROM v_lignes_retenues
        WHERE start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR campus_id = %(campus)s::int)
    """, params)
    stockes = _une(cur, """
        SELECT count(DISTINCT c.contract_id) AS total,
               count(DISTINCT c.contract_id)
                   FILTER (WHERE c.status IN ('paid', 'closed')) AS retenus
        FROM contracts c
        WHERE c.start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR c.site_id IN (
                SELECT site_id FROM sites
                WHERE campus_id = %(campus)s::int))
    """, params)
    montant = Decimal(retenues['montant'])
    lignes = int(retenues['lignes'])
    return {
        'montant': montant,
        'lignes': lignes,
        'contrats': int(retenues['contrats']),
        'campus_actifs': int(retenues['campus_actifs']),
        'contrats_stockes': int(stockes['total']),
        'contrats_retenus': int(stockes['retenus']),
        'panier_moyen': (montant / lignes) if lignes else Decimal('0'),
    }


def par_jour(cur, filtres: Filtres) -> dict:
    params = filtres.parametres()
    lignes = _toutes(cur, """
        WITH jours AS (
            SELECT jour::date AS jour
            FROM generate_series(%(debut)s::date, %(fin)s::date, interval '1 day') AS jour
        ), totaux AS (
            SELECT start_date AS jour, sum(line_amount) AS montant
            FROM v_lignes_retenues
            WHERE start_date BETWEEN %(debut)s AND %(fin)s
              AND (%(campus)s::int IS NULL OR campus_id = %(campus)s::int)
            GROUP BY start_date
        )
        SELECT j.jour, COALESCE(t.montant, 0) AS montant
        FROM jours j LEFT JOIN totaux t USING (jour)
        ORDER BY j.jour
    """, params)
    return {'jours': [ligne['jour'].strftime('%d/%m') for ligne in lignes],
            'valeurs': [float(ligne['montant']) for ligne in lignes]}


def par_unite(cur, filtres: Filtres) -> dict:
    params = filtres.parametres()
    lignes = _toutes(cur, """
        SELECT unit, count(*) AS lignes, sum(line_amount) AS montant
        FROM v_lignes_retenues
        WHERE start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR campus_id = %(campus)s::int)
        GROUP BY unit
    """, params)
    donnees = {ligne['unit']: (int(ligne['lignes']), Decimal(ligne['montant'] or 0))
               for ligne in lignes}
    total = sum((valeur[1] for valeur in donnees.values()), Decimal('0'))
    return {
        'heure': donnees.get('hour', (0, Decimal('0'))),
        'jour': donnees.get('day', (0, Decimal('0'))),
        'total': total,
    }


def par_campus(cur, filtres: Filtres) -> list[dict]:
    params = filtres.parametres()
    lignes = _toutes(cur, """
        SELECT c.name                                   AS campus,
               sum(v.line_amount)                       AS montant,
               count(*)                                 AS lignes,
               count(DISTINCT v.contract_id)            AS contrats,
               round(sum(v.line_amount) / count(*), 2)  AS panier
        FROM v_lignes_retenues v
        JOIN campus c ON c.campus_id = v.campus_id
        WHERE v.start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR v.campus_id = %(campus)s::int)
        GROUP BY c.name, c.campus_id
        ORDER BY montant DESC
    """, params)
    total = sum((Decimal(ligne['montant']) for ligne in lignes), Decimal('0'))
    for ligne in lignes:
        ligne['part'] = float(Decimal(ligne['montant']) / total * 100) if total else 0.0
        ligne['montant'] = Decimal(ligne['montant'])
    return lignes


def top_equipements(cur, filtres: Filtres, limite: int = 8) -> list[dict]:
    params = filtres.parametres()
    params['limite'] = limite
    return _toutes(cur, """
        SELECT e.name                        AS equipement,
               cat.name                      AS categorie,
               sum(v.line_amount)            AS montant,
               count(*)                      AS lignes
        FROM v_lignes_retenues v
        JOIN equipments e   ON e.equipment_id = v.equipment_id
        JOIN categories cat ON cat.category_id = e.category_id
        WHERE v.start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR v.campus_id = %(campus)s::int)
        GROUP BY e.name, cat.name, e.equipment_id
        ORDER BY montant DESC
        LIMIT %(limite)s
    """, params)


# ---------------------------------------------------------------------------
# Qualité et lots
# ---------------------------------------------------------------------------
def lots(cur, limite: int = 12) -> list[dict]:
    return _toutes(cur, """
        SELECT batch_id, batch_number, campaign_id, status, rows_received, rows_accepted,
               rows_rejected, contracts_accepted, contracts_rejected, anomalies,
               rejection_rate, alerte_qualite, charge_le, recu_le, motif_rejet,
               dossier_source
        FROM ingestion_batches
        ORDER BY batch_id DESC
        LIMIT %(limite)s
    """, {'limite': limite})


def qualite(cur) -> dict:
    ligne = _une(cur, """
        SELECT count(*) FILTER (WHERE status = 'CHARGE')                       AS lots,
               count(*) FILTER (WHERE status = 'REJETE_STRUCTURE')             AS refus,
               count(*) FILTER (WHERE alerte_qualite)                          AS alertes,
               COALESCE(sum(rows_accepted), 0)                                 AS acceptees,
               COALESCE(sum(rows_rejected), 0)                                 AS rejetees,
               COALESCE(sum(rows_deduplicated), 0)                             AS doublons,
               COALESCE(sum(anomalies), 0)                                     AS anomalies,
               max(charge_le)                                                  AS dernier
        FROM ingestion_batches
    """)
    isoles = _une(cur, """
        SELECT count(*) AS n FROM (
            SELECT DISTINCT batch_id, contract_id FROM batch_rejections
        ) AS contrats
    """)
    total = int(ligne['acceptees']) + int(ligne['rejetees'])
    taux = (Decimal(int(ligne['rejetees'])) * 100 / total) if total else Decimal('0')
    return {**{cle: (int(valeur) if isinstance(valeur, int) else valeur)
               for cle, valeur in ligne.items()},
            'contrats_isoles': int(isoles['n']),
            'taux': taux.quantize(Decimal('0.01'))}


def motifs_rejet(cur, limite: int = 8) -> list[dict]:
    return _toutes(cur, """
        SELECT split_part(motifs[1], ':', 1) AS code,
               count(*)                      AS lignes
        FROM batch_rejections
        GROUP BY 1
        ORDER BY lignes DESC, code
        LIMIT %(limite)s
    """, {'limite': limite})


def rejets(cur, limite: int = 40) -> list[dict]:
    return _toutes(cur, """
        SELECT b.batch_number, r.position, r.contract_id, r.line_no, r.motifs,
               r.valeurs_brutes
        FROM batch_rejections r
        JOIN ingestion_batches b USING (batch_id)
        ORDER BY b.batch_number DESC, r.position
        LIMIT %(limite)s
    """, {'limite': limite})


def anomalies(cur, limite: int = 20) -> list[dict]:
    return _toutes(cur, """
        SELECT b.batch_number, a.position, a.contract_id, a.line_no, a.code, a.detail
        FROM batch_anomalies a
        JOIN ingestion_batches b USING (batch_id)
        ORDER BY b.batch_number DESC, a.position
        LIMIT %(limite)s
    """, {'limite': limite})


# ---------------------------------------------------------------------------
# Contrats
# ---------------------------------------------------------------------------
def contrats(cur, filtres: Filtres, limite: int = 25, recherche: str | None = None,
             statut: str | None = None) -> list[dict]:
    params = filtres.parametres()
    params.update({'limite': limite, 'recherche': recherche, 'statut': statut})
    return _toutes(cur, """
        SELECT c.contract_id, c.start_date, c.status, cl.name AS client,
               s.name AS site, ca.name AS campus,
               COALESCE(sum(l.line_amount), 0) AS montant,
               count(l.line_no)                AS lignes,
               c.status IN ('paid', 'closed')  AS retenu
        FROM contracts c
        JOIN clients cl ON cl.client_id = c.client_id
        JOIN sites s    ON s.site_id = c.site_id
        JOIN campus ca  ON ca.campus_id = s.campus_id
        LEFT JOIN contract_lines l ON l.contract_id = c.contract_id
        WHERE c.start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR ca.campus_id = %(campus)s::int)
          AND (%(statut)s::text IS NULL OR c.status = %(statut)s::text)
          AND (%(recherche)s::text IS NULL OR c.contract_id::text = %(recherche)s::text)
        GROUP BY c.contract_id, cl.name, s.name, ca.name
        ORDER BY c.start_date DESC, c.contract_id DESC
        LIMIT %(limite)s
    """, params)


def contrat(cur, contract_id: int) -> dict | None:
    entete = _une(cur, """
        SELECT c.contract_id, c.start_date, c.status, cl.name AS client,
               s.name AS site, ca.name AS campus, b.batch_number
        FROM contracts c
        JOIN clients cl ON cl.client_id = c.client_id
        JOIN sites s    ON s.site_id = c.site_id
        JOIN campus ca  ON ca.campus_id = s.campus_id
        JOIN ingestion_batches b ON b.batch_id = c.batch_id
        WHERE c.contract_id = %(id)s
    """, {'id': contract_id})
    if entete is None:
        return None
    lignes = _toutes(cur, """
        SELECT l.line_no, e.name AS equipement, cat.name AS categorie,
               l.quantity, l.duration, l.unit, l.unit_rate, l.line_amount
        FROM contract_lines l
        JOIN equipments e   ON e.equipment_id = l.equipment_id
        JOIN categories cat ON cat.category_id = e.category_id
        WHERE l.contract_id = %(id)s
        ORDER BY l.line_no
    """, {'id': contract_id})
    total = sum((Decimal(ligne['line_amount']) for ligne in lignes), Decimal('0'))
    return {'entete': dict(entete), 'lignes': lignes, 'total': total}


def observations_iot(cur, limite: int = 5) -> dict:
    """Bloc facultatif : n'affiche rien si le bonus IoT n'a pas été exécuté."""
    try:
        total = _une(cur, 'SELECT count(*) AS n FROM iot_observations')
        dernieres = _toutes(cur, """
            SELECT device_id, event_id, equipment_id, observed_at, latitude, longitude
            FROM iot_observations ORDER BY observed_at DESC LIMIT %(limite)s
        """, {'limite': limite})
        return {'disponible': True, 'total': int(total['n']), 'lignes': dernieres}
    except psycopg2.errors.UndefinedTable:
        cur.connection.rollback()
        return {'disponible': False, 'total': 0, 'lignes': []}


# ---------------------------------------------------------------------------
# Séries et vues enrichies (console)
# ---------------------------------------------------------------------------
def serie_journaliere(cur, filtres: Filtres) -> dict:
    """Montant, lignes et contrats par jour, jours vides compris."""
    params = filtres.parametres()
    lignes = _toutes(cur, """
        WITH jours AS (
            SELECT jour::date AS jour
            FROM generate_series(%(debut)s::date, %(fin)s::date, interval '1 day') AS jour
        ), totaux AS (
            SELECT start_date AS jour,
                   sum(line_amount)            AS montant,
                   count(*)                    AS lignes,
                   count(DISTINCT contract_id) AS contrats
            FROM v_lignes_retenues
            WHERE start_date BETWEEN %(debut)s AND %(fin)s
              AND (%(campus)s::int IS NULL OR campus_id = %(campus)s::int)
            GROUP BY start_date
        )
        SELECT j.jour,
               COALESCE(t.montant, 0)  AS montant,
               COALESCE(t.lignes, 0)   AS lignes,
               COALESCE(t.contrats, 0) AS contrats
        FROM jours j LEFT JOIN totaux t USING (jour)
        ORDER BY j.jour
    """, params)
    return {
        'jours': [ligne['jour'] for ligne in lignes],
        'etiquettes': [ligne['jour'].strftime('%d/%m') for ligne in lignes],
        'montant': [float(ligne['montant']) for ligne in lignes],
        'lignes': [int(ligne['lignes']) for ligne in lignes],
        'contrats': [int(ligne['contrats']) for ligne in lignes],
    }


def matrice_campus_jour(cur, filtres: Filtres) -> dict:
    """Montant par campus et par jour, pour la carte de chaleur."""
    params = filtres.parametres()
    lignes = _toutes(cur, """
        SELECT c.campus_id, c.name AS campus, v.start_date AS jour,
               sum(v.line_amount) AS montant
        FROM v_lignes_retenues v
        JOIN campus c ON c.campus_id = v.campus_id
        WHERE v.start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR v.campus_id = %(campus)s::int)
        GROUP BY c.campus_id, c.name, v.start_date
    """, params)
    campus = _toutes(cur, """
        SELECT campus_id, name FROM campus
        WHERE (%(campus)s::int IS NULL OR campus_id = %(campus)s::int)
        ORDER BY campus_id
    """, params)
    jours = [filtres.debut.fromordinal(filtres.debut.toordinal() + decalage)
             for decalage in range((filtres.fin - filtres.debut).days + 1)]
    index = {(ligne['campus_id'], ligne['jour']): float(ligne['montant'])
             for ligne in lignes}
    return {
        'campus': campus,
        'jours': jours,
        'valeurs': [[index.get((ligne['campus_id'], jour), 0.0) for jour in jours]
                    for ligne in campus],
    }


def categories_arbre(cur, filtres: Filtres) -> list[dict]:
    """Bonus récursif : montants par catégorie racine et par sous-catégorie."""
    params = filtres.parametres()
    lignes = _toutes(cur, """
        WITH RECURSIVE arbre AS (
            SELECT category_id, parent_id, category_id AS racine_id, 0 AS profondeur
            FROM categories WHERE parent_id IS NULL
            UNION ALL
            SELECT enfant.category_id, enfant.parent_id, a.racine_id, a.profondeur + 1
            FROM categories enfant JOIN arbre a ON enfant.parent_id = a.category_id
        )
        SELECT racine.name              AS racine,
               cat.name                 AS categorie,
               (a.profondeur > 0)       AS enfant,
               sum(v.line_amount)       AS montant,
               count(*)                 AS lignes
        FROM v_lignes_retenues v
        JOIN equipments e   ON e.equipment_id = v.equipment_id
        JOIN categories cat ON cat.category_id = e.category_id
        JOIN arbre a        ON a.category_id = cat.category_id
        JOIN categories racine ON racine.category_id = a.racine_id
        WHERE v.start_date BETWEEN %(debut)s AND %(fin)s
          AND (%(campus)s::int IS NULL OR v.campus_id = %(campus)s::int)
        GROUP BY racine.name, cat.name, a.profondeur
        ORDER BY montant DESC
    """, params)

    racines: dict[str, dict] = {}
    for ligne in lignes:
        racine = racines.setdefault(ligne['racine'],
                                    {'nom': ligne['racine'], 'montant': 0.0,
                                     'enfants': []})
        montant = float(ligne['montant'])
        if ligne['enfant']:
            racine['enfants'].append({'nom': ligne['categorie'], 'montant': montant,
                                      'lignes': int(ligne['lignes'])})
        else:
            racine['montant'] += montant
            racine['lignes'] = int(ligne['lignes'])
    # Le montant d'une racine est déjà porté par ses propres équipements ;
    # on y ajoute les sous-catégories pour obtenir le total de l'arbre.
    for racine in racines.values():
        racine['montant'] += sum(enfant['montant'] for enfant in racine['enfants'])
        racine['enfants'].sort(key=lambda enfant: enfant['montant'], reverse=True)
    return sorted(racines.values(), key=lambda racine: racine['montant'], reverse=True)


def etapes_pipeline(cur) -> dict:
    """Compteurs du parcours d'un lot, pour la frise animée."""
    ligne = _une(cur, """
        SELECT count(*)                                              AS lots,
               count(*) FILTER (WHERE status = 'CHARGE')             AS charges,
               count(*) FILTER (WHERE status = 'REJETE_STRUCTURE')   AS refuses,
               COALESCE(sum(rows_received), 0)                       AS recues,
               COALESCE(sum(rows_deduplicated), 0)                   AS doublons,
               COALESCE(sum(rows_accepted), 0)                       AS acceptees,
               COALESCE(sum(rows_rejected), 0)                       AS rejetees,
               COALESCE(sum(anomalies), 0)                           AS anomalies
        FROM ingestion_batches
    """)
    return {cle: int(valeur or 0) for cle, valeur in ligne.items()}


def flux_activite(cur, limite: int = 12) -> list[dict]:
    """Fil d'activité : lots, refus et observations IoT, du plus récent au plus ancien."""
    iot = _une(cur, "SELECT to_regclass('public.iot_observations') IS NOT NULL AS present")
    branch_iot = """
        UNION ALL
        SELECT 'iot', max(o.received_at), 0, 'info',
               'Observations GPS reçues',
               count(*) || ' observations · ' || count(DISTINCT o.device_id) || ' boîtiers'
        FROM iot_observations o
        HAVING count(*) > 0
    """ if iot['present'] else ''
    lignes = _toutes(cur, """
        SELECT 'lot' AS genre, b.charge_le AS quand, b.batch_number AS reference,
               CASE WHEN b.alerte_qualite THEN 'alerte' ELSE 'ok' END AS ton,
               'Lot ' || lpad(b.batch_number::text, 6, '0') || ' chargé' AS titre,
               b.rows_accepted || ' lignes · ' || b.contracts_accepted
                   || ' contrats · ' || round(b.rejection_rate, 1) || ' %% de rejet' AS detail
        FROM ingestion_batches b
        WHERE b.status = 'CHARGE'
        UNION ALL
        SELECT 'refus', b.recu_le, b.batch_number, 'danger',
               'Lot ' || lpad(b.batch_number::text, 6, '0') || ' refusé',
               COALESCE(b.motif_rejet, 'structure invalide')
        FROM ingestion_batches b
        WHERE b.status = 'REJETE_STRUCTURE'
    """ + branch_iot + """
        ORDER BY quand DESC NULLS LAST
        LIMIT %(limite)s
    """, {'limite': limite})
    return lignes


def points_iot(cur, limite: int = 400) -> list[dict]:
    try:
        return _toutes(cur, """
            SELECT device_id, equipment_id, observed_at, latitude, longitude
            FROM iot_observations
            ORDER BY observed_at DESC
            LIMIT %(limite)s
        """, {'limite': limite})
    except psycopg2.errors.UndefinedTable:
        cur.connection.rollback()
        return []
