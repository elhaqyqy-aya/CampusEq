# Point d'étape — axes 1 et 2

Ce dossier rassemble les livrables et les sources du projet CampusEquip.

- `01_Modele_Donnees/` : schéma relationnel en PDF et dictionnaire généré à partir de `03_Code/schema.sql`.
- `02_Calcul_Contrat/` : preuve PDF du calcul manuel du contrat 7, comparé au total SQL.
- `03_Code/` : schéma PostgreSQL, analyses SQL, traitement d'un lot et programme de surveillance.
- `04_Rapport_Premier_Lot/` : rapport JSON du lot 4 chargé, sa synthèse PDF et deux captures du tableau de bord montrant le chargement et PostgreSQL.
- `bonus/` : scripts SQL et Python complémentaires, exemples IoT, tableau de bord Flask, application frontend et simulation GPS.

Les PDF et le classeur de données sont produits depuis les éléments du projet disponibles. Le rapport du lot est dérivé du JSON conservé dans le même dossier.

Les sources complètes et exécutables sont dans [`../CampusEquip_etudiant/`](../CampusEquip_etudiant/). Pour démarrer la pile principale, utilisez son [`DOCKER.md`](../CampusEquip_etudiant/DOCKER.md) et son [`docker-compose.yml`](../CampusEquip_etudiant/docker-compose.yml), depuis le dossier `CampusEquip_etudiant`. Les Dockerfiles requis sont dans `docker/`; le frontend a son propre `app/docker-compose.yml`. Les copies dans `bonus/` servent à remettre les bonus avec le point d'étape, et non à remplacer le dossier racine d'exécution.
