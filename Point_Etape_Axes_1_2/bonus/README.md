# Bonus CampusEquip

Ce dossier regroupe les bonus réalisés en plus des livrables des axes 1 et 2 :

- scripts SQL d'indexation, de catégories récursives et de précalcul ;
- lecture par morceaux ;
- producteur, collecteur et schéma IoT ;
- tableau de bord Flask complet dans `dashboard/`, y compris sa page et son moteur de simulation GPS ;
- application frontend et visualisation du pipeline dans `app/`.

Les dossiers `dashboard/` et `app/` sont des copies des sources de
`CampusEquip_etudiant/`. Pour les exécuter, utilisez le projet complet afin de
disposer des dépendances, de la configuration et des services :

```powershell
Set-Location ..\..\CampusEquip_etudiant
docker compose up -d --build
docker compose -f app/docker-compose.yml up -d
```

Le tableau de bord Flask est servi sur le port 5055 et l'application frontend
sur le port 5173. La simulation GPS utilise des données fictives et le schéma
isolé `gps_sim`; elle est accessible depuis le tableau de bord.
Si vous avez créé un fichier `.env` et souhaitez l'utiliser explicitement,
ajoutez `--env-file .env` à la commande du frontend.
