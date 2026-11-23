# Bonus 2 — catégories récursives et précalcul

Toutes les requêtes sont exécutées sur la base de démonstration, après rafraîchissement de la vue matérialisée.

## `02_categories_recursives.sql`

### bonus_categories_arbre — 6 ligne(s) en 9.3 ms

| category_id | categorie | profondeur | chemin | categorie_racine | sous_categories_directes |
|---|---|---|---|---|---|
| 1 | Audiovisuel | 0 | Audiovisuel | Audiovisuel | 2 |
| 3 | Image | 1 | Audiovisuel > Image | Audiovisuel | 0 |
| 4 | Son | 1 | Audiovisuel > Son | Audiovisuel | 0 |
| 2 | Événementiel | 0 | Événementiel | Événementiel | 2 |
| 5 | Mobilier | 1 | Événementiel > Mobilier | Événementiel | 0 |
| 6 | Éclairage | 1 | Événementiel > Éclairage | Événementiel | 0 |

### bonus_montant_par_racine — 2 ligne(s) en 15.2 ms

| categorie_racine | lignes_retenues | montant | pct_montant | equipements_distincts |
|---|---|---|---|---|
| Événementiel | 663 | 795059.00 | 50.24 | 60 |
| Audiovisuel | 654 | 787586.00 | 49.76 | 60 |

## `03_precalcul.sql`

### bonus_precalcul_ecart — 0 ligne(s) en 6.8 ms

| campus_id | jour | montant_a_la_demande | montant_precalcule | ecart |
|---|---|---|---|---|

### bonus_precalcul_totaux — 1 ligne(s) en 3.7 ms

| total_precalcule | total_a_la_demande | cellules_precalculees |
|---|---|---|
| 1582645.00 | 1582645.00 | 125 |

## Preuve d'égalité

- Cellules précalculées : **125**
- Total précalculé : **1582645.00 MAD**
- Total recalculé à la demande : **1582645.00 MAD**
- Écarts détectés : **0**

Les deux chemins donnent le même résultat. Le précalcul sert à afficher vite ; le calcul à la demande sert à vérifier.

