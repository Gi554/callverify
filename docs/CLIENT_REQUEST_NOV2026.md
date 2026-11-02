# Retour client du 2 novembre 2026 — suivi de réalisation

Les espaces Assurance et Isolation restent distincts. Ce document traduit le retour
client en livraisons vérifiables ; il ne contient aucun identifiant de connexion.
Chaque ligne reste ouverte tant que ses critères ne sont pas livrés et vérifiés.
Les paiements demandés sont un suivi de règlements effectués hors Orvia, sans virement.
Une correction après paiement doit produire un ajustement, en conservant le paiement.

| Demande | État et contrôle restant |
| --- | --- |
| 1. Pilotage administrateur | Bloc dans le layout existant, sept indicateurs, filtres serveur et actualisation à une minute implémentés. Livré par PR #244, CI et déploiement réussis. |
| 2A. Isolation : objectifs, présence et prime | Objectifs hebdomadaires, périodes de conditions, présence et prime CAD séparées, taux figés et lecture personnelle implémentés ; livré par PR #245. |
| 2B. Assurance : mandat et tarif | Mandat ou objectif hebdomadaire, dates, conditions et tarif de présence individuels implémentés ; livré par PR #245. |
| 2C–D. Montants générés et paiements | Consultation personnelle, registre administrateur, contrôle de solde/révision, idempotence et ajustements après correction livrés par PR #245, contrôles PostgreSQL réussis. Aucun transfert bancaire. |
| 3. Historique complet | Journal administrateur consultable, filtres période/auteur/type/référence et détail avant/après des audits enregistrés livrés en PR #246. Objectifs et paiements audités en PR #245. Les anciens événements incomplets ne sont pas reconstitués ; audit exhaustif des anciens parcours à contrôler. |
| 4. Centre d’alertes | Notifications métier existantes conservées. Centre administrateur à neuf catégories et prises en charge indépendantes implémenté ; livrés en PR #247, CI réussie. |
| 5. Anomalies | Contrôles en direct des doublons potentiels (même fiche/début, ou numéro exact après trim), responsables nuls, résultats/rappels échus, montants sans tarif ou à régulariser/rapprocher et refus de paiements implémentés. Les alertes sont prises en charge sans correction automatique ; pas de détection approximative des numéros ni preuve externe de paiement. |
| 6. Performance individuelle setter | Vue individuelle admin/setter implémentée : inventaire actuel, qualifications capturées dans les rendez-vous, résultats et gains figés, séries jour/semaine/mois et compteurs Orvia séparés. Le décrochage du prospect reste indisponible, sans inférence depuis le poste NEWT. Livré en PR #248, CI réussie. |
| 8. Rapports automatiques | Exports Excel actuels à compléter par PDF et génération quotidienne/hebdomadaire/mensuelle avec historique d’exécution. |
| 9. Recherche avancée | Recherches existantes à compléter par les critères combinés du retour, toujours limitées à l’espace actif. |
| 11. Exports séparés | PDF ajouté aux statistiques et exports tabulaires/dossiers existants, avec mêmes filtres et permissions ; validation et livraison en cours. Limite 500 lignes. Les nouveaux filtres communs avancés restent à compléter. |
| 12. Sauvegardes et sécurité | Dispositifs existants à vérifier en production : sauvegarde planifiée, restauration de recette, sessions, audits et permissions des nouveaux modules. |
| 13. Interface | Réutiliser les layouts, StatKpi, graphiques, panneaux et formulaires existants ; recette ordinateur/mobile à chaque nouveau parcours. |

La partie tronquée du message rappelant le tableau de bord client Isolation est
couverte par les livraisons précédentes (visites à venir/passées, relances personnelles,
résultats manquants). Les nouveaux écarts ne remplacent pas ces parcours.
