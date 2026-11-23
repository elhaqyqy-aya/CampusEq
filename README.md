# CampusEquip

Le projet complet se trouve dans [`CampusEquip_etudiant/`](CampusEquip_etudiant/).

## Démarrage avec Docker

Prérequis : Git et Docker Desktop démarré.

```powershell
git clone https://github.com/elhaqyqy-aya/CampusEq.git
Set-Location .\CampusEq\CampusEquip_etudiant
docker compose up -d --build
```

La console est disponible sur <http://localhost:5055>. Pour lancer aussi
l'application frontend, exécutez depuis `CampusEquip_etudiant` :

```powershell
docker compose -f app/docker-compose.yml up -d
```

Le frontend est disponible sur <http://localhost:5173>. Consultez
[`DOCKER.md`](CampusEquip_etudiant/DOCKER.md) pour les commandes, les ports,
le dépannage et les modes de lancement; le
[`README du projet`](CampusEquip_etudiant/README.md) décrit les axes, le
dashboard et la simulation GPS.

Les services utilisent une configuration locale de démonstration par défaut.
Ne publiez jamais votre fichier `.env`; `.env.exemple` documente les réglages
personnalisables.
