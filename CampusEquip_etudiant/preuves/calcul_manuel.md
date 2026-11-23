# Preuve — calcul d'un contrat à la main

Contrat **7** — client Association 0622, Campus Marrakech / guichet 2 (Campus Marrakech), début le 07/11/2026, statut `paid`.

| Ligne | Équipement | Quantité | Durée | Unité | Tarif | Calcul | Montant en base |
|---:|---|---:|---:|---|---:|---|---:|
| 1 | Équipement 075 | 4 | 1 | hour | 15.00 | 4 × 1 × 15.00 = **60.00** | 60.00 |
| 2 | Équipement 005 | 1 | 1 | hour | 33.00 | 1 × 1 × 33.00 = **33.00** | 33.00 |
| 3 | Équipement 075 | 1 | 1 | day | 268.00 | 1 × 1 × 268.00 = **268.00** | 268.00 |

**Total à la main : 361.00 MAD.**
**Total retenu par la vue SQL : 361.00 MAD.**

Les deux valeurs sont identiques : la même formule est appliquée par le code Python (pour le contrôle) et par PostgreSQL (colonne générée `line_amount`), ce qui évite qu'un indicateur diverge du tarif historique reçu.

## La requête qui produit le total

```sql
SELECT sum(line_amount)
FROM v_lignes_retenues
WHERE contract_id = %s;   -- la vue applique le filtre paid / closed
```

## Ce que la preuve vérifie

- la durée est déjà exprimée dans l'unité de la ligne : on ne convertit ni
  les jours en heures, ni l'inverse ;
- le tarif conservé est celui de la ligne (`unit_rate`), pas un tarif courant ;
- tout le montant est rattaché à `start_date` du contrat ;
- le contrat n'est compté qu'une fois, même avec plusieurs lignes.

