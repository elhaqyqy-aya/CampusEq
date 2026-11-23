# Preuves des règles — attendu, observé, commande

Chaque essai du sujet (page 10) est couvert par un test automatisé **exécuté**
et, quand c'est utile, par un artefact conservé. Rien n'est annoncé comme testé
sans une sortie correspondante. La sortie complète des tests est conservée dans
`preuves/tests_unittest.txt` (`Ran 41 tests … OK`).

Commande unique :

```powershell
$env:CAMPUSEQUIP_TEST_URL = "postgresql://postgres@127.0.0.1:5432/campusequip_test"
python -m unittest discover -s tests -t . -v
```

## Tableau des essais

| # | Essai du sujet | Attendu | Observé | Test |
|---|---|---|---|---|
| 1 | Location valide à l'heure et à la journée | 150 + 400 = 550 MAD ; seuls `paid`/`closed` comptent | contrat 2001 : 550,00 MAD ; `cancelled` stocké mais 0 dans la vue | `test_montants_heure_et_journee_et_statuts` |
| 2 | Répétition exacte et conflit de clé | la copie compte une fois ; le conflit isole le contrat entier | 1 doublon retiré, contrat 11 (3 lignes) entièrement rejeté | `test_repetition_confirmee_et_conflit_de_cle` |
| 3 | Quantité invalide et `quantity = 25` | contrat invalide isolé ; 25 accepté + anomalie | 1 contrat rejeté, 1 accepté, 1 anomalie en base | `test_quantite_invalide_et_quantite_25` |
| 4 | Référence inconnue ou en-tête contradictoire | toutes les lignes du contrat en quarantaine | 3 lignes rejetées, 0 contrat écrit, motifs `EQUIPEMENT_INCONNU` et `ENTETE_CONTRAT_CONTRADICTOIRE` | `test_entete_contradictoire_et_reference_inconnue` |
| 5 | Structure incorrecte | lot refusé avant toute écriture métier | `REJETE_STRUCTURE`, 0 contrat, 1 ligne de journal `REJETE_STRUCTURE` | `test_structure_invalide_refusee_avant_ecriture`, `test_colonne_supplementaire_refusee` |
| 6 | Rejeu après arrêt et redémarrage | identifiants, lignes et montants inchangés | `DEJA_CHARGE`, 0 ligne ajoutée, compteurs identiques | `test_rejeu_identique_ne_double_rien`, `test_dossier_renomme_reconnu_comme_rejeu` |
| 7 | Nouveau lot réutilisant un contrat chargé | aucun ajout partiel, journal précédent intact | `ConflitContrat` levée, 0 nouvelle ligne, durée du contrat 100 inchangée | `test_nouveau_lot_reutilisant_un_contrat_echoue_sans_rien_ecrire` |
| 8 | Trois lots successifs pendant la surveillance | trois rapports distincts, traitement automatique | 3 lignes `CHARGE`, 3 rapports JSON, puis 3 `DEJA_CHARGE` au rejeu | `test_trois_lots_pris_en_charge_sans_redemarrage` |
| 9 | Taux de rejet au-delà de 20 % | alerte sans bloquer les contrats valides | 30 % → alerte, 6 contrats chargés, 3 isolés | `test_taux_superieur_a_20_pourcent_alerte_mais_charge_le_reste`, `preuves/alerte.md` |
| 10 | Campagne différente dans la même base | refus | `REJETE_STRUCTURE` motif `CAMPAGNE_REFUSEE`, aucun contrat ajouté | `test_campagne_differente_refusee` |
| 11 | Référentiels modifiés en cours de campagne | refus | `REJETE_STRUCTURE` motif `REFERENTIELS_INCOHERENTS` | `test_referentiels_modifies_refuses` |
| 12 | Une ligne invalide parmi des lignes valides | tout le contrat isolé | 2 lignes rejetées, contrat non chargé, motif `CONTRAT_EN_QUARANTAINE` | `test_une_ligne_invalide_isole_toutes_les_lignes_du_contrat` |
| 13 | Banc de charge dans le tableau de bord | exécution isolée, compteurs exacts, rapport téléchargeable, aucune modification métier | 10 générés et reçus, zéro perdu, schéma temporaire supprimé | `test_page_api_et_execution_isolee` |

## Preuves conservées

| Fichier | Ce qu'il montre |
|---|---|
| `preuves/tests_unittest.txt` | sortie brute des 41 tests (`OK`) |
| `preuves/calcul_manuel.md` | un contrat réel : 60 + 33 + 268 = 361 MAD, identique au total SQL |
| `preuves/alerte.md` | cas construit à 30 % de rejet : alerte, chargement partiel, extrait du rapport |
| `preuves/index_synthese.md` | plans avant/après index, résultats identiques, gain mesuré |
| `preuves/lecture_morceaux.md` | lecture par morceaux : mêmes décisions qu'en lecture complète |
| `preuves/bonus_sql.md` | catégories récursives, précalcul égal au calcul à la demande |
| `preuves/iot.md` | acquisition GPS, rejeu, panne, montants des contrats inchangés |
| `rapports/` | un rapport par tentative (CHARGE, DEJA_CHARGE ou REJETE_STRUCTURE) |
| `quarantaine/` | un JSONL par lot avec position, valeurs brutes et motifs |

## Preuve de rejeu, pas à pas

1. `python -m outils.demo` charge quatre lots, puis les rejoue.
2. Dans `rapports/`, deux fichiers portent le même numéro de lot : le premier
   `CHARGE` avec `lignes_ajoutees_en_base = 549`, le second `DEJA_CHARGE` avec
   `lignes_ajoutees_en_base = 0`.
3. En base : `SELECT count(*) FROM contracts;` donne toujours 1104, et
   `SELECT count(*) FROM ingestion_batches WHERE status = 'CHARGE';` donne 4.

```sql
-- À exécuter soi-même : aucun lot ne doit apparaître deux fois.
SELECT signature, count(*) FROM ingestion_batches
WHERE status = 'CHARGE' GROUP BY signature HAVING count(*) > 1;   -- 0 ligne
```

## Ce que les tests ne prouvent pas

* Une ligne jamais reçue n'est pas détectée (le manifeste ne décrit pas le
  contenu attendu).
* Un encaissement bancaire n'est pas vérifié : `paid` est une convention.
* La concurrence entre deux surveillants n'est pas testée au-delà du verrou
  consultatif.
