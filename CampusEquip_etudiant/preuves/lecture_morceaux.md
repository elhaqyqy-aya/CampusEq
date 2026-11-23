# Bonus 3 — lecture par morceaux

Lot de test : **3146 lignes**, profil `mixte`, généré par `generer.py --contrats 1500 --lots 1 --graine 11`.

| Mode de lecture | Morceaux | Durée | Pic mémoire | Lignes décidées | Décisions identiques |
|---|---:|---:|---:|---:|---|
| complète | 1 | 1.30 s | 9.4 Mio | 3116 | oui |
| 100 lignes | 32 | 0.88 s | 8.8 Mio | 3116 | oui |
| 1000 lignes | 4 | 1.01 s | 8.8 Mio | 3116 | oui |
| 10000 lignes | 1 | 1.10 s | 8.9 Mio | 3116 | oui |

**Résultat : les quatre lectures prennent exactement les mêmes décisions** (même verdict, mêmes motifs, mêmes anomalies, mêmes montants, aux mêmes positions).

## Pourquoi les contrats ne sont pas coupés

`bonus/lecture_morceaux.py` ne décide rien à la fin d'un morceau : il empile les lignes contrôlées, puis appelle une seule fois `regles.finaliser_analyse`, qui vérifie la cohérence de chaque contrat et calcule les montants. Un contrat dont les lignes tombent dans deux morceaux est donc traité exactement comme en lecture complète.

## Limite honnête

La mémoire reste proportionnelle au nombre de lignes décidées : le script garde une décision compacte par ligne, mais libère les lignes brutes du CSV après chaque morceau. Pour un lot qui ne tiendrait pas en mémoire, l'étape suivante serait d'écrire ces décisions dans une table temporaire PostgreSQL au fil de l'eau, puis de les joindre pour la cohérence des contrats.

