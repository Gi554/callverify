# Suivi des livraisons CRM AMX

Une fonctionnalité est terminée après vérification, commit, push, PR et fusion dans main. Le cahier des charges métier est CRM_AMX_Cahier_des_charges.docx du 18 octobre 2026.

## Correctifs CallVerify livrés

- PR 4 : nombres Excel avec suffixe .0, première ligne sans en-tête, diagnostic des campagnes sans numéro exploitable, état de ligne principal, badges, exports et séparation du résultat Basic.

## Fonctionnalité 1 — portail et accès aux espaces

Livrable du présent lot : portail de développement /crm, connexion et déconnexion centrales, droits explicites par espace, entrée directe pour un seul espace et sélection pour les comptes multi-espaces. Les tickets sont signés, limités à deux minutes et propres à chaque audience. Les services Assurance et Isolation possèdent des bases séparées et vérifient leurs droits côté API. Assurance ne propose aucune route Twilio.

Les quelques routes de lecture Assurance servent à vérifier le périmètre conseiller ; elles excluent les identifiants internes du setter. La création et l'édition de dossiers par les utilisateurs restent bloquées jusqu'à leur propre fonctionnalité. L'administration des accès passe actuellement par des commandes serveur.

Limites de ce lot : l'interface CallVerify historique conserve sa session propre ; la navigation commune vers ses parcours complets n'est pas encore migrée. Les rôles setter/client Isolation n'ont pas encore de routes métier. MFA, invitations et récupération de mot de passe centrales restent à intégrer avant production. Les tickets émis avant une révocation peuvent rester valides jusqu'à deux minutes.

## Fonctionnalités suivantes non livrées

1. Gestion et migration complète des comptes, MFA, invitations, récupération et navigation unifiée avec Isolation.
2. Dossiers Isolation, affectations des setters, travail des prospects et suivi des visites.
3. Dossiers Assurance et import brut, verrouillage temporaire, affectations multi-conseillers.
4. Phonetico dans chaque CRM, après validation des opérations réelles du fournisseur.
5. Agendas et rendez-vous, puis comptes rendus, incidents, tâches et alertes persistantes.
6. Contrats, statistiques métier, sauvegardes externes et déploiement final.

Les prochains éléments seront découpés en fonctionnalités plus petites, chacune avec sa PR fusionnée avant la suivante. Aucun de ces modules n'est déclaré terminé par la présence de son emplacement dans le dépôt.
