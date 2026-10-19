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

## Observations partagées Isolation

1. Avec un setter Isolation, ouvrir un prospect attribué et ajouter une note depuis le suivi ; disposer d’une visite du dossier liée au client.
2. Dans Visites → Observations partagées, la note apparaît Interne. Avec le client de la visite, le même écran ne doit pas la montrer.
3. Le responsable ou l’administrateur sélectionne Publier pour ce client, vérifie le texte et confirme avec un motif. Le client actualise : seule cette observation apparaît, avec rôle et identifiant de l’auteur.
4. Une autre note non publiée reste absente. Un autre client, même lié au même dossier par une visite, ne reçoit aucun partage implicite.
5. Retirer le partage avec un motif puis actualiser le client : l’observation disparaît. Elle reste conservée dans le suivi interne. Les copies déjà consultées ne peuvent pas être retirées.
6. Réattribuer le dossier : l’ancien setter perd les commandes de publication ; le nouveau ou l’administrateur peut gérer le partage, sans changer l’auteur historique. Une ancienne révision doit être refusée et exiger un rechargement.

Commandes automatiques : `python manage.py test core.test_isolation_sharing` (deux tests de concurrence exécutés uniquement sur PostgreSQL). API : GET/POST `/api/visits/{id}/activities/` ; POST exige activity_id, revision du prospect, visible et reason. L’identité client provient de la visite, jamais d’un champ fourni par le navigateur. Aucun appel, Lookup ou e-mail n’est déclenché.

## Répartition à tour de rôle Isolation

1. Avec l’administrateur Isolation, ouvrir la file de prospects et Répartir entre plusieurs setters. Sélectionner les non affectés de la page et deux setters actifs ; saisir le motif.
2. Prévisualiser sans enregistrer : vérifier chaque cible et les compteurs. Pour cinq prospects et deux setters : trois/deux, selon les identifiants croissants, indépendamment de l’ordre des cases cochées. Recharger une autre session : aucune affectation avant confirmation.
3. Confirmer : tout le lot est attribué. Les nouveaux responsables retrouvent leurs prospects ; l’historique d’affectation conserve le motif et le mode round_robin.
4. Entre aperçu et confirmation, affecter un prospect depuis une autre session : confirmation refusée pour tout le lot ; aucun partage partiel. Recharger puis refaire une sélection.
5. Setter, client et compte Assurance ne peuvent pas utiliser les routes de répartition. Aucun appel ou Lookup déclenché. La charge préexistante ne participe pas au calcul.

API : POST `/api/work-queue/distribution-preview/` avec setter_ids et items (id/revision), puis POST `/api/work-queue/distribute/` avec ces champs, request_id, reason et preuve par item. Les cibles sont recalculées côté serveur. Tests : `python manage.py test core.test_isolation_bulk` ; quatre tests de concurrence du module sont exécutés uniquement sur PostgreSQL. Limite : 25 prospects de la page courante, pas une distribution massive en arrière-plan.
