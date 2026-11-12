WITH RECURSIVE arbre AS (
    SELECT category_id,
           name,
           category_id            AS racine_id,
           name::text             AS racine_nom,
           0                      AS profondeur,
           name::text             AS chemin
    FROM categories
    WHERE parent_id IS NULL
    UNION ALL
    SELECT enfant.category_id,
           enfant.name,
           arbre.racine_id,
           arbre.racine_nom,
           arbre.profondeur + 1,
           (arbre.chemin || ' > ' || enfant.name)::text
    FROM categories enfant
    JOIN arbre ON enfant.parent_id = arbre.category_id
)
SELECT a.category_id,
       a.name                                        AS categorie,
       a.profondeur,
       a.chemin,
       a.racine_nom                                  AS categorie_racine,
       (SELECT count(*) FROM categories enfant WHERE enfant.parent_id = a.category_id)
                                                     AS sous_categories_directes
FROM arbre a
ORDER BY a.chemin;


-- @resultat: bonus_montant_par_racine
-- Montant et nombre de lignes remontés à la catégorie racine. Le montant se
-- propage par le chemin : `v_lignes_retenues` -> equipments -> arbre.
WITH RECURSIVE arbre AS (
    SELECT category_id, category_id AS racine_id, 0 AS profondeur
    FROM categories
    WHERE parent_id IS NULL
    UNION ALL
    SELECT enfant.category_id, arbre.racine_id, arbre.profondeur + 1
    FROM categories enfant
    JOIN arbre ON enfant.parent_id = arbre.category_id
)
SELECT r.name                                        AS categorie_racine,
       count(*)                                      AS lignes_retenues,
       sum(v.line_amount)                            AS montant,
       round(100 * sum(v.line_amount)
             / sum(sum(v.line_amount)) OVER (), 2)    AS pct_montant,
       count(DISTINCT v.equipment_id)                 AS equipements_distincts
FROM v_lignes_retenues v
JOIN equipments e ON e.equipment_id = v.equipment_id
JOIN arbre a      ON a.category_id = e.category_id
JOIN categories r ON r.category_id = a.racine_id
GROUP BY r.name
ORDER BY montant DESC;
