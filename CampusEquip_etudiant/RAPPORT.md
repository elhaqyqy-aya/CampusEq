![](docs/captures/mark.png)

**

# CampusEquip — pipeline des axes 1 et 2

*Rapport de projet — 4 lots chargés, 1 104 contrats, dernier chargement le 04/11/2026 22:10*

## 1. Objectif et démarche

CampusEquip loue du matériel à des associations sur six campus. Le projet transforme des fichiers de locations en données fiables, chargées dans PostgreSQL, et en indicateurs SQL explicables. Le pipeline suit quatre étapes : contrôler la structure du lot, normaliser sans réparer, isoler les contrats incohérents en quarantaine, puis charger les contrats acceptés dans une seule transaction.

Deux choix structurent le travail. D'abord, les règles de décision sont séparées de la base : `etudiant/regles.py` ne lit aucun fichier et n'écrit rien, ce qui permet de tester chaque règle sans PostgreSQL. Ensuite, le montant d'une ligne est une colonne calculée par la base (`quantity * duration * unit_rate`), donc l'indicateur ne peut pas diverger du tarif historique reçu.

## 2. Modèle relationnel

| Table | Grain | Clés et contraintes principales |
|---|---|---|
| campus | un campus | PK campus_id |
| sites | un guichet | PK site_id, FK campus_id — 1 campus → N sites |
| clients | une association | PK client_id |
| categories | une catégorie | PK category_id, FK parent_id (auto-référence) |
| equipments | un type de matériel | PK equipment_id, FK category_id |
| contracts | un contrat | PK contract_id, FK client_id, site_id, batch_id |
| contract_lines | une ligne de contrat | PK (contract_id, line_no), FK equipment_id |
| ingestion_batches | une tentative de traitement | PK batch_id, signature unique |

Les contraintes de qualité sont aussi dans le schéma : `quantity` entre 1 et 100, `unit` limité à `hour` ou `day`, `duration` entre 1 et 720 heures ou 1 et 365 jours selon l'unité, `unit_rate` positif avec au plus deux décimales, et `status` limité aux quatre valeurs du sujet. Le schéma ne laisse donc pas entrer une ligne que Python aurait laissé passer par erreur.

## 3. Règles de qualité et quarantaine

La décision se prend au niveau du contrat, pas de la ligne isolée : une seule ligne invalide met tout son contrat en quarantaine, car un contrat à moitié chargé fausserait les montants. Les répétitions exactes, elles, sont retirées avant les contrôles et ne comptent qu'une fois.

- répétition exacte après normalisation → une seule occurrence conservée ;
- même (contract_id, line_no) avec un contenu différent → tout le contrat isolé ;
- en-tête de contrat contradictoire (client, site, date ou statut) → tout le contrat isolé ;
- référence inconnue (client, site, équipement) → tout le contrat isolé ;
- quantity > 20 → ligne acceptée et signalée comme anomalie, jamais rejetée ;
- colonnes absentes, en trop ou dans le mauvais ordre → lot refusé avant écriture.

Le taux de rejet vaut rejets ÷ lignes après dédoublonnage. Sur les lots chargés : 2 475 lignes reçues, 24 répétitions retirées, 2 203 acceptées, 248 rejetées, soit 10,1 % ; 248 lignes et 24 anomalies sont tracées en base. Au-delà de 20 %, le pipeline signale une alerte mais charge les contrats valides : le seuil déclenche une revue, il ne bloque pas le flux.

## 4. Chargement transactionnel et rejeu

La signature d'un lot est un SHA-256 calculé sur les empreintes des deux fichiers et sur la version des règles. Elle ne dépend ni du nom du dossier ni du nom des fichiers : un lot redéposé sous un autre nom est reconnu. Le journal `ingestion_batches` est la seule référence : si la signature y figure déjà, le statut est DEJA_CHARGE et aucune ligne métier n'est ajoutée. Si un nouveau lot réutilise un `contract_id` déjà chargé, la transaction entière échoue et l'échec remonte au surveilleur.

La base mémorise aussi la première campagne et l'empreinte des référentiels : une autre campagne est refusée dans la même base. Preuve observée sur ce jeu : 4 lots chargés, puis 16 rejeux reconnus DEJA_CHARGE, sans aucun ajout.

## 5. Résultats des trois analyses

Les indicateurs ne retiennent que les contrats `paid` et `closed` : 663 contrats sur 1 104 stockés, 1 317 lignes, 1 582 645 MAD au total. Tout le montant est rattaché à `start_date`.

| Campus | Montant retenu (1er – 21 nov.) | Part |
|---|---|---|
| Campus Rabat | 301 191 MAD | 19,0 % |
| Campus Casablanca | 290 138 MAD | 18,3 % |
| Campus Tanger | 277 297 MAD | 17,5 % |

![Montant retenu par jour et par campus — jours sans location à zéro.](resultats/graphique_a1_montant_jour_campus.png)

*Montant retenu par jour et par campus — jours sans location à zéro.*

| Unité | Lignes retenues | Montant | Part du montant |
|---|---|---|---|
| à l'heure | 663 | 433 944 MAD | 27,4 % |
| à la journée | 654 | 1 148 701 MAD | 72,6 % |

![Montant retenu à l'heure et à la journée, par campus.](resultats/graphique_a3_heure_journee.png)

*Montant retenu à l'heure et à la journée, par campus.*

Réponse en deux phrases. La répartition entre campus est serrée (13,9 % à 19,0 % du montant) et Campus Rabat arrive en tête avec 301 191 MAD ; l'équipement le plus rentable est Équipement 047. Les locations à la journée représentent 72,6 % du montant pour un nombre de lignes comparable à celui des heures : les deux unités ne contribuent donc pas de la même façon, et on compare des MAD, jamais des heures avec des jours.

## 6. Preuves

- 41 tests automatisés passent (règles pures, chargement, quarantaine, rejeu, conflit inter-lots, structure, alerte, trois lots surveillés) : OK ;
- structure invalide : lot refusé, zéro contrat écrit, refus tracé dans le journal ;
- conflit de contrat entre deux lots : transaction annulée, journal intact ;
- alerte au-delà de 20 % : taux 30 % observé, 6 contrats valides chargés, 3 isolés ;
- bonus mesurés : index (×15 sur un comptage), catégories récursives, précalcul égal au calcul à la demande, lecture par morceaux aux mêmes décisions, chaîne IoT avec rejeu et panne.

## 7. Limites et répartition du travail

Le pipeline traite un lot à la fois : aucune concurrence entre plusieurs surveillants n'est gérée au-delà d'un verrou consultatif. Il ne détecte pas une ligne jamais reçue (le manifeste ne décrit pas le contenu attendu ligne à ligne), ni un encaissement bancaire : `paid` est une convention pédagogique. Les référentiels sont supposés fixes par campagne, ce que la base vérifie par empreinte.

Répartition à compléter par le binôme : chacun doit pouvoir expliquer une jointure (par exemple contracts → sites → campus), une décision de qualité (la quarantaine d'un contrat) et le calcul d'un montant. Conformément au sujet, consignez les aides réellement utilisées dans `journal_IA.md`.

## Annexe A — reproduire les résultats

Toutes les commandes partent de la racine du projet, avec `DATABASE_URL` défini (voir le README). Aucune ne demande de mot de passe écrit dans un fichier.

```text
python -m outils.init_base --reinitialiser   # base neuve + schéma
python -m outils.demo                        # 4 lots : chargement, rejeu, analyses
python -m outils.analyses                    # tableaux et graphiques seuls
python -m unittest discover -s tests -t .    # 41 tests
python -m outils.preuve_alerte               # alerte > 20 %
python -m outils.preuve_bonus                # récursif et précalcul
python -m outils.preuve_index                # plans avant/après index
python -m outils.preuve_morceaux             # lecture par morceaux
python -m outils.preuve_iot                  # chaîne IoT simulée
python -m outils.rapport                     # ce rapport
```

## Annexe B — où trouver chaque preuve

| Question | Preuve | Fichier |
|---|---|---|
| Le modèle tient-il ? | contraintes exécutées, insertion refusée | etudiant/schema.sql |
| Quels montants ? | trois analyses + graphiques | resultats/ |
| Quels contrats isolés ? | un rapport et un JSONL par lot | rapports/, quarantaine/ |
| Le rejeu double-t-il ? | 4 rejeux DEJA_CHARGE à 0 ajout | preuves/TESTS.md |
| Les règles sont-elles testées ? | 41 tests OK | preuves/tests_unittest.txt |
| Les bonus sont-ils mesurés ? | index, récursif, morceaux, IoT | preuves/index_synthese.md, bonus_sql.md, lecture_morceaux.md, iot.md |
