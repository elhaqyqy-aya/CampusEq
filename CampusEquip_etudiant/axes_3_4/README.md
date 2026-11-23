# CampusEquip — axes 3 et 4

Cette extension complète le pipeline PostgreSQL des axes 1–2 sans remplacer
ses contrats, ses règles de qualité, ses indicateurs ni son rejeu transactionnel.
MongoDB garde l'historique des événements, Redis sert des projections
reconstructibles, Airflow orchestre les tâches et TimescaleDB stocke les
positions fictives et les mesures de tentatives.

## 1. Démarrer les services

Docker Desktop doit être démarré. Depuis `CampusEquip_etudiant` :

```powershell
docker compose up -d --build
docker compose ps
```

Compose démarre PostgreSQL, MongoDB, Redis, TimescaleDB, l'application et
Airflow en une seule fois. PostgreSQL reste le système de référence pour les
contrats et les montants. Les ports locaux par défaut sont :

| Service | Adresse locale | Données |
|---|---|---|
| PostgreSQL axes 1–2 | `localhost:5433` par défaut | `campusequip` |
| MongoDB | `localhost:27018` | événements, rejets et journal des lots |
| Redis | `localhost:6380` | cache et projections temporaires |
| TimescaleDB | `localhost:5435` | positions et tentatives |
| Airflow | <http://localhost:8080> | interface et planification |

MongoDB, Redis et TimescaleDB sont exposés uniquement sur l'interface locale.
Les ports MongoDB, Redis et TimescaleDB sont volontairement différents des
ports courants pour éviter les conflits avec les installations locales et le
port PostgreSQL des axes 1–2. Ils restent personnalisables dans `.env` avec
`MONGODB_HOST_PORT`, `REDIS_HOST_PORT` et `TIMESCALE_HOST_PORT`.

Airflow utilise son mode `standalone` d'apprentissage et une base SQLite
interne ; ce n'est pas une configuration de production. Consultez
`docker compose logs airflow` pour le démarrage et les informations du premier
compte Airflow.

Les services conservent leurs données dans des volumes nommés. `docker compose
down` arrête les conteneurs sans effacer ces données. N'utilisez
`docker compose down -v` que si vous voulez détruire les volumes de démonstration.

## 2. Publier des lots de test

Attendez que la pile soit prête, puis exportez **les contrats réellement présents
dans PostgreSQL**, et non le CSV brut qui peut contenir des contrats rejetés :

```powershell
python -m axes_3_4.cli exporter-contrats --sortie axes_3_4/flux/contrats_acceptes.csv
python axes_3_4/kit/generer_evenements.py `
  --contrats axes_3_4/flux/contrats_acceptes.csv `
  --sortie axes_3_4/flux --profil mixte --lots 3 --intervalle 2
```

Le producteur fourni publie les lots dans `axes_3_4/flux/lot-*` par renommage
atomique et écrit `READY` en dernier. Ne modifiez pas les lots publiés et ne
consommez pas les dossiers `.pending-*`. `mixte` produit des événements valides,
une copie, un conflit, un événement tardif, un contrat inconnu et une date
impossible ; les valeurs GPS sont fictives.

Airflow recherche les lots `READY` toutes les minutes. Dans l'interface,
activez le DAG `campusequip_evenements`. Le capteur attend au plus une heure,
ignore les dossiers incomplets et ne met pas les données des événements dans
XCom. Une seule exécution de lot est active à la fois. Si un lot de locations
axes 1–2 doit être chargé par le DAG, placez-le sous `axes_3_4/locations/` et
définissez `CAMPUSEQUIP_LOCATION_BATCH` sur son chemin dans le conteneur (par
exemple `/opt/airflow/location_batches/lot-000001`) dans `.env` avant de
démarrer Airflow. Sinon, le DAG utilise les contrats déjà chargés et contrôle
chaque référence au moment de l'ingestion des événements.

## 2.1 Organisation des fichiers

Les composants sont rangés par responsabilité, sans mélanger les scripts avec
les fichiers d'infrastructure :

```text
axes_3_4/
├── cache/                 # cache et projections Redis
├── storage/               # dépôts MongoDB/PostgreSQL et TimescaleDB
├── orchestration/
│   ├── dags/              # DAG Airflow
│   └── airflow_support.py
├── flux/                  # lots d'événements publiés
└── locations/             # lots optionnels des axes 1–2
docker/
├── app.Dockerfile
└── airflow-axes34.Dockerfile
docker-compose.yml         # point d'entrée Compose à la racine
```

## 3. Exécuter localement ou refaire une preuve

Pour exécuter les commandes Python sur l'hôte, installez les dépendances
facultatives et configurez les quatre URL :

```powershell
pip install -r requirements.txt
pip install -r axes_3_4/requirements.txt
$env:DATABASE_URL = "postgresql://campusequip:campusequip@127.0.0.1:5433/campusequip"
$env:MONGODB_URL = "mongodb://127.0.0.1:27018"
$env:REDIS_URL = "redis://127.0.0.1:6380/0"
$env:TIMESCALE_URL = "postgresql://campusequip:campusequip@127.0.0.1:5435/campusequip_ts"
python -m axes_3_4.cli initialiser-timescale
```

Exemples de lectures et de rejeu :

```powershell
python -m axes_3_4.cli traiter-lot axes_3_4/flux/lot-000001
python -m axes_3_4.cli historique 2001
python -m axes_3_4.cli dernier 2001
python -m axes_3_4.cli suivi-enrichi 2001
python -m axes_3_4.cli tentatives-evenements <campaign_id> 1
python -m axes_3_4.cli montant-jour 2026-11-01
python -m axes_3_4.cli montant-jour 2026-11-01 --publier
python -m axes_3_4.cli actualiser-cache
python -m axes_3_4.cli reconstruire-incidents
python -m axes_3_4.cli file-incidents
python -m axes_3_4.cli etat-operationnel 2001
python -m axes_3_4.cli tentatives `
  --debut 2026-11-01T00:00:00Z --fin 2026-11-02T00:00:00Z
```

`traiter-lot` peut être relancé sur la même source : une copie valide augmente
le compteur des copies, mais aucune seconde insertion métier n'est faite. Les
conflits de `(device_id, event_id)` gardent le premier document MongoDB et
créent un rejet avec son motif. Les événements valides des autres lignes sont
conservés. Le rapport sépare `accepted`, `copies`, `conflicts`, `rejected` et
`inserted`; `accepted = inserted + copies`. Chaque tentative d'ingestion est
conservée séparément dans `event_ingestion_attempts`, tandis que `event_batches`
représente le dernier état traité du lot.

Pour vérifier le cache, lisez deux fois une date (`MISS`, puis `HIT`), attendez
61 secondes puis relisez-la (`MISS`). Après le chargement d'un lot de locations,
`actualiser-cache` supprime les anciennes clés de dates et republie les montants
calculés depuis PostgreSQL ; son résultat donne les nombres de clés invalidées
et de dates réchauffées. Le DAG effectue cette même invalidation/actualisation
après l'étape de chargement des locations.

## 4. Responsabilités et choix de données

* **PostgreSQL** reste la source des contrats et de l'indicateur financier :
  seuls `paid` et `closed` sont comptés, et le montant est rattaché à
  `start_date`. Un `return` ne modifie ni statut ni montant.
* **MongoDB** conserve un document par événement accepté, avec l'identité
  unique `(device_id, event_id)`, le document normalisé, le texte UTC source
  `observed_at` et sa date BSON UTC `observed_at_date`. Les fonctions
  `historique_contrat`, `dernier_evenement` et `suivi_enrichi` fournissent les
  lectures ordonnée, récente et enrichie. Cette dernière réalise explicitement
  la jointure MongoDB/PostgreSQL en Python.
* **Redis** stocke le montant journalier comme chaîne décimale, sous
  `campusequip:axe34:montant:YYYY-MM-DD`, TTL 60 secondes. Les lectures
  distinguent `MISS`, `HIT`, `UNAVAILABLE` et `BYPASS`. Si Redis est en panne,
  une lecture peut relire PostgreSQL ; une erreur PostgreSQL remonte et n'est
  jamais remplacée par zéro. Une tâche de publication Redis échoue si Redis
  n'est pas disponible.
* La clé Redis `campusequip:axe34:incidents` est un sorted set des derniers
  événements opérationnels (`position` exclu) de type `incident` ou `failure`.
  Le score est l'instant UTC ; Redis départage les scores égaux par membre
  lexicographique (identifiant de contrat sérialisé). La projection entière
  peut être reconstruite depuis MongoDB ; un retour plus récent retire le
  contrat sans effacer l'incident historique.
* **TimescaleDB** conserve les positions avec latitude/longitude en degrés et
  les tentatives avec date UTC, DAG, run, tâche, numéro d'essai, statut et
  durée en millisecondes. L'agrégation utilise des fenêtres UTC de cinq minutes
  semi-ouvertes `[début, fin)`, le taux d'erreur est `erreurs / tentatives`,
  et la durée moyenne est en millisecondes. Les fenêtres sans observation ne
  sont pas matérialisées. Le capteur Airflow n'est pas instrumenté : sa durée
  d'attente n'est pas une tentative métier.

Les écritures entre PostgreSQL, MongoDB, Redis et TimescaleDB n'ont pas de
transaction globale. Les événements sont écrits d'abord dans MongoDB ;
l'écriture Timescale est idempotente et un rejeu répare une mesure manquante.
Redis est une projection recalculable. Les tâches ayant des erreurs temporaires
ont deux reprises bornées après l'essai initial ; l'intégrité de lot a zéro
reprise et une location refusée échoue explicitement. Si une panne survient après
le commit PostgreSQL,
le rejeu des locations utilise le journal existant et ne recharge pas les
contrats. Si une projection manque, relancez `reconstruire-incidents` après
avoir réparé Redis.

## 5. Tests

Depuis `CampusEquip_etudiant` :

```powershell
python -m unittest tests.test_axes_3_4 -v
python -m unittest discover -s tests -t . -v
docker compose config --quiet
```

Les tests Python vérifient le contrat des événements, les références,
l'empreinte, les lots publiés et l'ordre déterministe sans prétendre avoir
exécuté les services. Les tests d'intégration MongoDB/Redis/TimescaleDB s'effectuent avec les
services lancés par `docker compose up -d --build`.
