-- =====================================================================
-- BONUS 2b — calcul à la demande contre résultat précalculé
--
-- La vue matérialisée `mv_montant_jour_campus` (créée par etudiant/schema.sql)
-- stocke le montant jour x campus. Elle doit être rafraîchie après un
-- chargement : REFRESH MATERIALIZED VIEW. Les deux requêtes ci-dessous doivent
-- renvoyer exactement le même résultat, seule la vitesse change.
--
-- Intérêt : un tableau de bord qui interroge 20 fois par minute ne recalcule
-- pas l'agrégat sur toutes les lignes ; un rapport d'audit, lui, recalcule à la
-- demande pour vérifier que le précalcul n'a pas dérivé.
-- =====================================================================

-- @resultat: bonus_precalcul_ecart
-- Aucune ligne ne doit sortir de cette requête : c'est la preuve d'égalité.
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
