-- =====================================================================
-- CampusEquip — analyses SQL de l'axe 1
--
-- Exécution :
--     python -m outils.analyses          (résultats, tableaux Markdown, graphique)
-- ou, avec psql :
--     psql -d campusequip -f analyses.sql
--
-- Chaque bloc commence par un marqueur « -- @resultat: nom » que le lanceur
-- Python utilise pour nommer ses exports. Le SQL reste lisible et exécutable
-- tel quel : les marqueurs sont de simples commentaires.
--
-- Convention commerciale : seuls paid et closed comptent ; le montant d'une
-- ligne vaut quantité x durée x tarif, et il est rattaché à start_date.
-- Toutes les requêtes lisent la vue v_lignes_retenues : elles ne peuvent donc
-- pas diverger sur le filtre de statut ni sur le calcul du montant.
-- =====================================================================

-- @resultat: lots_analyses
-- Quels lots sont dans la base ? C'est la première chose à écrire dans un
-- rapport : un indicateur ne vaut que pour les lots annoncés.
SELECT b.batch_id,
       b.batch_number                                  AS lot,
       b.campaign_id,
       b.status,
       b.rows_accepted                                 AS lignes_acceptees,
       b.rows_rejected                                 AS lignes_rejetees,
       b.contracts_accepted                            AS contrats_acceptes,
       b.rejection_rate                                AS taux_rejet_pct,
       b.alerte_qualite,
       b.charge_le
FROM ingestion_batches b
WHERE b.status = 'CHARGE'
ORDER BY b.batch_id;


-- @resultat: a1_montant_par_jour_campus
-- A1. Montant par date et par campus, du 1er au 21 novembre 2026.
--     generate_series garantit une ligne par jour, même sans location :
--     les jours sans montant apparaissent à 0 au lieu de disparaître.
--     Le cumul est calculé par campus, dans l'ordre des dates.
WITH jours AS (
    SELECT jour::date AS jour
    FROM generate_series(date '2026-11-01', date '2026-11-21', interval '1 day') AS jour
),
totaux AS (
    SELECT campus_id, start_date AS jour, sum(line_amount) AS montant, count(*) AS lignes
    FROM v_lignes_retenues
    GROUP BY campus_id, start_date
)
SELECT c.campus_id,
       c.name                                              AS campus,
       j.jour,
       coalesce(t.lignes, 0)                               AS lignes_retenues,
       coalesce(t.montant, 0)                              AS montant_jour,
       sum(coalesce(t.montant, 0)) OVER (PARTITION BY c.campus_id ORDER BY j.jour)
                                                           AS cumul_campus
FROM campus c
CROSS JOIN jours j
LEFT JOIN totaux t ON t.campus_id = c.campus_id AND t.jour = j.jour
ORDER BY c.campus_id, j.jour;


-- @resultat: a2_equipements_contributeurs
-- A2. Équipements les plus contributeurs, classés par montant décroissant
--     dans chaque campus. DENSE_RANK donne le même rang aux égalités (au lieu
--     de ROW_NUMBER, qui départagerait arbitrairement deux montants égaux).
WITH montant_equipement AS (
    SELECT campus_id, equipment_id, sum(line_amount) AS montant, count(*) AS lignes
    FROM v_lignes_retenues
    GROUP BY campus_id, equipment_id
)
SELECT m.campus_id,
       c.name                                   AS campus,
       m.equipment_id,
       e.name                                   AS equipement,
       cat.name                                 AS categorie,
       m.lignes                                 AS lignes_retenues,
       m.montant,
       dense_rank() OVER (PARTITION BY m.campus_id ORDER BY m.montant DESC) AS rang
FROM montant_equipement m
JOIN campus c     ON c.campus_id = m.campus_id
JOIN equipments e ON e.equipment_id = m.equipment_id
JOIN categories cat ON cat.category_id = e.category_id
ORDER BY m.campus_id, rang, m.equipment_id;


-- @resultat: a3_heure_ou_journee
-- A3. Comparaison heure / journée, par campus. On ne compare jamais des heures
--     à des jours : on compare des MONTANTS en MAD et le nombre de lignes.
--     pct_montant situe chaque unité dans le total du campus.
WITH par_unite AS (
    SELECT campus_id, unit, count(*) AS lignes, sum(line_amount) AS montant
    FROM v_lignes_retenues
    GROUP BY campus_id, unit
)
SELECT campus_id,
       campus,
       unit,
       lignes,
       montant,
       round(100 * montant / sum(montant) OVER (PARTITION BY campus_id), 2) AS pct_montant,
       round(montant / nullif(lignes, 0), 2)                               AS panier_moyen
FROM (
    SELECT p.campus_id, c.name AS campus, p.unit, p.lignes, p.montant
    FROM par_unite p JOIN campus c ON c.campus_id = p.campus_id
) AS detail
ORDER BY campus_id, unit;


-- @resultat: a3b_synthese_unites
-- A3 (suite). Le même constat, tous campus confondus : deux lignes suffisent
-- pour répondre « les locations à l'heure et à la journée contribuent-elles
-- de la même façon ? ».
SELECT unit,
       count(*)                                                     AS lignes_retenues,
       count(DISTINCT contract_id)                                  AS contrats,
       sum(line_amount)                                             AS montant,
       round(100 * sum(line_amount) / sum(sum(line_amount)) OVER (), 2) AS pct_montant_global
FROM v_lignes_retenues
GROUP BY unit
ORDER BY montant DESC;


-- @resultat: controle_totaux
-- Contrôle : les trois analyses doivent sommer le même univers.
-- total_vue est la référence ; les deux autres valeurs doivent lui être égales.
SELECT (SELECT sum(line_amount) FROM v_lignes_retenues)                       AS total_vue,
       (SELECT sum(montant_jour) FROM (
            SELECT sum(line_amount) AS montant_jour
            FROM v_lignes_retenues
            GROUP BY campus_id, start_date) x)                                AS total_a1,
       (SELECT sum(montant) FROM (
            SELECT sum(line_amount) AS montant
            FROM v_lignes_retenues
            GROUP BY campus_id, unit) y)                                      AS total_a3,
       (SELECT count(*) FROM contracts)                                       AS contrats_stockes,
       (SELECT count(*) FROM contracts WHERE status IN ('paid', 'closed'))    AS contrats_retenus;


-- @resultat: quarantaine_par_motif
-- Règle de quarantaine telle qu'elle est tracée en base : motifs agrégés sur
-- les lots chargés. Un même rejet peut porter plusieurs motifs.
SELECT b.batch_number AS lot,
       r.contract_id,
       r.line_no,
       r.motifs
FROM batch_rejections r
JOIN ingestion_batches b USING (batch_id)
ORDER BY b.batch_number, r.position
LIMIT 50;
