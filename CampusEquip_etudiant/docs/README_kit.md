# CampusEquip v2 pour les axes 1 et 2

Vous devez lire le sujet étudiant joint. Cette version remplace le kit initial de locations à la journée : ne mélangez pas ses colonnes ou ses données avec celles du kit v2. Vous devez utiliser une base PostgreSQL distincte de ShopFlow et une seule campagne par base.

## Ce qui est fourni

`generer.py` produit des locations fictives pour 6 campus, 12 guichets, 2 000 associations et 120 équipements. Il utilise uniquement la bibliothèque standard de Python 3.10 ou plus. `surveiller.py` détecte les lots complets, vérifie leurs empreintes et appelle votre traitement. `etudiant/traitement.py` et `etudiant/schema.sql` sont à compléter : le kit ne fournit pas le pipeline résolu. Vous pouvez reprendre les bibliothèques, connexions PostgreSQL et fonctions du cours.

`exemples/` contient deux lots propres de 20 contrats pour commencer. Ils ne contiennent aucun corrigé. Les schémas du sujet sont dans `visuels/`. Aucun service des axes 3 et 4 n'est nécessaire pour cette première moitié.

## Commencer petit

Depuis la racine du kit, vous devez créer une base neuve et configurer votre connexion sans inscrire de mot de passe dans les fichiers à remettre. Complétez d'abord le modèle et le traitement, puis lancez :

```text
python surveiller.py --entree exemples --une-fois
```

Le programme signale explicitement que le traitement est à compléter tant que vous n'avez pas remplacé le squelette. Vous devez vérifier vos résultats sur un petit lot avant de passer à un flux plus volumineux.

## Créer votre campagne

Pour créer deux nouveaux petits lots, utilisez :

```text
python generer.py --sortie essai --contrats 20 --lots 2 --profil propre --intervalle 0
```

Pour une nouvelle démonstration continue, utilisez un nouveau dossier ET une base neuve. Dans un premier terminal :

```text
python generer.py --sortie flux --contrats 1000 --intervalle 10
```

Dans un second terminal, après avoir complété `traiter_lot` :

```text
python surveiller.py --entree flux
```

Sans `--lots`, le générateur tourne jusqu'à Ctrl+C. `--lots 3` produit exactement trois nouveaux lots puis s'arrête. `--contrats 10000` augmente le nombre de contrats par lot ; il ne fixe pas un nombre de lignes. Vous devez conserver les mêmes paramètres `--contrats`, `--graine` et `--profil` lors d'une reprise dans un même dossier.

Les dates métier simulées vont du 1er au 21 novembre 2026. Le temps réel de génération est distinct. Les identifiants de contrats sont uniques dans une campagne et continuent après un redémarrage. Les référentiels ne changent pas au cours de la campagne.

## Rencontrer des défauts de qualité

Le profil par défaut `mixte` ajoute des répétitions exactes, quantités invalides, conflits de clé, en-têtes contradictoires, équipements inconnus et quantités anormalement élevées. Il ne fournit aucun classement des lignes acceptées ou rejetées. Vous devez écrire vos propres petits tests ciblés pour tous les cas du sujet, notamment la structure incorrecte, le taux de rejet au-delà de 20 % et le conflit inter-lots. Le profil `propre` sert au premier chargement.

## Respecter le contrat des fichiers

Chaque dossier `lot_000001` contient `locations.csv`, `referentiels.json`, `manifest.json` et `READY`. Les onze colonnes du CSV sont :

```text
contract_id,client_id,site_id,start_date,status,line_no,equipment_id,quantity,unit,duration,unit_rate
```

Le manifeste contient `schema_version`, `campaign_id`, `batch_number`, `created_at`, `contracts_requested`, `rows`, `profile` et `files`. Le champ `files` donne les SHA-256 de `locations.csv` et `referentiels.json`. Le nombre `rows` est celui des lignes physiques hors en-tête, avant dédoublonnage ; il ne garantit pas leur validité. Vous devez utiliser les deux empreintes et la version de règles pour identifier un traitement. Le manifeste assure l'intégrité des fichiers reçus, pas leur qualité métier.

La fonction `traiter_lot(dossier, manifeste)` doit renvoyer un dictionnaire avec `status` égal à `CHARGE`, `DEJA_CHARGE` ou `REJETE_STRUCTURE`. Vous devez y ajouter les compteurs utiles. Une panne ou un conflit de chargement doit lever une erreur ; il ne doit jamais être annoncé comme un succès. Le surveilleur s'arrête sur un squelette non complété. En mode continu, une erreur temporaire est affichée et le même lot est retenté avant de passer au suivant. En mode `--une-fois`, une erreur donne un code de sortie non nul.

Vous devez enregistrer le journal de rejeu dans PostgreSQL, dans la transaction des données. La liste des dossiers déjà vus par le surveilleur n'est qu'une optimisation en mémoire. Après son redémarrage, votre journal SQL doit empêcher les doubles chargements. Une seule instance du surveilleur est prévue ; la concurrence entre plusieurs consommateurs est hors périmètre.

## Arrêter et reprendre proprement

Vous devez arrêter les deux terminaux avec Ctrl+C après la démonstration. Les fichiers sont conservés et le disque peut se remplir si le générateur reste actif. Aucun programme ne supprime automatiquement vos sources.

Vous devez conserver `generator-state.json`. Une interruption peut laisser un numéro de lot inutilisé ou un dossier caché `.lot_*.en_cours` : le surveilleur l'ignore. Le générateur réserve ses numéros avant publication pour éviter leur réutilisation. Si la machine s'arrête brutalement, `.generator.lock` peut subsister. Vous devez vérifier qu'aucun générateur n'utilise ce dossier avant de retirer uniquement ce verrou résiduel. Ne supprimez pas le fichier d'état pour forcer une reprise.

Pour repartir de zéro, vous devez choisir un nouveau dossier et une base neuve. Vous ne devez jamais charger deux campagnes dans la même base de démonstration.

## Bonus IoT ou API

Vous pouvez simuler un GPS avec `device_id`, `event_id`, `equipment_id`, `observed_at`, `latitude`, `longitude`. Vous devez contrôler un identifiant d'équipement connu, un instant ISO UTC, une latitude entre -90 et 90 et une longitude entre -180 et 180. La clé `(device_id, event_id)` identifie l'observation : un rejeu identique n'ajoute rien et un contenu contradictoire est rejeté avec un motif. Vous devez stocker ces observations dans une table séparée, sans modifier les montants des contrats. Vous pouvez simuler une panne du producteur pour prouver la reprise. Aucun GPS personnel réel n'est nécessaire.

Une API constitue une autre option du même bonus, pas un bonus supplémentaire. Vous devez documenter les champs, la clé, les contrôles et le comportement en cas de panne. Une réponse enregistrée localement permet de tester sans dépendre d'un accès réseau. Les clés d'accès éventuelles ne doivent pas figurer dans les livrables.
