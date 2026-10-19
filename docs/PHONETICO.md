# NEWT / Phonetico — périmètre livré

Documentation examinée : NEWT PBX API, révision 3 du 6 mai 2026 (PDF fourni par le client). Le document est une spécification fournisseur, pas une autorisation de lancer des appels. Contrainte utilisateur en vigueur : strictement aucun appel.

## Associations locales

Utilisateurs et accès → espace → Postes Phonetico : association manuelle setter/numéro de poste. Un seul PBX, un poste global par compte, unicité du poste ; motif et révision pour modifier/retirer. Aucun lien n’est créé à partir du nom PBX. Un setter multi-espaces exige l’administration de ses deux espaces actifs pour changer son association.

## Annuaire fournisseur en lecture seule

Bouton explicite Consulter l’annuaire NEWT. Le backend appelle uniquement HTTPS https://newtapi.fibernetics.ca/cgi-bin/fnpapi avec fonction 343, format CSV et corrélation aléatoire de dix caractères hexadécimaux. Aucun sélecteur de fonction dans l’API ou l’interface. Aucun appel au démarrage, worker ou rafraîchissement périodique. Les fonctions de composition, raccrochage, DTMF et enregistrement ne sont pas implémentées. La lecture 244 limitée ci-dessous est séparée de l’annuaire.

Configuration exclusivement serveur : NEWT_DIRECTORY_ENABLED=false par défaut, NEWT_USERNAME et NEWT_PASSWORD vides dans l’exemple. Renseigner les secrets hors Git puis activer explicitement pour une recette de lecture autorisée. Les valeurs reçues dans la conversation ne sont pas copiées dans la configuration ou le dépôt par ce lot. TLS vérifié, Basic Auth, aucune redirection, délais de connexion/lecture et limite de taille (256 Kio) ; erreur fournisseur neutralisée. Limite 2000 postes, CSV UTF-8, trois colonnes strictes ; numéros uniques, nom borné. Adresse PBX ignorée et jamais renvoyée. Une réponse vide, tronquée/mal formée ou en erreur n’est jamais présentée comme une liste vide réussie.

Le PBX étant global sans filtre d’espace documenté, la consultation exige administration explicite Assurance ET Isolation. Une simple administration d’un espace, un setter, un conseiller ou un superutilisateur sans ces accès n’y a pas droit. POST session/CSRF sans paramètres, quota de cinq consultations par minute par utilisateur. Verrou de base centrale singleton pour sérialiser les lectures via plusieurs workers et respecter le fonctionnement transactionnel du fournisseur. Le cache de throttling doit être partagé en production pour un quota distribué.

Résultat sans cache et paginé dans l’interface (25 lignes), noms indicatifs et numéros uniquement, date de consultation. Pas de persistance de l’annuaire ou de réponse fournisseur ; audit minimal du nombre de postes consultés. Aucune modification de compte, droit, poste, association ou base métier. L’annuaire ne prouve pas le titulaire d’un poste et ne réserve pas son numéro. Les noms proviennent du PBX et sont rendus comme texte.

Migration portail 0012 requise. Le service portail reçoit les secrets via l’environnement du compose CRM ; cette configuration commune est aussi héritée par les workers centraux existants, qui n’exécutent aucune tâche NEWT. Aucune preuve de connexion réelle obtenue : tous les tests HTTP sont simulés. Aucun appel ni aucune requête fournisseur réelle effectué pendant cette livraison.

## État observé d’un poste associé (244)

Bouton manuel sur une association locale de setter actif, réservé aux administrateurs des deux espaces. Opt-in serveur indépendant NEWT_STATUS_ENABLED=false par défaut. La requête fournisseur porte exclusivement la fonction 244 et le poste enregistré, jamais un poste ou une fonction choisi dans les paramètres du navigateur. Même verrou singleton que l’annuaire et même quota de cinq lectures/minute ; aucun polling ou appel automatique.

Validation de huit colonnes CSV (neuvième vide finale tolérée), poste exact et corrélation dix caractères hexadécimaux égale à celle envoyée. Au maximum 64 Kio et 100 observations ; erreur, format partiel, autre poste, code inconnu ou corrélation absente sont un échec, jamais une disponibilité présumée. Les codes R/C/H documentés sont conservés tels quels, sans traduction en résultat d’appel tant que leur signification exacte n’est pas confirmée. Aucun numéro de destination, nom, identifiant d’appel ou d’enregistrement renvoyé ou enregistré. Résultat : codes distincts, nombre d’observations, horodatage, conclusion indeterminate systématique. Une réponse vide ne prouve pas que le poste est libre, ni qu’un numéro est actif/inactif. Aucun historique des états fournisseur ; audit minimal de la consultation. Aucune action sur les appels existants.

Tests entièrement simulés, aucune requête 244 réelle et aucun appel lancé. L’activation de la configuration pour une recette réelle reste à décider séparément.

## À livrer séparément

Vérification réelle des droits/configuration pour l’annuaire, recette de lecture 244 et remontée des journaux 511, interprétation documentée des codes et rapprochement appels/contacts. La fonction 245 et tout contrôle d’appel restent absents et soumis à une nouvelle autorisation explicite avant tout test réel. Création automatique de comptes depuis les postes reportée.
