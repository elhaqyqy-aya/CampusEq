# Preuve — alerte au-delà de 20 % de rejet

Cas construit exprès : 9 contrats, dont 3 avec une quantité négative 
(contrats 7, 8, 9) et un contrat valide portant une anomalie de quantité 25.

| Indicateur | Attendu | Observé |
|---|---|---|
| Statut | CHARGE | CHARGE |
| Lignes reçues | 10 | 10 |
| Doublons retirés | 0 | 0 |
| Lignes acceptées | 7 | 7 |
| Lignes rejetées | 3 | 3 |
| Taux de rejet | 30,00 % | 30.00 % |
| Alerte qualité | oui | oui |
| Contrats acceptés | 6 | 6 |
| Contrats rejetés | 3 | 3 |
| Lignes ajoutées en base | 7 | 7 |

En base : **6 contrats**, 3 ligne(s) en quarantaine, 1 anomalie(s) signalée(s).

## Ce que la preuve démontre

L'alerte n'interrompt pas le chargement : les 6 contrats valides sont en base, les 3 contrats invalides restent en quarantaine avec leurs motifs, et le taux de rejet (3 / 10 = 30 %) dépasse le seuil de 20 %. L'anomalie de quantité 25 reste une ligne acceptée et signalée : elle n'entre ni dans les rejets ni dans le taux.

## Extrait du rapport produit

```json
{
  "statut": "CHARGE",
  "lot": 1,
  "campagne": "campagne-alerte",
  "compteurs": {
    "lignes_recues": 10,
    "doublons_retires": 0,
    "lignes_apres_dedoublonnage": 10,
    "lignes_acceptees": 7,
    "lignes_rejetees": 3,
    "contrats_recus": 9,
    "contrats_acceptes": 6,
    "contrats_rejetes": 3,
    "anomalies": 1,
    "taux_rejet_pct": 30.0,
    "alerte_qualite": true,
    "lignes_ajoutees_en_base": 7
  },
  "motif_rejet_structure": null
}
```

Le rapport complet est généré dans `rapports/` avec un nom horodaté. Base utilisée : `campusequip_alerte` (isolée de la base de démonstration).

