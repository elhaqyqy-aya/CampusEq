# Bonus 1 — plan SQL avant / après index

Volume de mesure : **250 000 contrats**, 500 000 lignes,
180 jours de dates métier. Le schéma `bonus_index` est supprimé après la mesure : la base
de démonstration n'est pas modifiée.

Index ajouté : `bonus_index.contracts (start_date) WHERE status IN ('paid', 'closed')`.
Il est **partiel** : les contrats `draft` et `cancelled`, exclus des indicateurs, n'y
figurent pas.

Chaque requête est exécutée **une fois à blanc puis mesurée**, avant et après
l'index : l'écart vient donc de l'index, pas d'un cache réchauffé par la première
exécution.

## Requête A — activité d'une journée (sans jointure de lignes)

Nombre de contrats et de guichets actifs par campus, pour le 6 novembre 2026.

| | Sans index | Avec index |
|---|---:|---:|
| Temps d'exécution | 53.67 ms | 3.64 ms |
| Empreinte du résultat | `79c54f5a1f8658cff3e09e1ea4c0c030` | `79c54f5a1f8658cff3e09e1ea4c0c030` |
| Résultat identique | oui | |
| Gain | | **×15** |

Avant : `Seq Scan` sur les 250 000 contrats. Après : `Bitmap Index Scan`
sur l'index partiel, puis lecture des seules lignes utiles.

## Requête B — montant d'une journée (avec jointure des lignes)

Même filtre, mais on additionne les montants : la requête doit lire `contract_lines`.

| | Sans index | Avec index |
|---|---:|---:|
| Temps d'exécution | 211.04 ms | 119.24 ms |
| Empreinte du résultat | `df6eed2f41fac1df546a8ddd7407c3ac` | `df6eed2f41fac1df546a8ddd7407c3ac` |
| Résultat identique | oui | |
| Gain | | **×1.8** |

Ici le gain est faible : le planificateur choisit de balayer les
500 000 lignes (`Seq Scan on contract_lines`) et l'index ne fait
disparaître que le balayage des contrats. C'est le résultat le plus instructif du bonus :
**un index ne corrige que la partie du coût qu'il adresse**. Pour cette requête, le
correctif serait de forcer une boucle imbriquée (jointure `LATERAL` par contrat) ou de
réduire encore la période, pas d'ajouter un second index sur `start_date`.

Coût de création de l'index : **0.20 s**. Les plans complets sont dans
`index_activite_avant.txt`, `index_activite_apres.txt`, `index_montant_avant.txt` et
`index_montant_apres.txt`.

## Ce qu'il faut retenir

Un index n'accélère pas « la base » : il accélère **une forme de requête**, au prix
d'écritures plus lentes et d'espace disque. Le même index divise ici le temps par
15 sur un comptage et ne change presque rien sur une agrégation de
montants. Sur une petite table, le planificateur peut préférer le parcours séquentiel :
c'est normal, et le résultat reste identique.
