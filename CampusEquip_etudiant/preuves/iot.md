# Bonus IoT — preuves d'acquisition, de rejeu et de panne

Producteur : `python -m bonus.iot.producteur` (GPS simulé, positions fictives).
Collecteur : `python -m bonus.iot.collecteur --entree <dossier> --une-fois`.

## 1. Acquisition et contrôles

| Lot | Statut | Reçues | Insérées | Rejetées | Rejeu |
|---|---|---:|---:|---:|---:|
| flux | CHARGE | 50 | 50 | 0 | 0 |
| flux | CHARGE | 50 | 50 | 0 | 0 |

Total inséré : **100 observations**. Contrôles appliqués : équipement connu dans `equipments`, instant ISO 8601 en UTC, latitude entre -90 et 90, longitude entre -180 et 180, clé `(device_id, event_id)`.

## 2. Rejeu des mêmes fichiers

| Lot | Statut | Insérées |
|---|---|---:|
| flux | DEJA_CHARGE | 0 |
| flux | DEJA_CHARGE | 0 |

Rejeu conforme : **oui** — aucune observation ajoutée, le journal `iot_lots` reconnaît la signature des fichiers.

## 3. Panne du producteur (JSON tronqué)

- Code de sortie du collecteur : **1** (échec visible)
- Statut du lot : **REJETE_STRUCTURE**
- Motif : `JSON_INVALIDE ligne 20 : Unterminated string starting at`
- Lignes insérées par ce lot : **0** (transaction annulée en bloc)

## 4. Les locations ne sont pas modifiées

| | Avant | Après |
|---|---:|---:|
| Observations stockées | 0 | 100 |
| Montant retenu des contrats | 1582645.00 | 1582645.00 |

Montants identiques : **oui**. Les observations GPS vivent dans `iot_observations`, jamais dans `contract_lines`.

## Journal des lots IoT

| Fichier | Statut | Insérées | Traité le |
|---|---|---:|---|
| observations.jsonl | CHARGE | 50 | 04/11/2026 22:20:26 |
| observations.jsonl | CHARGE | 50 | 04/11/2026 22:20:26 |
| observations.jsonl | REJETE_STRUCTURE | 0 | 04/11/2026 22:20:27 |

## Limites

Ce bonus ne prétend pas remplacer une plateforme IoT : pas de file de messages, pas de TLS, pas de gestion de parc de boîtiers. Il montre la chaîne complète (acquisition, contrôles, clé d'idempotence, rejeu, panne) sur des fichiers locaux reproductibles.

