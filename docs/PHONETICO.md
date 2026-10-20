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

## Diagnostic du format des journaux 511

Le PDF indique une première ligne d’en-têtes pour 511 mais ne donne pas leurs noms ni la sémantique des statuts. Cette étape n’est donc pas un historique d’appels métier : le bouton Diagnostic du format demande une fenêtre explicite de sept dates maximum, non futures, et ne retourne que noms de colonnes, empreinte de schéma et nombre de lignes. Aucun détail d’appel n’est renvoyé ou conservé. Aucune conversion de statut, attribution au setter ou rapprochement prospect n’est réalisée.

NEWT_CDR_SCHEMA_ENABLED=false par défaut, activation indépendante des lectures 343/244. Hôte HTTPS et fonction 511 fixes, paramètres _sd/_ed générés depuis des dates validées, _dir=B, format CSV et corrélation hexadécimale ; pas de fonction choisie par le navigateur. Réservé aux administrateurs des deux espaces, session/CSRF, quota partagé et verrou global de lecture NEWT. Réponse de 1 Mio maximum, 64 colonnes, 10000 lignes et 2048 caractères par cellule. CSV UTF-8 strict, en-têtes distincts non vides et nombre de colonnes constant, sinon refus intégral. Seuls la période, le compte de lignes et l’empreinte sont audités ; pas de données d’appel dans l’audit. Aucun traitement automatique au démarrage ou en arrière-plan.

Le fuseau du PBX et l’inclusivité réelle de ses dates doivent être confirmés en recette. Un compte zéro signifie seulement que le rapport reçu contient ses en-têtes sans données, pas l’absence d’activité. Les en-têtes et noms fournisseur sont affichés comme texte. Sans réponse réelle validée, l’adaptateur peut refuser un format incompatible plutôt que deviner. La recette de lecture et la correspondance des colonnes seront séparées des commandes d’appel, toujours absentes. Tests simulés uniquement, aucune requête NEWT réelle.

## À livrer séparément

Vérification réelle des droits/configuration pour l’annuaire, recette de lecture 244 et remontée des journaux 511, interprétation documentée des codes et rapprochement appels/contacts. La fonction 245 et tout contrôle d’appel restent absents et soumis à une nouvelle autorisation explicite avant tout test réel. Création automatique de comptes depuis les postes reportée.


## Recette manuelle autorisée du 20 octobre 2026

Lors de tests expressément demandés par l’utilisateur, la fonction 343 a confirmé Martinien au poste 501 et Emery au poste 512. Des commandes 245 ciblées ont répondu HTTP 200 avec Success. L’utilisateur a confirmé la sonnerie et le décrochage sur Martinien puis le fonctionnement d’un appel externe demandé. Ce mode fait d’abord sonner le poste source ; aucun auto-answer demandé, aucun audio navigateur ou WebRTC démontré. Aucune relance automatique ou campagne activée. Numéros externes et identifiants de corrélation de recette non conservés dans Git.

La relecture du détail d’appels 511 pour la journée a renvoyé HTTP 500. Les durées, résultats CDR et codes R/C/H restent donc non validés ; Success n’est pas assimilé à un décrochage distant. Ces tests manuels ne livrent pas encore un bouton d’appel dans le CRM ou un historique métier exploitable. Les commandes d’appel ont été limitées aux demandes explicites de cette séance ; aucun nouvel appel n’est autorisé par cette note.


## API métier Assurance (lot 61)

Le click-to-call Assurance est désormais implémenté côté serveur, désactivé par défaut : voir [ASSURANCE_CLICK_TO_CALL.md](ASSURANCE_CLICK_TO_CALL.md). Cette livraison remplace, pour Assurance seulement, les mentions historiques ci-dessus d’absence de commande métier 245. Aucun appel réel pendant ce lot. Raccrochage, historique CDR, bouton frontend, Isolation et WebRTC restent non livrés ; le diagnostic 511 HTTP500 demeure non résolu.
