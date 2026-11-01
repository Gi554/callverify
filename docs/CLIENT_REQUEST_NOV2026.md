# Retour client du 2 novembre 2026 — suivi de réalisation

Les espaces Assurance et Isolation restent distincts. Ce document traduit le retour
client en livraisons vérifiables ; il ne contient aucun identifiant de connexion.
Chaque ligne reste ouverte tant que ses critères ne sont pas livrés et vérifiés.
Les paiements demandés sont un suivi de règlements effectués hors Orvia, sans virement.
Une correction après paiement doit produire un ajustement, en conservant le paiement.

| Demande | État et contrôle restant |
| --- | --- |
| 1. Pilotage administrateur | Bloc dans le layout existant, sept indicateurs, filtres serveur et actualisation à une minute implémentés. Livré par PR #244, CI et déploiement réussis. |
| 2A. Isolation : objectifs, présence et prime | Objectifs hebdomadaires, périodes de conditions, présence et prime CAD séparées, taux figés et lecture personnelle implémentés ; livraison du registre en cours. |
| 2B. Assurance : mandat et tarif | Mandat ou objectif hebdomadaire, dates, conditions et tarif de présence individuels implémentés ; livraison du registre en cours. |
| 2C–D. Montants générés et paiements | Consultation personnelle, registre administrateur, contrôle de solde/révision, idempotence et ajustements après correction implémentés ; validation CI en cours. Aucun transfert bancaire. |
| 3. Historique complet | Audits et historiques métier existants ; compléter les nouveaux objectifs, mandats, paiements et ajustements, avec auteur/avant/après. |
| 4. Centre d’alertes | Notifications de rendez-vous et rappels existantes ; compléter la rubrique administrateur et les anomalies. |
| 5. Anomalies | Ajouter les contrôles de cohérence et leur état de traitement, sans corriger les données automatiquement. |
| 6. Performance individuelle setter | Statistiques et appels disponibles dans leurs périmètres ; réunir prospects/appels/qualification/rendez-vous/rémunération et séries jour/semaine/mois. |
| 8. Rapports automatiques | Exports Excel actuels à compléter par PDF et génération quotidienne/hebdomadaire/mensuelle avec historique d’exécution. |
| 9. Recherche avancée | Recherches existantes à compléter par les critères combinés du retour, toujours limitées à l’espace actif. |
| 11. Exports séparés | Préserver les exports métier ; compléter les filtres communs et PDF sans mélange d’espaces. |
| 12. Sauvegardes et sécurité | Dispositifs existants à vérifier en production : sauvegarde planifiée, restauration de recette, sessions, audits et permissions des nouveaux modules. |
| 13. Interface | Réutiliser les layouts, StatKpi, graphiques, panneaux et formulaires existants ; recette ordinateur/mobile à chaque nouveau parcours. |

La partie tronquée du message rappelant le tableau de bord client Isolation est
couverte par les livraisons précédentes (visites à venir/passées, relances personnelles,
résultats manquants). Les nouveaux écarts ne remplacent pas ces parcours.
