WITH a_la_demande AS (
    SELECT campus_id, start_date AS jour, sum(line_amount) AS montant
    FROM v_lignes_retenues
    GROUP BY campus_id, start_date
)
SELECT coalesce(d.campus_id, m.campus_id)  AS campus_id,
       coalesce(d.jour, m.jour)            AS jour,
       d.montant                           AS montant_a_la_demande,
       m.montant                           AS montant_precalcule,
       coalesce(d.montant, 0) - coalesce(m.montant, 0) AS ecart
FROM a_la_demande d
FULL OUTER JOIN mv_montant_jour_campus m
       ON m.campus_id = d.campus_id AND m.jour = d.jour
WHERE coalesce(d.montant, 0) <> coalesce(m.montant, 0)
ORDER BY 1, 2;

-- @resultat: bonus_precalcul_totaux
-- Contrôle de total, plus lisible qu'une liste d'écarts.
SELECT (SELECT sum(montant) FROM mv_montant_jour_campus)        AS total_precalcule,
       (SELECT sum(line_amount) FROM v_lignes_retenues)         AS total_a_la_demande,
       (SELECT count(*) FROM mv_montant_jour_campus)            AS cellules_precalculees;
