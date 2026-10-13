# État du projet CallVerify

## Livré et testable sans identifiants externes

- Interface responsive crème/olive, connexion et navigation par URL.
- Campagnes créées/modifiées/archivées ; budgets estimés et progression.
- Import CSV/XLSX avec choix de feuille, aperçu, mappage, doublons et rapport CSV.
- Résultats recherchables et paginés ; fiche, historique, preuves et classifications indépendantes.
- Exports CSV/XLSX avec colonnes choisies, filtres, téléchargement privé et expiration.
- Invitations, suspension, rôles et MFA avec QR code, chiffrement et codes de secours.
- Paramètres de conservation/cadence/cache/devise ; exclusions et décisions d'autorisation justifiées.
- Audit, alertes, outbox persistante, reprise de publication, limiteur global Redis et purge programmée.
- Lookup Basic et enrichissements facultatifs préparés avec gestion des restrictions ; aucune requête réelle effectuée.
- Conteneurs API/frontend, workers, Beat et configuration HTTPS Caddy.
- Guide administrateur, API, exploitation et contrôle `preflight`.

## Vérifications réalisées

Tests unitaires/fonctionnels sur SQLite et PostgreSQL, compilation Vue/TypeScript, construction du frontend Nginx, contrôle des configurations Compose locale/production, limiteur Redis réel, sauvegarde et restauration PostgreSQL sur bases jetables. La recette navigateur utilise exclusivement des contacts fictifs. Le rapport de recette précise les validations finales.

## Informations que vous ajouterez plus tard

Compte Twilio et droits canadiens, coût unitaire et devise, SMTP et expéditeur, hébergement/domaine, région de stockage, secrets de production et politique de rétention. Ces valeurs restent dans l'environnement serveur, jamais dans le frontend ni les documents partagés.

## Travaux qui dépendent de ces informations

- Recette des requêtes Twilio réelles et de leur facturation ; rapprochement automatique des données de facturation à définir.
- Configuration SMTP et vérification de réception des emails.
- Déploiement public avec HTTPS, stockage privé réel, chiffrement des sauvegardes et restauration sur l'hébergement retenu.
- Tests de charge au volume cible, supervision externe et antivirus selon vos exigences.
- Émission d'appels Voice : à implémenter après définition du scénario autorisé, émetteur, fuseaux/horaires, consentements et exclusions, cadence, concurrence, tentatives, budget et arrêt chez le fournisseur. L'application actuelle prépare les campagnes et contrôle l'admissibilité, sans émettre d'appel.

Une version de qualification technique peut être livrée après la recette fournisseur et d'hébergement, indépendamment du module d'émission d'appels.
