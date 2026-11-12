SELECT s.campus_id,
       c.name                       AS campus,
       sum(l.line_amount)           AS montant,
       count(*)                     AS lignes
FROM contracts c
JOIN contract_lines l ON l.contract_id = c.contract_id
JOIN sites s          ON s.site_id = c.site_id
JOIN campus c2        ON c2.campus_id = s.campus_id
WHERE c.status IN ('paid', 'closed')
  AND c.start_date BETWEEN date '2026-11-05' AND date '2026-11-07'
GROUP BY s.campus_id, c.name
ORDER BY s.campus_id;

-- Index candidat. Il est partiel : les contrats draft et cancelled, exclus
-- des indicateurs, n'ont pas besoin d'y figurer.
CREATE INDEX ix_contracts_ret  ON contracts (start_date) WHERE status IN ('paid', 'closed');
CREATE INDEX ix_contracts_ret2 ON contracts (start_date, site_id) WHERE status IN ('paid', 'closed');

-- Variante « couvrante » : l'index seul suffit pour la jointure et le filtre.
-- (À comparer aussi, mais un index plus large coûte plus cher à maintenir.)
CREATE INDEX ix_contracts_ret3 ON contracts (start_date) INCLUDE (site_id)
    WHERE status IN ('paid', 'closed');
