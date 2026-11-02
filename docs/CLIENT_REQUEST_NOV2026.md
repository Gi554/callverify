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
| 3. Historique complet | Journal administrateur consultable, filtres période/auteur/type/référence et détail avant/après des audits enregistrés livrés en PR #246. Objectifs et paiements audités en PR #245. Les parcours rendez-vous/report/qualification/tâches et écritures financières utilisent leurs audits existants. Les auteurs du journal sont résolus par nom et identifiant dans le même espace ; les anciens événements incomplets ne sont pas reconstitués. |
| 4. Centre d’alertes | Notifications métier existantes conservées. Centre administrateur à neuf catégories et prises en charge indépendantes implémenté ; livrés en PR #247, CI réussie. |
| 5. Anomalies | Contrôles en direct des doublons potentiels (même fiche/début, ou numéro exact après trim), responsables nuls, résultats/rappels échus, montants sans tarif ou à régulariser/rapprocher et refus de paiements implémentés. Les alertes sont prises en charge sans correction automatique ; pas de détection approximative des numéros ni preuve externe de paiement. |
| 6. Performance individuelle setter | Vue individuelle admin/setter implémentée : inventaire actuel, qualifications capturées dans les rendez-vous, résultats et gains figés, séries jour/semaine/mois et compteurs Orvia séparés. Le décrochage du prospect reste indisponible, sans inférence depuis le poste NEWT. Livré en PR #248, CI réussie. |
| 8. Rapports automatiques | Exports PDF/Excel disponibles. Rapports quotidiens, hebdomadaires et mensuels (performance, campagnes, finances), worker durable, configuration admin et historique livrés en PR #250, CI réussie. Activation propre à chaque espace depuis l’onglet Rapports. |
| 9. Recherche avancée | Recherche admin combinée nom/téléphone/setter actuel/setter de réservation/client-conseiller/campagne/identifiant/dates/statuts implémentée, avec filtre sur un même rendez-vous, ouverture de fiche et exports filtrés ; livrée par PR #251, CI réussie. |
| 11. Exports séparés | PDF livré par PR #249 dans les statistiques et exports tabulaires/dossiers existants, avec mêmes filtres et permissions. Limite 500 lignes. Filtres administratifs combinés et exports exacts livrés par PR #251. |
| 12. Sauvegardes et sécurité | Livré en PR #252. Sauvegarde chiffrée créée le 2 novembre, trois bases restaurées dans un conteneur sans réseau, médias/configuration vérifiés ; cron quotidien 04:15 heure serveur installé. Sessions et routes privées contrôlées en production. Copie hors site non configurée. |
| 13. Interface | Layouts, StatKpi, StatBars, panneaux et exports existants réutilisés ; comportements et compilation testés, PDF rendus et inspectés. Recette visuelle ordinateur/mobile des pages non effectuée : navigateur local refusé par Work, même après nouvelle tentative. |

La partie tronquée du message rappelant le tableau de bord client Isolation est
couverte par les livraisons précédentes (visites à venir/passées, relances personnelles,
résultats manquants). Les nouveaux écarts ne remplacent pas ces parcours.

## Recette du 2 novembre 2026

Les PR #244 à #252 sont fusionnées et leurs CI sont vertes. Les modules ont été déployés par CD ; les permissions administrateur/setter/client/closer/conseiller ont été contrôlées sur les routes réellement hébergées, sans afficher de données personnelles. Six rapports réels (trois types par espace) ont été générés et conservés, PDF et Excel validés. Les planifications des deux espaces sont actives à 19 h au Québec.

Sessions : DEBUG désactivé, cookies de session HTTPS/HttpOnly/SameSite Strict, CSRF HTTPS et durée maximale de huit heures. Les 18 tests ciblés sessions/auteurs/rapports et les suites complètes passent, dont concurrence PostgreSQL en CI. Le journal montre les états avant/après enregistrés ; les changements de tâches imbriqués sont également présentés dans ces rubriques.

La sauvegarde du 2 novembre a restauré Isolation (44 tables), portail (34 tables), Assurance (37 tables) ; migrations et lecture de chaque table vérifiées. Clé en 600, dossier en 700. Cron installé une fois, autres tâches conservées, aucun conteneur de recette restant. Ce dispositif reste local au VPS ; la conservation séparée de la clé et une destination de copie hors site relèvent d’une configuration supplémentaire. La revue visuelle des pages reste le seul contrôle demandé non exécuté dans cette session, car l’accès navigateur demeure refusé. Les limites de volume et de sources de chaque livraison sont détaillées dans DELIVERY.md.
