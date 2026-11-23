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


SELECT unit,
       count(*)                                                     AS lignes_retenues,
       count(DISTINCT contract_id)                                  AS contrats,
       sum(line_amount)                                             AS montant,
       round(100 * sum(line_amount) / sum(sum(line_amount)) OVER (), 2) AS pct_montant_global
FROM v_lignes_retenues
GROUP BY unit
ORDER BY montant DESC;

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

SELECT b.batch_number AS lot,
       r.contract_id,
       r.line_no,
       r.motifs
FROM batch_rejections r
JOIN ingestion_batches b USING (batch_id)
ORDER BY b.batch_number, r.position
LIMIT 50;
