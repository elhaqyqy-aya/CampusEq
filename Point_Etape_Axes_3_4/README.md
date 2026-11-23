# Point d'étape — axes 3 et 4

Livrables issus du projet CampusEquip :

- `01_MongoDB/` : aperçu du modèle de documents de la collection `events` et exemples réels issus du lot d'événements 1.
- `02_Redis/` : clés du cache financier, projections d'incidents et durées de vie.
- `03_Airflow/` : diagramme du DAG et copie du DAG CampusEquip fourni.
- `04_TimescaleDB/` : résumé du modèle temporel et script SQL du schéma.

Le code source du DAG et le schéma TimescaleDB sont copiés depuis `CampusEquip_etudiant/axes_3_4`. Les documents PDF et le diagramme PNG sont des synthèses de ces sources.

Pour exécuter les axes 3 et 4 avec leurs services, utilisez le projet complet dans [`../CampusEquip_etudiant/`](../CampusEquip_etudiant/) : Docker Compose et les Dockerfiles nécessaires y sont regroupés. Depuis ce dossier, suivez [`DOCKER.md`](../CampusEquip_etudiant/DOCKER.md) ou le guide [`axes_3_4/README.md`](../CampusEquip_etudiant/axes_3_4/README.md), puis lancez `docker compose up -d --build`. Le frontend se lance séparément avec `app/docker-compose.yml`.
