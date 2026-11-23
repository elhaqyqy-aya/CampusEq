# CampusEquip sous Docker

La pile Docker Compose démarre l'application des axes 1–2 et les services des
axes 3–4 : PostgreSQL, MongoDB, Redis, TimescaleDB et Airflow. Aucun Python ni
service de base de données n'est à installer sur la machine.

---

## 1. Démarrer

Dans PowerShell, ouvrez le dossier `CampusEquip_etudiant` (celui qui contient
`docker-compose.yml`), puis lancez :

```bash
docker compose up -d --build
```

Puis ouvrir **http://localhost:5055**.

Si les ports par défaut sont déjà utilisés, créez un fichier `.env` à côté de
`docker-compose.yml` et indiquez par exemple :

```dotenv
POSTGRES_HOST_PORT=5434
APP_HOST_PORT=5056
```

La console sera alors disponible sur **http://localhost:5056** et PostgreSQL
sur le port **5434**. Pour le lancement habituel, aucune configuration `.env`
n'est nécessaire.

Au premier démarrage, le conteneur `app` :

1. attend que PostgreSQL réponde (`pg_isready`) ;
2. vérifie si la base contient déjà des contrats ;
3. si elle est vide : applique `etudiant/schema.sql`, génère 4 lots de
   300 contrats, les charge, rejoue les mêmes lots, puis lance les analyses ;
4. démarre la console sur `0.0.0.0:5055`.

Suivre le démarrage :

```bash
docker compose logs -f app
```

Vous devez voir, dans l'ordre :

```text
Attente de PostgreSQL — prêt.
Base vide : application du schéma…
Schéma appliqué (…). 12 objets vérifiés.
Chargement du jeu de démonstration (4 lots)…
…
Console CampusEquip sur http://0.0.0.0:5055
```

### Frontend connecté

Après le démarrage de la pile, démarrez le frontend séparé :

```powershell
docker compose --env-file .env -f app/docker-compose.yml up -d
```

Ouvrez **http://localhost:5173**. Le frontend transmet les requêtes `/api/`
à la console Flask sur `APP_HOST_PORT` (5055 par défaut). Le nouvel endpoint
`/api/prototype/snapshot` ne fait que lire les sources du projet; le navigateur
n'accède jamais directement aux bases. Si `.env` définit un port hôte
différent, les deux commandes Compose doivent être lancées depuis la racine du
projet pour utiliser le même fichier d'environnement. Les limites du schéma
(absence de stock unitaire et de dates d'échéance) sont expliquées dans
[app/README.md](app/README.md).

---

## 2. Les commandes utiles

| But | Commande |
|---|---|
| Démarrer / reconstruire | `docker compose up -d --build` |
| Voir l'état | `docker compose ps` |
| Suivre les journaux | `docker compose logs -f app` |
| Arrêter (les données restent) | `docker compose stop` |
| Arrêter et supprimer les conteneurs | `docker compose down` |
| Tout supprimer, y compris la base | `docker compose down -v` |
| Rejouer la démonstration | `docker compose run --rm app demo` |
| Relancer les analyses SQL | `docker compose run --rm app analyses` |
| Lancer les tests du socle | `docker compose run --rm app tests` |
| Ouvrir un shell dans l'image | `docker compose run --rm app sh` |
| Console psql | `docker compose exec db psql -U campusequip -d campusequip` |
| Régénérer le rapport | `docker compose run --rm app python -m outils.rapport` |
| Régénérer le guide | `docker compose run --rm app python -m outils.guide` |
| Voir les preuves | `docker compose run --rm app python -m outils.valider` |

Exemples SQL utiles :

```bash
docker compose exec db psql -U campusequip -d campusequip -c "\dt"
docker compose exec db psql -U campusequip -d campusequip -c \
  "select batch_number, status, rows_accepted, rejection_rate from ingestion_batches order by batch_id;"
```

---

## 3. Se connecter depuis un client SQL (pgAdmin, DBeaver)

PostgreSQL est publié sur le port **5433** de la machine hôte (pour ne pas
entrer en conflit avec un PostgreSQL déjà installé sur 5432).

| Paramètre | Valeur |
|---|---|
| Hôte | `localhost` |
| Port | `5433` |
| Base | `campusequip` |
| Utilisateur | `campusequip` |
| Mot de passe | `campusequip` |

Ces identifiants sont ceux d'une **démonstration locale** : ils sont écrits dans
`docker-compose.yml` pour que la pile démarre sans configuration. Pour un usage
réel, passez-les en variables d'environnement ou dans un fichier `.env` non
versionné.

---

## 4. Ce que contient la pile

```text
docker-compose.yml
├── db    postgres:17-alpine
│         volume nommé campusequip_pgdata  → les données survivent à un « down »
│         port 5433 → 5432
├── app          image construite depuis ./docker/app.Dockerfile
├── mongodb      image mongo:7.0 (port hôte 27018)
├── redis        image redis:7.4-alpine (port hôte 6380)
├── timescaledb  image timescale/timescaledb (port hôte 5435)
└── airflow      image construite depuis ./docker/airflow-axes34.Dockerfile

Code organisé par responsabilité :
CampusEquip_etudiant/
├── docker/
│   ├── app.Dockerfile
│   └── airflow-axes34.Dockerfile
└── axes_3_4/
    ├── cache/             → Redis
    ├── storage/           → dépôts MongoDB/PostgreSQL et TimescaleDB
    └── orchestration/     → DAG et adaptateur Airflow
```

Le service app conserve aussi les volumes montés :

```text
./rapports      → rapports de lots (JSON + Markdown)
./quarantaine   → lignes rejetées et motifs (JSONL)
./resultats     → CSV, Markdown, graphiques PNG
campusequip_flux → dossier flux_demo (nécessaire à la démo « morceaux »)
```

L'image ne contient que le code et les dépendances Python
(`psycopg2-binary`, `Pillow`, `python-docx`) : elle fonctionne hors ligne.

---

## 5. Réglages

| Variable | Effet |
|---|---|
| `AUTO_DEMO=0` | n'injecte pas le jeu de démonstration (base vide, schéma seul) |
| `PORT` | port interne de la console (défaut 5055) |
| `APP_HOST_PORT` | port de la console sur votre machine (défaut 5055) |
| `POSTGRES_HOST_PORT` | port PostgreSQL sur votre machine (défaut 5433) |
| `MONGODB_HOST_PORT` | port MongoDB sur votre machine (défaut 27018) |
| `REDIS_HOST_PORT` | port Redis sur votre machine (défaut 6380) |
| `TIMESCALE_HOST_PORT` | port TimescaleDB sur votre machine (défaut 5435) |
| `CAMPUSEQUIP_RAPPORTS` / `CAMPUSEQUIP_QUARANTAINE` | dossiers de sortie |
| `DATABASE_URL` | connexion complète (déjà positionnée par Compose) |

Exemple, démarrer sans données de démonstration :

```bash
AUTO_DEMO=0 docker compose up -d --build
docker compose run --rm app init --reinitialiser   # schéma seul
```

> Sous Windows, utilisez plutôt un fichier `.env` à côté de `docker-compose.yml` :
> `AUTO_DEMO=0`.

---

## 6. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `port is already allocated` sur 5055 | une console tourne encore en local | définir `APP_HOST_PORT=5056` dans `.env` |
| `port is already allocated` sur 5433 | un autre PostgreSQL utilise ce port | définir `POSTGRES_HOST_PORT=5434` dans `.env` |
| `Base déjà initialisée : schéma et données conservés.` | normal après le premier démarrage | rien à faire ; `docker compose run --rm app demo` pour recharger |
| Permission denied sur `rapports/` (Linux) | l'utilisateur du conteneur (uid 1000) n'écrit pas dans le dossier hôte | `sudo chown -R $USER rapports quarantaine resultats` |
| Le conteneur redémarre en boucle | la base n'est pas prête ou `DATABASE_URL` est fausse | `docker compose logs db` puis `docker compose logs app` |
| Le code a changé mais pas l'image | cache de construction | `docker compose up -d --build --force-recreate` |

Après une modification du code, la commande à retenir est toujours :

```bash
docker compose up -d --build
```

---

## 8. Axes 3–4 : événements, cache et orchestration

Depuis ce même dossier, démarrez les services complémentaires avec :

```powershell
docker compose up -d --build
```

Cette commande démarre également la pile existante. Airflow est disponible sur
**http://localhost:8080** ; consultez `docker compose logs airflow`
pour son premier démarrage. MongoDB écoute sur `27018`, Redis sur `6380` et
TimescaleDB sur `5435`, tous liés à l'interface locale. Ces ports évitent le
conflit avec les ports courants et avec le PostgreSQL principal. Les données
restent dans des volumes nommés.

Le parcours complet — export des contrats acceptés, production des événements,
activation du DAG, lectures MongoDB, cache Redis, incidents et mesures
TimescaleDB — est décrit dans **[axes_3_4/README.md](axes_3_4/README.md)**.
Les commandes de base restent inchangées :

```powershell
docker compose ps
docker compose logs -f airflow
docker compose stop
docker compose down
```

`docker compose down` conserve les données. `docker compose down -v` supprime
aussi les volumes, y compris les bases de démonstration.

Le prototype frontend autonome se lance séparément avec
`docker compose -f app/docker-compose.yml up -d` et est servi sur
http://localhost:5173. Il ne se connecte à aucune base et ne modifie pas la pile
des services de données. Consultez [app/README.md](app/README.md).

---

## 7. Vérifier que tout fonctionne

```bash
curl http://localhost:5055/api/sante
# {"base":"campusequip","contrats":1104,"lots":4,"ok":true,"version":"17.x"}

docker compose run --rm app tests
# Tous les tests disponibles … OK
```

La même base peut ensuite être interrogée depuis psql, pgAdmin ou le notebook
de votre choix, sans jamais toucher au pipeline.
