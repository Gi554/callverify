# Évolution CRM AMX

Référence métier : CRM_AMX_Cahier_des_charges.docx, version du 18 octobre 2026, fourni par le client. L'évolution est livrée par lots testés sur staging, puis PR et fusion vers main. Aucun préfixe de branche automatique.

## Lot 1 — socle en cours

Identité centrale dans portal/backend, droits explicites par espace, ticket signé de deux minutes avec audience Assurance ou Isolation et clés distinctes. Aucune permission implicite accordée à un administrateur central. La révocation bloque les nouveaux tickets ; un ticket déjà émis reste valable au maximum deux minutes. Les sessions centrales et historiques sont distinctes.

Assurance possède un service et une base propres. Les premières routes de lecture exposent les contacts et un aperçu, sans Twilio ni normalisation. La vue conseiller filtre ses dossiers et utilise une liste explicite de champs excluant l'auteur setter. La création et l'édition restent bloquées jusqu'au développement du verrouillage temporaire.

Isolation conserve temporairement core/ et config/ pour éviter de déplacer les sources métier en même temps que l'authentification. L'accès par ticket central est limité à ses administrateurs ; les portails setter/client viendront avec les affectations. L'interface historique reste disponible et utilise encore sa session propre. Cette transition n'est pas une migration complète des comptes ni des parcours métier.

## Lots suivants

2. Isolation : dossiers, affectations setters, qualification et rappels, Phonetico, visites, résultats et agenda du client unique.
3. Assurance : import brut sans pipeline technique, contacts communs, verrouillage avec expiration et renouvellement, affectations multi-conseillers, rendez-vous et historique.
4. Agendas Google/Microsoft/Calendly selon capacités réelles, comptes rendus obligatoires, incidents et tâches idempotentes avec alertes persistantes et emails.
5. Contrats, statistiques, sauvegardes externes/restaurations, sécurité, déploiement VPS et recette complète.

## Points à traiter avant production

Migration explicite des comptes historiques, MFA du portail, invitation et récupération centrales, gestion des adhésions depuis le portail, révocation des sessions/tickets selon le besoin, limitation distribuée des tentatives, connecteurs externes, sauvegardes et déploiement. Ne pas interpréter les routes de socle comme des modules métiers terminés. Les identifiants d'intégration restent côté serveur. Les fonctions Phonetico seront implémentées après vérification de sa documentation ; aucun appel réel n'est déclenché par ce socle.
