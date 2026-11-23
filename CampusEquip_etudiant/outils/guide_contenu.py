"""Contenu du guide de projet (texte structuré, rendu par outils/guide.py).

Les blocs sont volontairement simples : titre, paragraphe, liste, code, tableau,
encadré, image. Le rendu Markdown et le rendu DOCX partagent exactement le même
contenu, donc les deux versions ne peuvent pas diverger.
"""
from __future__ import annotations

# Types de blocs :
#   ('couverture', titre, sous_titre, lignes)
#   ('h1', texte) / ('h2', texte) / ('h3', texte)
#   ('p', texte) / ('ul', [éléments]) / ('ol', [éléments])
#   ('code', texte) / ('table', entetes, lignes)
#   ('note', titre, texte) / ('image', chemin, largeur_cm, legende)
#   ('saut',)


def contenu() -> list[tuple]:
    return [
        ('couverture',
         'CampusEquip',
         'Guide complet du projet — axes 1 et 2',
         [
             ('Projet', 'Pipeline de locations : SQL analytique et contrôle qualité'),
             ('Livrable', 'Code, base PostgreSQL, tableau de bord, preuves et rapport'),
             ('Version', 'campusequip-v2.0'),
             ('Remise', '21 novembre 2026'),
             ('Binôme', 'à compléter avant impression'),
         ]),

        ('h1', 'Comment utiliser ce guide'),
        ('p', "Ce document explique le projet dans l’ordre où il se construit : le besoin, "
              "le modèle, les règles, le chargement, les analyses, le tableau de bord, puis "
              "l’exploitation. Il se lit à trois moments."),
        ('ul', [
            "Avant la démonstration : les sections 1 à 9 pour comprendre et savoir refaire.",
            "Le jour de la démo : la section 11 donne le déroulé minuté et les commandes exactes.",
            "Devant le jury : les sections 12 et 13 contiennent le discours et les réponses "
            "aux questions les plus probables.",
        ]),
        ('note', 'Trois règles à garder en tête',
         "1) Aucune valeur n’est inventée pour « réparer » une donnée : une ligne douteuse part "
         "en quarantaine avec son motif.\n"
         "2) Une ligne invalide isole tout son contrat : un contrat à moitié chargé fausserait "
         "les montants.\n"
         "3) Rien n’est annoncé comme réussi sans une preuve exécutée : un test, un rapport, "
         "une requête, une capture."),

        ('h2', 'Sommaire'),
        ('table',
         ['§', 'Section', 'Ce qu’on y trouve'],
         [['1', 'Le projet en bref', 'contexte, questions, périmètre, barème, livrables'],
          ['2', 'Architecture', 'rôle de chaque module, circulation d’un lot'],
          ['3', 'Modèle de données', 'grain, clés, contraintes, vue d’indicateurs'],
          ['4', 'Règles de qualité', 'structure, normalisation, doublons, quarantaine, taux'],
          ['5', 'Chargement et rejeu', 'signature, journal, transaction, conflit, campagne'],
          ['6', 'Analyses SQL', 'les trois analyses, contrôle de cohérence, calcul manuel'],
          ['7', 'Tableau de bord', 'pages, filtres, accès analytique en lecture seule, stress test'],
          ['8', 'Bonus', 'index, récursif, précalcul, morceaux, IoT — et leurs mesures'],
          ['9', 'Installation', 'environnement, base, vérifications, erreurs fréquentes'],
          ['10', 'Lancer et démontrer', 'séquence complète, sorties attendues, arrêt'],
          ['11', 'Démonstration jury', 'déroulé minuté, commandes, pièges'],
          ['12', 'Le discours', 'texte à prononcer, trois à quatre minutes'],
          ['13', 'Questions du jury', 'vingt-quatre questions et leurs réponses'],
          ['14', 'Checklist', 'ce qu’il faut vérifier avant de rendre'],
          ['A–C', 'Annexes', 'commandes, motifs de rejet, glossaire']], [1.3, 4.6, 8.5]),

        ('h1', '1. Le projet en bref'),
        ('p', "CampusEquip loue du matériel à des associations sur six campus, chacun avec deux "
              "guichets. Les locations arrivent par lots : un dossier contenant un CSV de "
              "lignes de contrats, un fichier de référentiels, un manifeste et un marqueur de "
              "disponibilité. Le projet transforme ces fichiers en données fiables dans "
              "PostgreSQL, puis en indicateurs SQL explicables."),
        ('h2', 'Les questions auxquelles le projet répond'),
        ('ol', [
            "Quel montant chaque campus réalise-t-il chaque jour ?",
            "Quels équipements rapportent le plus ?",
            "Les locations à l’heure et à la journée contribuent-elles de la même façon ?",
            "Quels contrats doivent être isolés parce que leurs données sont incohérentes ?",
            "Un fichier déjà traité peut-il être reçu à nouveau sans doubler les montants ?",
        ]),
        ('h2', 'Le périmètre'),
        ('p', "Ce guide documente le socle des axes 1 et 2 (10 points et jusqu’à 5 points de "
              "bonus). La seconde partie est intégrée dans axes_3_4/README.md : MongoDB, Redis, "
              "Airflow et TimescaleDB. Le bonus IoT historique reste une extension distincte."),
        ('table',
         ['Attendu du socle', 'Points'],
         [['Modèle relationnel et contraintes', '2'],
          ['Trois analyses SQL, un tableau par analyse et un graphique', '2'],
          ['Contrôles Python, quarantaine et rapport de qualité', '2'],
          ['Chargement transactionnel, rejeu, prise en charge automatique', '2'],
          ['Preuves reproductibles et compréhension individuelle', '2']], [12.6, 2.8]),
        ('h2', 'Ce qui a été livré'),
        ('ul', [
            "Un modèle PostgreSQL de huit tables et deux vues, avec contraintes de cohérence.",
            "Un pipeline Python qui lit, contrôle, isole et charge un lot en une transaction.",
            "Un journal de lots en base qui rend le rejeu possible, même après redémarrage.",
            "Trois analyses SQL avec tableaux, deux graphiques et une synthèse chiffrée.",
            "Un tableau de bord de pilotage : analyses en lecture seule et banc de charge isolé.",
            "41 tests du socle, 11 tests ciblés axes 3–4 et six preuves conservées pour les axes 1–2.",
            "Un rapport de trois pages, plus ce guide.",
            "Une extension MongoDB, Redis, Airflow et TimescaleDB documentée dans axes_3_4/README.md.",
        ]),

        ('h1', '2. Architecture et organisation du code'),
        ('p', "Le code est séparé en trois couches, ce qui permet de tester les décisions sans "
              "base de données et de remplacer la base sans toucher aux règles."),
        ('code',
         "flux_demo/lot_000001/          lot publié par le générateur\n"
         "        │\n"
         "        ├── surveiller.py       détecte les dossiers complets (marqueur READY)\n"
         "        │        └── etudiant/traitement.py   traiter_lot(dossier, manifeste)\n"
         "        │                 ├── regles.py    décisions pures (aucun SQL)\n"
         "        │                 ├── depot.py     chargement transactionnel\n"
         "        │                 └── rapports/ quarantaine/\n"
         "        │\n"
         "        ├── PostgreSQL  campusequip\n"
         "        │        ├── contrats, lignes, référentiels, journal des lots\n"
         "        │        └── v_lignes_retenues (paid/closed uniquement)\n"
         "        │\n"
         "        └── dashboard/     tableau de bord Flask, analyses en lecture seule + stress isolé"),
        ('table',
         ['Module', 'Rôle', 'Ne fait pas'],
         [['etudiant/regles.py', 'normaliser, contrôler, isoler, signer', 'aucun accès fichier ou base'],
          ['etudiant/traitement.py', 'lire un lot, produire les rapports', 'aucune décision métier'],
          ['etudiant/depot.py', 'transaction, journal, rejeu, conflits', 'aucune règle de données'],
          ['etudiant/schema.sql', 'tables, contraintes, vues', 'aucune donnée'],
          ['analyses.sql', 'les trois analyses et les contrôles', 'aucune écriture'],
          ['dashboard/', 'analyses en lecture seule; stress dans un schéma temporaire', 'aucune écriture métier'],
          ['outils/', 'installation, démo, preuves, rapport, guide', 'aucune logique métier']],
         [3.6, 7.2, 5.4]),
        ('note', 'Pourquoi cette séparation',
         "Elle rend les tests possibles sans PostgreSQL (13 tests sur les règles), elle évite "
         "qu’une règle soit dupliquée entre Python et SQL. Les pages analytiques restent en "
         "lecture seule; le banc de charge écrit uniquement dans un schéma temporaire isolé."),

        ('h1', '3. Le modèle de données'),
        ('p', "Le grain est la clé de tout le projet : chaque table répond à une seule question. "
              "Un campus a des sites, un site reçoit des contrats, un contrat porte des lignes, "
              "une ligne référence un équipement."),
        ('table',
         ['Table', 'Grain (une ligne = …)', 'Clés et contraintes'],
         [['campus', 'un campus', 'PK campus_id'],
          ['sites', 'un guichet', 'PK site_id · FK campus_id'],
          ['clients', 'une association', 'PK client_id'],
          ['categories', 'une catégorie', 'PK category_id · FK parent_id (auto-référence)'],
          ['equipments', 'un type de matériel', 'PK equipment_id · FK category_id'],
          ['contracts', 'un contrat', 'PK contract_id · FK client, site, lot'],
          ['contract_lines', 'une ligne de contrat', 'PK (contract_id, line_no) · FK équipement'],
          ['ingestion_batches', 'une tentative de traitement', 'PK batch_id · signature']]),
        ('h2', 'Les contraintes qui remplacent le contrôle humain'),
        ('ul', [
            "quantity comprise entre 1 et 100 ; unit limité à hour ou day ;",
            "duration entre 1 et 720 heures ou 1 et 365 jours selon l’unité ;",
            "unit_rate positif, au plus deux décimales, borné à numeric(12,2) ;",
            "status limité aux quatre valeurs paid, closed, draft, cancelled ;",
            "montant d’une ligne calculé par la base : quantity × duration × unit_rate.",
        ]),
        ('p', "La colonne line_amount est une colonne générée. Elle ne peut donc pas diverger du "
              "tarif historique reçu : la base recalcule le montant à chaque écriture. C’est un "
              "choix défendable devant un jury : l’indicateur et la donnée de base sont la même "
              "vérité, pas deux calculs parallèles."),
        ('h2', 'La vue d’indicateurs'),
        ('p', "Toutes les analyses lisent v_lignes_retenues, qui filtre les contrats paid et "
              "closed et joint le site, le campus et l’équipement. Une seule définition du "
              "périmètre, donc aucun risque qu’une analyse compte un contrat brouillon."),
        ('code',
         "CREATE VIEW v_lignes_retenues AS\n"
         "SELECT l.*, c.start_date, c.site_id, s.campus_id, c.client_id, c.status\n"
         "FROM contract_lines l\n"
         "JOIN contracts c USING (contract_id)\n"
         "JOIN sites s ON s.site_id = c.site_id\n"
         "WHERE c.status IN ('paid', 'closed');"),
        ('note', 'Question fréquente : pourquoi ne pas stocker le montant du contrat ?',
         "Parce qu’un contrat peut avoir plusieurs lignes avec des unités et des tarifs "
         "différents. Le stocker obligerait à le recalculer à chaque modification de ligne. "
         "La colonne générée par ligne, plus la somme à la lecture, restent justes dans tous les cas."),

        ('h1', '4. Les règles de qualité, une par une'),
        ('p', "Le pipeline applique toujours le même ordre : structure du lot, normalisation, "
              "répétitions exactes, contrôles de ligne, cohérence du contrat, quarantaine, "
              "chargement. Changer cet ordre change les compteurs, donc le taux de rejet."),
        ('h2', '4.1 Refuser la structure avant de lire les données'),
        ('p', "Un lot est refusé en bloc — statut REJETE_STRUCTURE — si un fichier manque, si le "
              "manifeste ne décrit pas exactement les deux sources, si une empreinte SHA-256 ne "
              "correspond pas, ou si l’en-tête du CSV n’est pas exactement les onze colonnes "
              "dans l’ordre. Rien n’est écrit : même pas les référentiels."),
        ('table',
         ['Colonne', 'Règle appliquée', 'Exemple refusé'],
         [['contract_id', 'entier > 0, chiffres seuls', '0, −3, 12a'],
          ['client_id / site_id / equipment_id', 'entier > 0 et présent au référentiel', '999999'],
          ['start_date', 'YYYY-MM-DD et date réelle', '2026-02-30'],
          ['status', 'paid, closed, draft, cancelled', 'PAID ? (accepté après minuscule)'],
          ['line_no', 'entier > 0', '0'],
          ['quantity', 'entier de 1 à 100', '−1, 0, 101'],
          ['unit', 'hour ou day', 'week'],
          ['duration', '1–720 h ou 1–365 j', '721 heures'],
          ['unit_rate', 'décimal, ≤ 2 décimales, ≥ 0', '25.555, 1,5, 1e3']], [3.4, 6.4, 5.2]),
        ('h2', '4.2 Ne jamais réparer une valeur'),
        ('p', "La normalisation se limite à ce que le sujet autorise : retirer les espaces "
              "périphériques et passer status et unit en minuscules. Une virgule décimale n’est "
              "pas remplacée par un point, un tarif à trois décimales n’est pas arrondi. Le "
              "tarif est lu avec Decimal, jamais avec float, pour éviter les erreurs d’arrondi "
              "sur les montants."),
        ('h2', '4.3 Dédoublonner avant de contrôler'),
        ('p', "Une répétition exacte est une ligne identique sur les onze colonnes après "
              "normalisation. Elle est retirée et comptée une seule fois dans le taux de rejet. "
              "Dédoublonner sur contract_id serait une faute : deux lignes d’un même contrat ne "
              "sont pas des copies."),
        ('h2', '4.4 Isoler tout le contrat, pas la ligne'),
        ('p', "C’est la règle la plus importante du sujet. Une seule ligne invalide met toutes "
              "les lignes du contrat en quarantaine, avec deux motifs : le motif propre de la "
              "ligne fautive, et le motif CONTRAT_EN_QUARANTAINE sur ses voisines, qui rappelle "
              "la ligne responsable. Un contrat à moitié chargé produirait un montant faux."),
        ('code',
         "position 5  contrat 902  QUANTITY_INVALIDE: « -1 » n'est pas un entier\n"
         "position 6  contrat 902  CONTRAT_EN_QUARANTAINE: ligne 5 invalide "
         "(QUANTITY_INVALIDE), tout le contrat est isolé"),
        ('h2', '4.5 L’exception de la quantité 25'),
        ('p', "Une quantité supérieure à 20 est acceptée : la ligne est écrite et une anomalie "
              "est signalée. Elle n’entre ni dans les rejets, ni dans le taux, ni dans la "
              "quarantaine. C’est une demande de revue, pas un refus."),
        ('h2', '4.6 Le taux de rejet et l’alerte'),
        ('p', "Taux = lignes en quarantaine ÷ lignes après dédoublonnage × 100. Le numérateur et "
              "le dénominateur comptent une seule fois les répétitions exactes. Si le "
              "dénominateur est nul, le taux vaut 0 %. Au-delà de 20 %, une alerte est levée : "
              "les contrats valides sont quand même chargés, les contrats fautifs restent en "
              "quarantaine. Le seuil déclenche une revue, il ne bloque pas le flux."),
        ('note', 'Ce qu’il faut savoir répondre : « pourquoi 25 passe et −1 non ? »',
         "−1 viole le domaine de la quantité (1 à 100) : la ligne est inutilisable. 25 est "
         "utilisable mais inhabituelle : la refuser ferait perdre une location réelle. Le sujet "
         "choisit donc de la charger en la signalant, et de laisser un humain décider."),

        ('h1', '5. Chargement transactionnel, rejeu et concurrence'),
        ('h2', '5.1 La signature d’un lot'),
        ('p', "La signature est un SHA-256 calculé sur la concaténation de la version des règles "
              "et des empreintes SHA-256 des deux fichiers. Le nom du dossier et le nom des "
              "fichiers n’entrent pas dans le calcul : un lot redéposé sous un autre nom est "
              "donc reconnu comme déjà traité."),
        ('code',
         "signature = sha256( RULES_VERSION + '|' + sha256(locations.csv) + '|' "
         "+ sha256(referentiels.json) )"),
        ('h2', '5.2 Le journal est la seule référence'),
        ('p', "La table ingestion_batches contient une ligne par tentative traitée, avec les "
              "compteurs, la signature et le statut. Un index unique partiel interdit deux "
              "chargements de la même signature, tout en laissant la trace d’un lot refusé en "
              "structure. Après un redémarrage du surveilleur, c’est le journal SQL — pas la "
              "mémoire du programme — qui empêche le double chargement."),
        ('h2', '5.3 Une seule transaction par lot'),
        ('p', "Journal, référentiels (au premier lot), contrats, lignes, quarantaine et anomalies "
              "sont écrits dans la même transaction. Si une étape échoue, tout est annulé : "
              "aucun lot à moitié chargé, et aucun journal qui annonce un succès partiel."),
        ('h2', '5.4 Le conflit entre deux lots'),
        ('p', "Si un nouveau lot réutilise un contract_id déjà chargé, la transaction entière "
              "échoue. Le pipeline ne remplace jamais un contrat existant : il lève une erreur "
              "explicite, le surveilleur l’affiche et retente le lot. Le journal précédent "
              "reste intact, ce qui est la preuve attendue par le sujet."),
        ('h2', '5.5 Une seule campagne par base'),
        ('p', "Au premier chargement réussi, la base mémorise le campaign_id et l’empreinte "
              "canonique des référentiels. Tout lot d’une autre campagne, ou dont les "
              "référentiels ont changé, est refusé en structure. Pour une nouvelle campagne, "
              "on crée une base neuve et un nouveau dossier de flux."),
        ('table',
         ['Statut renvoyé', 'Quand', 'Effet en base'],
         [['CHARGE', 'lot valide', 'journal + contrats + lignes + quarantaine'],
          ['DEJA_CHARGE', 'signature déjà chargée', 'aucune écriture métier'],
          ['REJETE_STRUCTURE', 'structure, campagne ou référentiels', 'journal de refus seulement'],
          ['erreur levée', 'conflit de contrat ou panne', 'transaction annulée, échec visible']],
         [3.4, 5.6, 6.4]),

        ('h1', '6. Les analyses SQL'),
        ('p', "Les trois analyses sont dans analyses.sql, exécutables telles quelles avec psql "
              "ou via python -m outils.analyses. Chacune commence par un commentaire "
              "@resultat qui permet au lanceur de nommer ses exports."),
        ('h2', '6.1 Montant par date et par campus'),
        ('p', "generate_series produit une ligne par jour du 1er au 21 novembre, y compris les "
              "jours sans location : ils apparaissent à zéro au lieu de disparaître. Le cumul "
              "est calculé par campus avec une fonction de fenêtre ordonnée par date."),
        ('code',
         "sum(coalesce(t.montant, 0)) OVER (\n"
         "    PARTITION BY c.campus_id ORDER BY j.jour\n"
         ") AS cumul_campus"),
        ('h2', '6.2 Équipements les plus contributeurs'),
        ('p', "Le classement utilise DENSE_RANK et non ROW_NUMBER : deux équipements à égalité "
              "de montant obtiennent le même rang, comme demandé. Un ROW_NUMBER les "
              "départagerait arbitrairement."),
        ('h2', '6.3 Heure ou journée'),
        ('p', "La comparaison porte sur des montants en MAD et sur le nombre de lignes, campus "
              "par campus. On n’additionne jamais des heures et des jours : la durée est déjà "
              "exprimée dans l’unité de la ligne, et le tarif est un tarif par unité."),
        ('h2', '6.4 Le contrôle de cohérence'),
        ('p', "Une requête compare le total de la vue, le total reconstitué par l’analyse A1 et "
              "celui de l’analyse A3. Les trois doivent être égaux : c’est la preuve qu’aucune "
              "analyse ne double-compte ni n’oublie une ligne."),
        ('table',
         ['Contrôle', 'Résultat observé'],
         [['Total de la vue retenue', '1 582 645,00 MAD'],
          ['Total A1 (somme des jours)', '1 582 645,00 MAD'],
          ['Total A3 (somme des unités)', '1 582 645,00 MAD'],
          ['Contrats stockés / retenus', '1 104 / 663']], [10.6, 4.4]),
        ('h2', '6.5 Le calcul à la main'),
        ('p', "La preuve preuves/calcul_manuel.md reprend un contrat réel et refait "
              "l’arithmétique : 4 × 1 × 15 = 60, 1 × 1 × 33 = 33, 1 × 1 × 268 = 268, soit "
              "361 MAD. Le total renvoyé par la vue SQL est identique. C’est la démonstration "
              "que la formule du sujet est bien celle qui est appliquée."),

        ('h1', '7. La console de pilotage'),
        ('p', "La console est une application Flask locale. Ses pages analytiques lisent PostgreSQL "
              "en lecture seule; une page de stress test facultative exécute le pipeline dans un "
              "schéma temporaire séparé. Ce n’est pas un simple tableau : c’est une interface "
              "animée qui rend les indicateurs, les bonus et les performances lisibles."),
        ('table',
         ['Page', 'Ce qu’on y voit', 'Ce qu’on y démontre'],
         [['Console', 'KPI animés, flux de revenu jour/cumul, jauge qualité, carte de chaleur '
                      'campus × jour, soleil des catégories, top équipements, pipeline, activité',
           'les trois questions du sujet en un écran'],
          ['Contrats', 'liste filtrable et fiche détaillée avec calcul ligne à ligne',
           'le grain et les statuts'],
          ['Qualité', 'taux, motifs, quarantaine, anomalies', 'les décisions de rejet sont traçables'],
          ['Laboratoire', 'les quatre bonus mesurés en direct', 'index, morceaux, précalcul, IoT'],
          ['Stress test', 'paliers de débit, qualité, latence, backlog et ressources', 'le pipeline est mesuré sans modifier les données métier'],
          ['Lots', 'journal, base, source IoT, activité', 'le rejeu et l’exploitation']],
         [3.0, 7.4, 6.0]),
        ('h2', '7.1 Ce qui la rend vivante'),
        ('ul', [
            "compteurs animés : chaque indicateur monte de zéro à sa valeur ;",
            "figures dessinées à l’ouverture (tracé de la courbe, barres qui poussent, arc de "
            "la jauge), avec des délais en cascade ;",
            "infobulles au survol sur chaque point, chaque case de la carte de chaleur et chaque "
            "segment du soleil des catégories ;",
            "changement de période ou de campus sans rechargement brutal : la vue se fond grâce "
            "aux View Transitions du navigateur ;",
            "fil d’activité rafraîchi toutes les 30 secondes, pastille « live » pulsée ;",
            "bascule jour / cumul instantanée, et respect du réglage « réduire les animations ».",
        ]),
        ('h2', '7.2 Les bonus dans l’interface'),
        ('p', "La page Laboratoire ne raconte pas les bonus : elle les exécute. Le lecteur par "
              "morceaux relit un vrai lot par tranches et compare ses décisions à la lecture "
              "complète ; le comparateur interroge la vue matérialisée et le calcul direct puis "
              "mesure les deux ; les mesures d’index viennent du script de preuve ; la carte IoT "
              "agrège les observations réellement stockées."),
        ('h2', '7.3 Comment elle se connecte'),
        ('p', "Les pages analytiques utilisent la même variable DATABASE_URL que le pipeline et "
              "ouvrent une session PostgreSQL READ ONLY. Le stress test ouvre une connexion "
              "séparée pour créer un schéma temporaire unique, y installer le schéma du projet, "
              "puis supprimer ce schéma après l’exécution. Le rôle doit avoir le droit CREATE "
              "sur la base pour lancer un test; les tables métier et les campagnes existantes "
              "ne sont jamais modifiées."),
        ('code',
         "$env:DATABASE_URL = \"postgresql://campusequip@127.0.0.1:5432/campusequip\"\n"
         "python -m dashboard.app --port 5055\n"
         "# puis http://127.0.0.1:5055"),
        ('h2', '7.4 Les partis pris techniques'),
        ('ul', [
            "aucun framework CSS, aucune bibliothèque de graphiques, aucune ressource réseau : "
            "les figures sont des SVG générés par le serveur, la page fonctionne hors ligne ;",
            "les pages analytiques sont en lecture seule; seul le stress test écrit dans son "
            "schéma temporaire isolé, sans toucher aux données métier ;",
            "les filtres de période et de campus s’appliquent à toutes les pages et se propagent "
            "dans la navigation ;",
            "les chiffres viennent des mêmes vues que les analyses SQL, donc ils ne peuvent pas "
            "diverger du rapport.",
        ]),
        ('image', 'docs/captures/console_guide.png', 16.2,
         'Console : indicateurs animés, flux de revenu, jauge qualité, carte de chaleur, '
         'catégories, pipeline et activité.'),
        ('image', 'docs/captures/labo_guide.png', 16.2,
         'Laboratoire : lecture par morceaux, précalcul contre demande, plans d’index et carte '
         'des boîtiers GPS.'),

        ('h1', '8. Les bonus réalisés'),
        ('p', "Quatre extensions du barème ont été réalisées et mesurées. Chacune a son script "
              "de preuve et son rapport dans preuves/."),
        ('h2', '8.1 Index et plans d’exécution (+1)'),
        ('p', "Sur un volume de 250 000 contrats et 500 000 lignes, la même requête est mesurée "
              "avant et après un index partiel sur (start_date) WHERE status IN ('paid','closed'). "
              "Sur un comptage d’activité, le gain est de ×15 ; sur une agrégation de montants, "
              "le gain est nul, car le plan balaie les lignes. C’est la leçon la plus utile : "
              "un index ne corrige que la partie du coût qu’il adresse."),
        ('h2', '8.2 Catégories récursives et précalcul (+1)'),
        ('p', "WITH RECURSIVE reconstruit l’arbre des catégories et remonte les montants vers la "
              "catégorie racine. En parallèle, une vue matérialisée stocke le montant jour × "
              "campus ; une requête compare le précalcul au calcul à la demande et doit renvoyer "
              "zéro écart. C’est la preuve que les deux chemins donnent la même réponse."),
        ('h2', '8.3 Lecture par morceaux (+1)'),
        ('p', "Un lecteur de flux lit le CSV par tranches de 100, 1 000 ou 10 000 lignes. Les "
              "décisions qui demandent tout le lot — cohérence d’un contrat, calcul des montants "
              "— sont prises à la fin, par la même fonction que la lecture complète. Les quatre "
              "lectures produisent exactement les mêmes décisions, aux mêmes positions."),
        ('h2', '8.4 Source IoT simulée (+2)'),
        ('p', "Un producteur écrit des observations GPS fictives (device_id, event_id, "
              "equipment_id, observed_at, latitude, longitude). Le collecteur contrôle "
              "l’équipement, l’instant UTC et les bornes géographiques, puis insère avec la clé "
              "(device_id, event_id). Un rejeu identique n’ajoute rien, un contenu contradictoire "
              "est rejeté avec un motif, et un fichier tronqué est refusé en bloc sans insertion "
              "partielle. Les observations vivent dans une table séparée : les montants des "
              "contrats sont inchangés avant et après."),

        ('h1', '9. Installation pas à pas'),
        ('h2', '9.1 Prérequis'),
        ('ul', [
            "Python 3.10 ou plus (testé avec 3.14).",
            "PostgreSQL 13 ou plus (testé avec 17), avec un rôle disposant du droit de créer la base.",
            "Aucun accès Internet nécessaire : les dépendances se limitent à psycopg2 et Pillow.",
        ]),
        ('h2', '9.2 Environnement Python'),
        ('code',
         "cd CampusEquip_etudiant\n"
         "python -m venv .venv\n"
         ".venv\\Scripts\\Activate.ps1        # Windows PowerShell\n"
         "# source .venv/bin/activate        # macOS / Linux\n"
         "pip install -r requirements.txt"),
        ('h2', '9.3 Base de données'),
        ('code',
         "-- avec psql, une seule fois :\n"
         "CREATE ROLE campusequip LOGIN PASSWORD 'mot-de-passe-local';\n"
         "CREATE DATABASE campusequip OWNER campusequip;\n"
         "\n"
         "-- puis, depuis le dossier du projet :\n"
         "$env:DATABASE_URL = \"postgresql://campusequip@127.0.0.1:5432/campusequip\"\n"
         "python -m outils.init_base --reinitialiser"),
        ('p', "Le mot de passe n’est jamais écrit dans un fichier remis : il vit dans la variable "
              "d’environnement, ou dans un fichier .env local ignoré par git (voir .env.exemple)."),
        ('h2', '9.4 Vérifier l’installation'),
        ('code',
         "python -m outils.init_base --verifier\n"
         "python -m unittest discover -s tests -t .\n"
         "python -m outils.demo"),
        ('h2', '9.5 Les erreurs fréquentes'),
        ('table',
         ['Message', 'Cause', 'Solution'],
         [['connection refused', 'PostgreSQL arrêté ou mauvais port', 'démarrer le service, vérifier DATABASE_URL'],
          ['database "campusequip" does not exist', 'base non créée', 'python -m outils.init_base'],
          ['password authentication failed', 'rôle ou mot de passe', 'recréer le rôle, vérifier .env'],
          ['campagne refusée', 'base déjà liée à une autre campagne', 'créer une base neuve'],
          ['générateur déjà actif', 'verrou résiduel .generator.lock', 'vérifier qu’aucun générateur ne tourne, puis retirer le verrou'],
          ['ModuleNotFoundError: psycopg2', 'environnement virtuel inactif', 'activer .venv puis réinstaller']],
         [4.6, 5.2, 5.6]),

        ('h1', '10. Lancer le projet et faire la démonstration'),
        ('h2', '10.1 La séquence complète, de zéro'),
        ('code',
         "# 1. base neuve et schéma\n"
         "python -m outils.init_base --reinitialiser\n"
         "\n"
         "# 2. génération de quatre lots de 300 contrats (profil mixte)\n"
         "python generer.py --sortie flux_demo --contrats 300 --lots 4 --profil mixte "
         "--intervalle 0 --graine 42\n"
         "\n"
         "# 3. chargement automatique par le surveilleur\n"
         "python surveiller.py --entree flux_demo --une-fois --intervalle 1\n"
         "\n"
         "# 4. rejeu : les mêmes lots doivent être reconnus\n"
         "python surveiller.py --entree flux_demo --une-fois --intervalle 1\n"
         "\n"
         "# 5. analyses, tableaux et graphiques\n"
         "python -m outils.analyses\n"
         "\n"
         "# 6. tableau de bord\n"
         "python -m dashboard.app --port 5055"),
        ('p', "La commande python -m outils.demo enchaîne les étapes 1 à 5 et affiche un bilan "
              "lot par lot. C’est la commande à utiliser si vous êtes pressé."),
        ('h2', '10.2 Ce que l’on doit voir'),
        ('table',
         ['Étape', 'Sortie attendue'],
         [['Chargement', '4 lignes CHARGE, de 549 à 553 lignes acceptées par lot'],
          ['Rejeu', '4 lignes DEJA_CHARGE avec lignes_ajoutees_en_base = 0'],
          ['Base', '1 104 contrats, 2 203 lignes stockées, 1 317 lignes retenues'],
          ['Analyses', '126 lignes A1 (6 campus × 21 jours), 609 lignes A2, 12 lignes A3'],
          ['Montant', '1 582 645 MAD, dont 72,6 % à la journée']], [3.4, 10.6]),
        ('h2', '10.3 Arrêter et reprendre'),
        ('p', "Ctrl+C dans chaque terminal. Les fichiers sont conservés, le journal aussi. "
              "Relancer le surveilleur sur le même dossier reprend au lot suivant sans jamais "
              "recharger un lot déjà traité. Ne supprimez jamais generator-state.json pour "
              "« forcer » une reprise : cela réutiliserait des identifiants déjà chargés."),

        ('h1', '11. La démonstration devant le jury'),
        ('p', "Objectif : dix minutes, sans temps mort, avec des preuves visibles à l’écran. "
              "Préparez trois fenêtres : un terminal, le tableau de bord, et un éditeur ouvert "
              "sur le dossier rapports/."),
        ('h2', '11.1 Déroulé minuté'),
        ('table',
         ['Temps', 'Ce que vous faites', 'Ce que vous dites'],
         [['0:00', 'page Vue d’ensemble', '« CampusEquip loue du matériel sur six campus ; nous transformons chaque lot en données fiables et en indicateurs. »'],
          ['0:45', 'KPI + graphique', '« Sur quatre lots, 1 104 contrats, 1,58 million de MAD, dont 72,6 % à la journée. »'],
          ['1:30', 'page Contrats → un contrat', '« Chaque montant est recalculable : 4 × 1 × 15 = 60, etc. Le total est 361 MAD. »'],
          ['2:30', 'terminal : rejeu', '« Le même lot, redéposé, est reconnu DEJA_CHARGE : zéro ligne ajoutée. »'],
          ['3:30', 'preuves/TESTS.md', '« Douze essais du sujet, chacun avec son attendu et son observé. »'],
          ['4:30', 'terminal : structure invalide', '« En-tête incorrect : lot refusé, aucune écriture métier, refus tracé. »'],
          ['5:30', 'terminal : conflit', '« Contrat déjà chargé dans un nouveau lot : transaction annulée, journal intact. »'],
          ['6:30', 'page Qualité', '« 96 contrats isolés, 248 lignes ; la quantité 25 reste acceptée et signalée. »'],
          ['7:30', 'bonus en une phrase', '« Index ×15 sur un comptage, récursif, lecture par morceaux, IoT avec rejeu et panne. »'],
          ['9:00', 'conclusion', '« Ce que nous ne savons pas faire : détecter une ligne jamais reçue, ou prouver un encaissement. »']],
         [1.6, 6.2, 9.0]),
        ('h2', '11.2 Les commandes à taper en direct'),
        ('code',
         "# rejeu : les quatre lots sont déjà chargés, rien ne doit être ajouté\n"
         "python surveiller.py --entree flux_demo --une-fois --intervalle 1\n"
         "\n"
         "# structure invalide : en-tête incorrect, lot refusé avant écriture\n"
         "python -m outils.demo_cas --cas structure\n"
         "\n"
         "# conflit inter-lots : contract_id déjà chargé, transaction annulée\n"
         "python -m outils.demo_cas --cas conflit"),
        ('note', 'Pourquoi deux scripts plutôt qu’une manipulation à la main',
         "Ces deux cas écrivent leurs lots dans .demo/ et ne touchent jamais exemples/ : la "
         "copie du kit reste intacte et la démonstration est rejouable autant de fois que "
         "nécessaire. Ils supposent que la base de démonstration est déjà chargée "
         "(python -m outils.demo)."),
        ('h2', '11.3 Les pièges à éviter'),
        ('ul', [
            "Ne lancez pas deux surveillants sur la même base pendant la démo.",
            "Vérifiez que DATABASE_URL est définie dans le terminal où vous tapez les commandes.",
            "Ne montrez pas un chiffre que vous ne savez pas expliquer : préparez trois chiffres "
            "seulement (1 104 contrats, 1 582 645 MAD, 72,6 %).",
            "Si une commande échoue, lisez le message à voix haute : un échec visible est prévu "
            "par le sujet, ce n’est pas un incident.",
        ]),

        ('h1', '12. Le discours'),
        ('p', "Trois à quatre minutes, à prononcer avant la démonstration technique. Le texte "
              "ci-dessous est écrit pour être dit, pas lu : gardez les nombres, adaptez les mots."),
        ('p', "« Notre projet part d’un constat simple : les fichiers de locations arrivent "
              "sales. Des lignes répétées, des quantités négatives, des clients inconnus, des "
              "contrats dont deux lignes se contredisent. Si on charge tout, les montants sont "
              "faux ; si on supprime tout, on perd des locations réelles."),
        ('p', "Nous avons donc construit un pipeline qui décide, ligne par ligne, puis contrat "
              "par contrat. D’abord la structure : si l’en-tête n’est pas exactement celui "
              "attendu, le lot est refusé avant la moindre écriture. Ensuite la normalisation, "
              "limitée à ce que le sujet autorise : pas de valeur inventée, pas d’arrondi "
              "silencieux, un tarif lu en Decimal. Puis le dédoublonnage des copies exactes. "
              "Enfin les contrôles : références, dates, quantités, durées, tarifs, et cohérence "
              "de l’en-tête du contrat."),
        ('p', "La règle centrale est celle de la quarantaine : une seule ligne invalide isole "
              "tout son contrat. Un contrat à moitié chargé produirait un montant faux, et un "
              "mauvais chiffre est plus dangereux qu’une ligne manquante. Les lignes isolées "
              "sont conservées avec leurs valeurs brutes et leurs motifs, dans un fichier et "
              "dans la base."),
        ('p', "Le chargement tient en une transaction : journal du lot, contrats, lignes, "
              "quarantaine. Si une seule étape échoue, rien n’est conservé. Et pour répondre à "
              "la question du rejeu : chaque lot a une signature calculée sur le contenu des "
              "deux fichiers et la version des règles. Un lot déjà vu, même renommé, est "
              "reconnu et n’ajoute rien. C’est le journal SQL, pas la mémoire du programme, qui "
              "garantit cela après un redémarrage."),
        ('p', "Côté analyse, trois questions : le montant par jour et par campus avec les jours "
              "à zéro, les équipements les plus contributeurs avec des rangs ex æquo, et la "
              "comparaison heure / journée. Un seul périmètre : les contrats payés et clôturés, "
              "et un montant rattaché à la date de début."),
        ('p', "Enfin, nous avons ajouté un tableau de bord dont les pages analytiques restent "
              "en lecture seule, ainsi qu’un banc de charge isolé pour mesurer le pipeline, "
              "et quatre extensions mesurées : un index dont nous montrons "
              "le plan avant et après, une analyse récursive des catégories, une lecture par "
              "morceaux qui prend exactement les mêmes décisions, et une chaîne IoT simulée "
              "avec rejeu et panne."),
        ('p', "Ce que nous ne faisons pas : nous ne détectons pas une ligne jamais reçue, et "
              "nous ne prouvons pas un encaissement bancaire. Le statut payé est une convention "
              "du sujet, pas une preuve comptable. »"),

        ('h1', '13. Questions probables du jury'),
        ('p', "Les réponses sont volontairement courtes : trois à cinq phrases, un exemple, un "
              "chiffre. Si la question dépasse le projet, dites ce que vous savez et ce que vous "
              "feriez ensuite."),
        ('h2', '13.1 Modèle et SQL'),
        ('p', "Q. Pourquoi une table contracts séparée de contract_lines ?"),
        ('p', "R. Parce que le grain n’est pas le même : un contrat porte un client, un site, une "
              "date et un statut, une ligne porte un équipement, une quantité, une durée et un "
              "tarif. Si on mettait tout dans une seule table, ces quatre colonnes seraient "
              "répétées sur chaque ligne, et rien n’empêcherait deux lignes d’un même contrat de "
              "se contredire. La séparation rend la contradiction détectable."),
        ('p', "Q. Pourquoi le montant est-il une colonne générée ?"),
        ('p', "R. Pour qu’il ne puisse pas diverger du tarif reçu. La base recalcule "
              "quantity × duration × unit_rate à chaque écriture ; il n’y a pas deux calculs à "
              "maintenir. Le revers, c’est qu’on ne peut pas stocker un montant négocié "
              "différent : ce n’est pas demandé ici."),
        ('p', "Q. Pourquoi DENSE_RANK et pas ROW_NUMBER ?"),
        ('p', "R. Le sujet demande que les égalités aient le même rang. ROW_NUMBER départagerait "
              "deux montants égaux par un ordre arbitraire ; DENSE_RANK leur donne le même rang "
              "et le rang suivant reste contigu."),
        ('p', "Q. Comment affichez-vous les jours sans location ?"),
        ('p', "R. generate_series produit les 21 dates, puis un LEFT JOIN avec les totaux et un "
              "coalesce à zéro. Sans cela, un jour sans location disparaîtrait du graphique, ce "
              "qui laisse croire à une absence de données plutôt qu’à une absence de ventes."),
        ('p', "Q. Pourquoi une vue plutôt qu’une table d’indicateurs ?"),
        ('p', "R. Parce qu’une vue ne peut pas être désynchronisée : elle est recalculée à la "
              "lecture. Une table d’agrégats demanderait un rafraîchissement après chaque lot, "
              "et c’est précisément le genre d’oubli qui produit un tableau de bord faux. La vue "
              "matérialisée n’existe que pour le bonus de comparaison précalcul / à la demande."),
        ('h2', '13.2 Qualité des données'),
        ('p', "Q. Pourquoi isoler tout le contrat et pas seulement la ligne ?"),
        ('p', "R. Parce que le montant d’un contrat est la somme de ses lignes. Si on garde deux "
              "lignes sur trois, le total est faux et rien ne le signale. Le sujet impose cette "
              "règle ; nous l’avons vérifiée par un test où une ligne valide est rejetée parce "
              "que sa voisine a une quantité négative, avec le motif CONTRAT_EN_QUARANTAINE."),
        ('p', "Q. Une quantité de 25 n’est-elle pas une erreur de saisie ?"),
        ('p', "R. Peut-être, mais ce n’est pas certain : une association peut louer 25 chaises. "
              "Refuser la ligne ferait perdre une location réelle ; la charger sans rien dire "
              "ferait passer une anomalie inaperçue. Le compromis du sujet — accepter et "
              "signaler — est le bon : un humain décide ensuite."),
        ('p', "Q. Pourquoi dédoublonner avant de contrôler ?"),
        ('p', "R. Parce que le taux de rejet se calcule après dédoublonnage. Une copie exacte "
              "n’est pas une erreur de données, c’est un artefact de transport. La compter comme "
              "un rejet gonflerait artificiellement le taux et déclencherait des alertes inutiles."),
        ('p', "Q. Comment le taux de rejet est-il calculé, et que se passe-t-il à 20 % ?"),
        ('p', "R. Rejets divisés par lignes après dédoublonnage, en pourcentage, zéro si le "
              "dénominateur est nul. Au-delà de 20 %, le lot est marqué en alerte mais les "
              "contrats valides sont chargés : le seuil sert à déclencher une revue, pas à "
              "bloquer l’activité. Nous l’avons prouvé sur un cas construit à 30 %."),
        ('p', "Q. Et si une ligne manque dans le fichier ?"),
        ('p', "R. Nous ne pouvons pas la détecter : le manifeste donne un nombre de lignes, pas "
              "le contenu attendu. Si le fichier est tronqué, l’empreinte SHA-256 ne correspond "
              "plus et le lot est refusé. Si la troncature est produite en amont puis re-hachée, "
              "seule une comparaison de volume avec les lots précédents le révélerait : c’est "
              "une limite que nous assumons."),
        ('h2', '13.3 Rejeu, transactions et concurrence'),
        ('p', "Q. Comment reconnaissez-vous un lot déjà traité ?"),
        ('p', "R. Par une signature SHA-256 calculée sur les empreintes des deux fichiers et la "
              "version des règles. Le nom du dossier n’y entre pas, donc un lot renommé est "
              "reconnu. La signature est unique dans le journal pour les lots chargés."),
        ('p', "Q. Que se passe-t-il si le programme s’arrête au milieu du chargement ?"),
        ('p', "R. La transaction est annulée par PostgreSQL : soit tout est écrit, soit rien. Au "
              "redémarrage, le surveilleur relit le dossier ; si le lot avait été validé, la "
              "signature est dans le journal et il répond DEJA_CHARGE."),
        ('p', "Q. Pourquoi le journal est-il en base et pas dans un fichier ?"),
        ('p', "R. Parce qu’il doit être écrit dans la même transaction que les données. Un "
              "fichier peut être écrit puis la transaction échouer, ou l’inverse : le journal "
              "mentirait. En base, journal et contrats réussissent ou échouent ensemble."),
        ('p', "Q. Que faites-vous si deux lots réutilisent le même contract_id ?"),
        ('p', "R. Le chargement échoue : nous ne remplaçons jamais un contrat existant, et nous "
              "ne laissons pas un lot partiel. L’erreur remonte au surveilleur, qui l’affiche et "
              "retente le lot. Le journal du lot précédent reste intact."),
        ('p', "Q. Deux surveillants en même temps ?"),
        ('p', "R. Le sujet prévoit un seul consommateur. Nous avons malgré tout un verrou "
              "consultatif PostgreSQL au début de la transaction : le second attend. Ce n’est "
              "pas un ordonnanceur distribué, juste une ceinture de sécurité."),
        ('h2', '13.4 Python et exploitation'),
        ('p', "Q. Pourquoi Decimal et pas float ?"),
        ('p', "R. Un float ne représente pas exactement 0,1 ; sur des milliers de lignes, les "
              "centimes dérivent. Decimal est exact et c’est aussi le type NUMERIC de PostgreSQL, "
              "donc le montant calculé en Python et celui calculé en base donnent le même résultat."),
        ('p', "Q. Pourquoi ne pas avoir utilisé pandas ?"),
        ('p', "R. Le volume d’un lot ne le justifie pas, et le sujet demande de raisonner ligne à "
              "ligne sur la structure et les motifs. La bibliothèque standard suffit et rend le "
              "comportement explicite. Le bonus de lecture par morceaux montre d’ailleurs qu’un "
              "traitement en flux est possible sans dépendance."),
        ('p', "Q. Où sont les rapports et les rejets ?"),
        ('p', "R. Un rapport JSON et Markdown par tentative dans rapports/, un fichier JSONL par "
              "lot dans quarantaine/ avec la position, les valeurs brutes et les motifs, et une "
              "trace en base dans batch_rejections et batch_anomalies. Le plus lisible pour un "
              "audit est le rapport Markdown."),
        ('p', "Q. Comment changez-vous de campagne ?"),
        ('p', "R. Nouvelle base et nouveau dossier de flux. Le premier lot mémorise la campagne "
              "et l’empreinte des référentiels ; tout autre campaign_id est refusé dans la même "
              "base, pour éviter de mélanger des identifiants qui ne sont uniques que dans leur "
              "campagne."),
        ('h2', '13.5 Limites et recul critique'),
        ('p', "Q. Quelle est la principale faiblesse de votre pipeline ?"),
        ('p', "R. Il ne détecte pas une ligne absente, et il suppose les référentiels fixes par "
              "campagne. Une deuxième faiblesse est la concurrence : un seul consommateur est "
              "prévu. Enfin, la quarantaine est un arrêt de traitement, pas une correction : "
              "quelqu’un doit reprendre les contrats isolés à la main."),
        ('p', "Q. Que feriez-vous avec deux semaines de plus ?"),
        ('p', "R. Trois choses, dans cet ordre : un contrôle de volume par rapport aux lots "
              "précédents pour détecter une troncature silencieuse ; une reprise assistée des "
              "contrats en quarantaine avec correction et rejeu ; et un vrai suivi de fraîcheur "
              "pour alerter si aucun lot n’arrive depuis trop longtemps."),
        ('p', "Q. Le tableau de bord peut-il fausser les chiffres ?"),
        ('p', "R. Les pages analytiques lisent les mêmes vues que les analyses, en session "
              "READ ONLY, et ne calculent rien à part des pourcentages d’affichage. Le stress "
              "test est distinct : il écrit uniquement dans un schéma temporaire isolé. Le contrôle de "
              "cohérence des trois totaux est dans analyses.sql, pas dans l’interface."),

        ('h1', '14. Checklist avant la remise'),
        ('ul', [
            "Les noms du binôme sont renseignés dans le README et dans le rapport.",
            "python -m unittest discover -s tests -t . affiche OK avec PostgreSQL de test disponible.",
            "python -m outils.valider va au bout sans erreur.",
            "rapports/ contient au moins un DEJA_CHARGE avec lignes_ajoutees_en_base = 0.",
            "preuves/ contient tests_unittest.txt, calcul_manuel.md, alerte.md, index_synthese.md.",
            "Aucun mot de passe, aucune URL personnelle dans les fichiers remis.",
            "Le sujet et le kit distribués sont conservés (docs/README_kit.md).",
            "Chaque membre sait expliquer une jointure, une décision de qualité et un montant.",
        ]),

        ('h1', 'Annexe A — Commandes utiles'),
        ('table',
         ['Commande', 'Effet'],
         [['python -m outils.init_base --reinitialiser', 'base neuve et schéma'],
          ['python -m outils.demo', 'démo complète : lots, chargement, rejeu, analyses'],
          ['python -m outils.analyses', 'tableaux CSV, Markdown et graphiques'],
          ['python -m dashboard.app --port 5055', 'tableau de bord'],
          ['python -m unittest discover -s tests -t .', 'tests du socle et des axes 3–4'],
          ['python -m outils.preuve_calcul', 'calcul d’un contrat à la main'],
          ['python -m outils.preuve_alerte', 'cas à 30 % de rejet'],
          ['python -m outils.preuve_bonus', 'récursif et précalcul'],
          ['python -m outils.preuve_index', 'plans avant/après index'],
          ['python -m outils.preuve_morceaux', 'lecture par morceaux'],
          ['python -m outils.preuve_iot', 'chaîne IoT simulée'],
          ['python -m outils.demo_cas --cas structure', 'lot à en-tête incorrect (démo)'],
          ['python -m outils.demo_cas --cas conflit', 'contrat déjà chargé (démo)'],
          ['python -m dashboard.app --port 5055', 'tableau de bord'],
          ['python -m outils.rapport', 'régénère RAPPORT.md et RAPPORT.docx'],
          ['python -m outils.guide', 'régénère ce guide']], [7.8, 7.0]),

        ('h1', 'Annexe B — Motifs de rejet'),
        ('table',
         ['Code', 'Signification', 'Portée'],
         [['QUANTITY_INVALIDE', 'quantité absente, non entière ou hors 1–100', 'contrat isolé'],
          ['DURATION_INVALIDE', 'durée hors bornes de l’unité', 'contrat isolé'],
          ['UNIT_INVALIDE', 'unité autre que hour ou day', 'contrat isolé'],
          ['UNIT_RATE_INVALIDE', 'tarif négatif, mal formé ou à 3 décimales', 'contrat isolé'],
          ['START_DATE_INVALIDE', 'date non ISO ou inexistante', 'contrat isolé'],
          ['STATUS_INVALIDE', 'statut hors des quatre valeurs', 'contrat isolé'],
          ['CLIENT_INCONNU / SITE_INCONNU / EQUIPEMENT_INCONNU', 'référence absente', 'contrat isolé'],
          ['CLE_LIGNE_EN_CONFLIT', 'même (contract_id, line_no), contenu différent', 'contrat isolé'],
          ['ENTETE_CONTRAT_CONTRADICTOIRE', 'client, site, date ou statut différent', 'contrat isolé'],
          ['CONTRAT_EN_QUARANTAINE', 'ligne saine isolée à cause d’une autre ligne', 'contrat isolé'],
          ['COLONNES_INCOHERENTES', 'ligne sans les onze colonnes', 'ligne + contrat'],
          ['QUANTITE_ELEVEE', 'quantité > 20 (anomalie, pas rejet)', 'ligne acceptée']],
         [5.4, 6.6, 3.4]),

        ('h1', 'Annexe C — Glossaire'),
        ('table',
         ['Terme', 'Définition dans ce projet'],
         [['Lot', 'dossier complet publié par le générateur, avec marqueur READY'],
          ['Campagne', 'série de lots issus du même dossier et des mêmes référentiels'],
          ['Quarantaine', 'lignes rejetées, conservées avec valeurs brutes et motifs'],
          ['Signature', 'SHA-256 des deux empreintes et de la version des règles'],
          ['Rejeu', 'traitement du même contenu une seconde fois, sans double chargement'],
          ['Anomalie', 'ligne acceptée mais signalée pour revue'],
          ['Vue retenue', 'v_lignes_retenues : contrats paid et closed uniquement']], [3.4, 11.4]),
    ]
