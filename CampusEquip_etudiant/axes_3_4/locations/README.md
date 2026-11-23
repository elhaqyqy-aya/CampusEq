# Lots de locations pour Airflow

Déposez ici un dossier de lot complet des axes 1–2 (CSV, référentiels,
manifeste et `READY`) si le DAG doit aussi charger les locations. Ce dossier est
monté en lecture seule dans les workers Airflow sous
`/opt/airflow/location_batches`.

Configurez `CAMPUSEQUIP_LOCATION_BATCH` dans le fichier `.env` à côté de
`docker-compose.yml`, avec le chemin du conteneur, par exemple :

```dotenv
CAMPUSEQUIP_LOCATION_BATCH=/opt/airflow/location_batches/lot-000001
```

Sans cette variable, Airflow ne charge pas un second lot de locations : il
utilise les contrats déjà acceptés dans PostgreSQL. N'ajoutez pas de secrets
dans ce dossier.
