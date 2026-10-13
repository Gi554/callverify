# Rapport de recette locale — 13 octobre 2026

## Résultats vérifiés

- 50 tests automatisés passent sur SQLite et PostgreSQL : permissions, CSRF, MFA chiffré et codes de secours, imports, budgets, cache, outbox, purge, exports, classifications et webhooks.
- Vue/TypeScript compile. Les images Docker API et Vue/Nginx sont construites avec succès ; Compose local et son override HTTPS sont valides.
- Connexion MFA testée en navigateur contre une base PostgreSQL jetable.
- Import UI : 4 lignes fictives, 2 contacts valides, 1 doublon, 1 numéro invalide. Aperçu et mappage téléphone/nom/référence confirmés.
- Export XLSX demandé, généré et téléchargé en navigateur. Le classeur contient trois contacts uniques et huit colonnes, avec classifications et justifications. La protection des formules CSV et des cellules XLSX est couverte par les tests.
- Redis réel : cinq requêtes autorisées et cinq bloquées sur un lot immédiat de dix au seuil de cinq par seconde.
- Worker Celery Linux réel : import asynchrone de 1000 lignes fictives, 100 numéros uniques, 900 doublons ; 1000 occurrences sources conservées, outbox marquée completed. Traitement observé d'environ quatre secondes sur cette machine ; ce n'est pas une garantie de capacité en production.
- Sauvegarde PostgreSQL `pg_dump -Fc` restaurée avec `pg_restore` dans une deuxième base jetable, avec conservation des enregistrements contrôlés.

## Limites de la recette

Aucun appel Twilio réel, aucun email transmis à un destinataire réel, aucun stockage S3 réel et aucun domaine public déployé. Les accès et informations seront fournis plus tard. La restauration média chiffrée et les tests de charge/concurrence au volume cible doivent être réalisés sur l'infrastructure retenue. Les appels Voice sont préparables mais leur émission reste à implémenter après validation du scénario.

Les données et comptes de recette sont fictifs. Aucun compte de production n'a été créé.
