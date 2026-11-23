# Kit événements CampusEquip

Python 3.10 ou plus, bibliothèque standard uniquement. Aucun service lancé par ce kit.

Exportez depuis votre propre table de contrats acceptés une seule colonne CSV nommée contract_id. Exemple SQL à adapter au nom réel de votre table : SELECT contract_id FROM contracts ORDER BY contract_id. Exportez le résultat avec en-tête depuis votre client PostgreSQL. Ne prenez pas le CSV brut de locations : il contient éventuellement des contrats rejetés.

Lancement depuis ce dossier :

```text
python generer_evenements.py --contrats contrats_acceptes.csv --sortie campagne --profil propre --lots 3
python generer_evenements.py --contrats contrats_acceptes.csv --sortie campagne --profil mixte --lots 3 --intervalle 2
```

Ctrl+C arrête proprement. Relancer avec le même export et dossier reprend après les lots publiés. Pour une nouvelle population, choisir un nouveau dossier de campagne. Un verrou évite deux producteurs concurrents. Après arrêt brutal, vérifier qu’aucun producteur ne tourne avant de retirer .lock. Les dossiers .pending incomplets restent ignorés ; conserver les lots publiés immuables. L’export est identifié par empreinte ; une modification demande une nouvelle campagne. Les dossiers publiés font autorité pour le prochain numéro, y compris après un arrêt juste après publication.

Chaque lot propre contient cinq événements. Un lot mixte contient dix lignes : les cinq événements propres, une copie exacte, un conflit de clé, un événement tardif valide, une référence inconnue et un horodatage impossible. Le consommateur doit expliquer chaque décision ; le générateur ne charge aucune base. Le manifeste contient schema_version, campaign_id, batch_no, profile, rows, contracts_sha256 et files (empreintes SHA-256). La publication est un renommage atomique sur le même système de fichiers ; cela ne constitue pas une garantie de résistance à une coupure électrique.

Une fixture mixte supplémentaire est fournie dans `demo_evenements/lot-000001`.
Elle est volontairement hors du dossier surveillé `axes_3_4/flux` : elle ne sera
pas ingérée automatiquement par Airflow. Pour la traiter manuellement, démarrez
les services et vérifiez que les contrats de `axes_3_4/flux/contrats_acceptes.csv`
sont présents dans PostgreSQL, puis lancez depuis la racine du projet :

```powershell
python -m axes_3_4.cli traiter-lot axes_3_4/kit/demo_evenements/lot-000001
```

Cette opération écrit dans les services MongoDB/TimescaleDB ; ne la lancez que
lorsque vous souhaitez réellement faire la démonstration d'ingestion.

Les deux lots propres de exemples/campagne utilisent le contrat pédagogique2001 des exemples du kit initial. Ils ne prouvent pas qu’il est accepté dans votre campagne ; vérifiez sa présence avant ingestion. Le fichier exemples/contrats_acceptes.csv représente cette hypothèse pédagogique.

MongoDB : historique immuable et identité composite. Redis : dernier état, TTL et classement des incidents/pannes. Le DAG final avec capteur READY, contrôle d’empreintes, fonctions métier, retries et dépendances est dans `../dags/campus_evenements.py` ; `dag_a_completer.py` redirige vers cette implémentation. TimescaleDB : observations de position et mesures des tentatives. Les quatre systèmes n’ont pas de transaction globale : conserver des écritures idempotentes et une procédure de réconciliation.

## Contrat des événements terrain

Le kit actuel utilise exactement six champs : `device_id`, `event_id`, `contract_id`, `event_type`, `observed_at`, `payload`. Il remplace pour cette seconde partie le format historique source/status/event_time. La clé est `(device_id, event_id)`, deux chaînes ASCII non vides contenant lettres, chiffres, tirets ou underscores. `contract_id` est un entier positif, hors booléens, présent parmi les contrats réellement acceptés. `observed_at` est un instant UTC réel au format YYYY-MM-DDTHH:MM:SSZ. `payload` est un objet JSON.

`event_type` appartient à withdrawal (retrait), return (retour), incident, failure (panne), position. Pour position, payload contient exactement latitude et longitude, nombres finis dans [-90,90] et [-180,180]. Ce sont des positions fictives, jamais des coordonnées personnelles. Pour les quatre autres types, payload est un objet de détails sans effet sur le montant commercial.

Comparer le contenu normalisé (espaces périphériques des identifiants et type, type en minuscules, clés JSON triées). Une copie exacte ne crée aucune insertion. Un conflit de clé conserve la première version acceptée et produit un rejet individuel. Toute autre valeur invalide est rejetée individuellement. Vérifier l’empreinte du fichier avant toute écriture. Conserver les sources et motifs.

Le dernier événement par contrat suit observed_at décroissant puis device_id et event_id décroissants. Pour le dernier état opérationnel et la file, exclure position avant ce calcul ; un incident ou une panne place le contrat dans la file, un retour plus récent l’en retire. Les positions restent dans l’historique et alimentent les mesures temporelles, avec leurs unités. Redis conserve le dernier état avec TTL 60 secondes et la file reconstruisible ; le cache de montant SQL par date reste également demandé. MongoDB conserve tous les événements acceptés. TimescaleDB conserve les mesures de position et les tentatives du pipeline. Aucun événement ne modifie automatiquement les montants SQL.
