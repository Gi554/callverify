# Audit des API CRM AMX — 20 octobre 2026

## Conclusion

**Les API ne couvrent pas encore tout le cahier des charges.** Le socle et de nombreux parcours internes sont développés et testés ; les appels Phonetico intégrés, la réservation avec contrôle externe à la confirmation, la MFA centrale et certaines statistiques métier restent incomplets. Une interface existante ou un test fournisseur manuel ne suffit pas à déclarer un module terminé.

Référence : CRM_AMX_Cahier_des_charges.docx v1.0 du 18 octobre 2026, sections 1 à 14, relu pour cet audit. Les corrections explicites de l’utilisateur priment : finances exclues des deux CRM, Calendly reporté, revue esthétique différée, pas d’appel automatique ou campagne activée. Les documents sont des exigences à comparer, pas une autorisation de lancer des opérations externes.

Revue statique des routes, règles et tests au commit main `1f46f1b` (PR #65). Les résultats de CI déjà obtenus et la recette navigateur des lots 56/57 constituent des preuves historiques ; **aucune nouvelle recette fournisseur ou suite complète n’est déclarée exécutée par cet audit documentaire**. Les statuts ci-dessous concernent le backend, pas l’acceptation du design ou du déploiement.

- **Développé/testé** : parcours borné présent avec contrôles serveur et tests ; ne signifie pas prêt pour production.
- **Partiel** : portion développée, exigence plus large non satisfaite.
- **Manquant** : pas de parcours métier identifié pour l’exigence.
- **Recette externe** : connecteur présent, fonctionnement avec les comptes client encore à valider.
- **Reporté/exclu** : décision explicite ou besoin métier à cadrer.

## Portail et sécurité

| Exigence | État backend | Routes ou sources vérifiées | Écart concret |
|---|---|---|---|
| Connexion commune, session, choix conditionnel d’espace (§1–3) | Développé/testé | `portal/backend/urls.py`, `identity/views.py`, `tests.py`, `test_sessions.py` | Sessions centrale et historique encore distinctes ; pas une migration complète. |
| Droits explicites par espace, bases/API séparées (§2,9,12) | Développé/testé | `/api/portal/access/<workspace>/`, `packages/access/tickets.py`, authentifications métier | Un ticket émis peut survivre jusqu’à deux minutes à une révocation. |
| Invitation, récupération, changement de mot de passe (§3,9) | Développé/testé + recette SMTP | `invitations.py`, `recovery.py`, `passwords.py`, tests associés | Transport réel client à recetter ; la file simulée ne prouve pas la délivrabilité. |
| Gestion des utilisateurs et audit d’accès (§2,9) | Développé/testé | `/workspaces/<workspace>/users/`, `/access-history/` | Ne remplace pas tous les journaux métier de chaque service. |
| Révocation des autres sessions | Développé/testé | `/api/portal/session/revoke-others/`, `session_security.py` | N’invalide pas immédiatement les tickets métier déjà émis. |
| MFA du portail central / migration comptes (§9 et avant production) | Manquant/partiel | `identity/views.py` authentifie identifiant/mot de passe ; MFA historique dans `core` | Ajouter enrôlement, validation, secours et politique centrale ; ne pas confondre MFA historique et centrale. |
| Limitation distribuée des tentatives | Partiel | `portal/backend/settings.py`, throttles DRF ; Redis optionnel côté historique | Pas de cache partagé explicite dans la configuration centrale ; validation multi-worker à terminer. |
| Cockpit administrateur multi-espace (§3) | Partiel | Accès et tableaux par espace présents | Agrégats transversaux autorisés non identifiés comme parcours complet. |
| Conservation, export/suppression des données personnelles (§9) | Partiel / règles à valider | Purge des fichiers historiques dans `core/maintenance.py` | Pas de politique complète ni parcours de suppression/anonymisation couvrant les trois services. Validation métier/juridique distincte. |

## Assurance

Préfixe des routes métier : `/api/assurance/`. Le routeur et les actions sont dans `apps/assurance/backend/urls.py` et `crm/`.

| Exigence | État backend | Preuves code/tests | Écart concret |
|---|---|---|---|
| Import CSV/XLSX brut, mapping, rapport (§4.1) | Développé/testé | `imports.py`, `tests.py`, `test_custom_import.py`, `test_agreement_journey.py` | Pas de normalisation/déduplication/Twilio, conformément au besoin Assurance. |
| Liste commune, fiche, coordonnées, verrou temporaire (§4.1–4.2) | Développé/testé | `contacts/`, `leases.py`, tests fonctionnels et concurrence PostgreSQL | Autosauvegarde du front pour coordonnées ; champs métier et autres actions ont un enregistrement explicite, pas autosauvegarde universelle. |
| Champs configurables, notes/documents et partage sélectif | Développé/testé | `custom_fields.py`, `notes.py`, `documents.py`, `test_shared_fields.py`, `test_note_sharing.py`, `test_document_sharing.py` | Champs définitifs à valider ; fichiers validés par taille/signature, pas antivirus complet. |
| Confidentialité de l’identité setter côté conseiller (§2,12) | Développé/testé sur les routes livrées | Sérialiseurs explicites, tests de droits/partages ; recette conseiller lot57 | À maintenir sur toute nouvelle route, particulièrement appels et statistiques ; aucun blanc-seing sur des modules non livrés. |
| Affectation multi-conseillers (§4.3) | Développé/testé | `assignments.py`, preuves centrales `participants.py` | Attributions actives vérifiées ; pas de répartition intelligente annoncée. |
| RDV interne, report, annulation et historique (§5.2) | Développé/testé | `appointments.py`, tests correspondants | Conflits internes seulement. L’en-tête du module confirme que l’agenda externe n’est pas consulté. |
| Compte rendu Oui/Non, problème ultérieur (§5.3) | Développé/testé | `reports.py`, `tests.py`, `test_notifications.py` | Absence de compte rendu reste distincte de Non ; un résultat ne peut pas être forcé matériellement hors application. |
| Tâche idempotente au setter d’origine, clôture motivée, reprise/réaffectation (§6) | Développé/testé | `follow-ups/`, `reports.py`, `test_task_reopening.py`, `test_task_assignment.py` | Contrôles de versions et audit ; suivre ce parcours dans la refonte front. |
| Alertes persistantes, rappels et escalades (§6) | Développé/testé + exploitation | `notifications.py`, `reminders.py`, `test_reminders.py`, `test_escalations.py` | Générateurs/relais doivent fonctionner en exploitation ; SMTP réel non validé. Lecture ≠ clôture. |
| Pipeline configurable (§7) | Développé/testé | `pipeline.py`, `test_pipeline.py` | Pas d’équivalence implicite entre statut commercial, RDV effectué et signature. |
| Mandats/contrats, dates et pièces (§7) | Partiel | `agreements.py`, `agreement_registry.py`, `agreement_export.py`, tests lots50–56 | Registre administratif admin, historique, alertes et Excel présents. Cycle juridique/signature, visibilité post-contrat et règles métier définitives non implémentés/à préciser. Finances exclues. |
| Statistiques par setter (§7) | Partiel | `statistics.py`, export, tests métier | RDV/comptes rendus/incidents/tâches et taux effectué présents. Pas de volume d’appels Phonetico, conversion commerciale en contrat ou délai de résolution dans les métriques actuelles. Statistiques du registre séparées, sans attribution commerciale au setter. |
| Historique complet des interactions (§4.1) | Partiel | `interactions.py`, journaux RDV/tâches/fiches | Chronologie des ajouts et journaux détaillés séparés ; appels absents, pas une timeline exhaustive de toute modification. |

## Isolation

Les URL internes `/api/` du service historique sont exposées par le proxy CRM sous `/api/isolation/`. Ne pas confondre ces deux préfixes lors de la refonte du client.

| Exigence | État backend | Preuves code/tests | Écart concret |
|---|---|---|---|
| Imports, normalisation canadienne, déduplication, Lookup (§8.1) | Développé/testé, limites fournisseur | `core/views.py`, traitements/services sous `core`, `core/tests.py` | Format et état réel de ligne distincts ; une information fournisseur absente ne prouve pas une ligne active. Les règles de classification restent à valider sur les cas client. |
| Traitement asynchrone, erreurs/progression, journal | Développé/testé + exploitation | Celery/outbox, `core/tasks.py`, tests historiques | Workers/Redis et reprises ambiguës à recetter sur infrastructure finale. |
| Twilio Voice (§8.1) | Partiel / activation reportée | Préparation appels, webhooks dans `config/urls.py`, tests historiques | Émission automatique non livrée/activée ; conformité et scénario à valider. Aucun appel silencieux automatique à lancer. |
| Affectations setters et file privée (§8.2) | Développé/testé | `work-queue/`, `isolation_work.py`, `isolation_bulk.py`, tests | Sélection massive bornée et tour de rôle présents ; charge/disponibilité avancée non livrée. |
| Qualification, notes, rappels, activité | Développé/testé sur parcours interne | `isolation_activity.py`, tests activité/travail | Pas de téléphonie Phonetico intégrée ni preuve d’un moteur complet de relances externes. |
| Visites, reports/annulations, résultat saisi par client | Développé/testé | `visits/`, `isolation_visits.py`, `isolation_client.py`, tests | Agenda interne ; contrôle externe à la confirmation manquant. |
| Client : ses dossiers, résultats, auteurs setters | Développé/testé | `client-prospects/`, `client-dashboard/`, tests partage/client | Périmètres contrôlés ; recette finale du parcours client à conserver dans la refonte. |
| Statistiques et exports (§8.2) | Partiel | `workspace-statistics/`, `isolation_statistics.py`, tests exports | Visites, prospects liés aux visites, résultats et intérêt présents. Pas de statistiques Phonetico ni conversion commerciale globale ; intérêt ≠ conversion finale. |

## Intégrations et exploitation

| Exigence | État | Preuves / reste à faire |
|---|---|---|
| Association setter ↔ extension | Développé/testé | API centrale `phone-extensions`, validation rôles ; `test_phone_extensions.py`. |
| Annuaire 343 / état 244 | Partiel | Adaptateurs et commandes admin protégées, flags désactivés par défaut. 343 réellement relu. 244 expose des observations, pas une disponibilité ni une interprétation certaine de R/C/H. |
| Click-to-call depuis fiche utilisateur (§5.1,8.2) | **Manquant dans le CRM** | 245 testé manuellement sur demandes explicites : source sonne puis utilisateur décroche, fonctionnement externe confirmé. Aucun endpoint métier de lancement associé au prospect, droits, idempotence et audit livrés. |
| Raccrochage 250 et statistiques agents 413 | Manquant | Pas d’API métier identifiée. Un endpoint générique de fonction fournisseur ne doit pas être créé pour contourner les droits. |
| Journaux 341/511 liés aux prospects | Manquant + fournisseur bloquant | Diagnostic de schéma 511 présent ; réponse réelle HTTP500. Pas de synchronisation CDR ni correspondance sûre des champs/statuts. Le test d’appel ne résout pas ce manque. |
| Google/Microsoft : OAuth, tokens chiffrés, busy | Développé/testé, recette externe | `identity/calendars.py`, connecteurs et `test_calendars.py`. Validation avec comptes réels encore nécessaire. |
| Publication/report/retrait de RDV externes | Partiel + recette externe | `calendar_sync.py`, ledger et tests ; sync unidirectionnelle sur agenda principal, opt-in propriétaire. Pas de synchronisation bidirectionnelle complète. |
| Disponibilité externe à la confirmation | **Manquant dans la réservation** | Busy consultable par propriétaire mais pas intégré à la transaction de réservation ; un conflit peut être détecté seulement au stade de synchronisation. À traiter sans exposer le calendrier privé au setter. |
| Calendly | Reporté | Décision explicite utilisateur ; non prioritaire pour finir la version Google/Microsoft. |
| E-mails | Développé/testé, recette externe | File chiffrée et contrôles d’éligibilité/relais ; SMTP et délivrabilité réels client à vérifier. |
| Sauvegarde/restauration locale et PostgreSQL | Développé/testé, outils opérateur | Lots58/59 ; restauration SQLite jetable et PostgreSQL réelle en CI. Pas de sauvegarde automatique externe opérationnelle. |
| Copie externe / médias de production | Reporté, non livré | Brouillon local S3 et tests déplacés dans `private-media/deferred-remote-backup/`, hors Git. Aucun bucket réel contacté ou configuré ; ne pas annoncer ce lot comme fusionné. |
| VPS/HTTPS, restauration hébergement, supervision | Partiel / recette déploiement | Compose et guides présents, pas une production client acceptée. |

## Ordre proposé pour finir le backend

1. **Click-to-call Phonetico métier** : première tranche Assurance, extension du compte connecté, destination de la fiche, contrôle de rôle/verrou, corrélation/audit, protection contre doublons et issue ambiguë. Pas d’appel réel dans les tests, pas d’activation automatique. Puis équivalent Isolation sur les prospects attribués. Un seul lot à la fois.
2. **Réservation avec disponibilité externe** Google/Microsoft : preuve limitée au créneau et au propriétaire, contrôle à la confirmation, gestion des échecs/conflits et lien calendrier. Pas de fuite du calendrier privé vers les setters.
3. **MFA centrale et limitation partagée** avant exposition publique, avec récupération et migration explicitement testées.
4. **Statistiques métier manquantes** : délai de résolution d’abord (données internes disponibles), conversions après définition métier ; métriques d’appels après déblocage CDR. Ne pas inventer des chiffres à partir de commandes Success.
5. **Contrats** : cadrer puis implémenter uniquement les transitions/visibilités nécessaires au métier ; aucune finance et aucune signature implicite.
6. Recettes fournisseurs, rétention et déploiement. Les blocages CDR/SMTP/OAuth ne doivent pas être présentés comme « API à coder » lorsque le connecteur existe déjà.

Chaque tranche : contrôles, commit sur staging, push, PR et fusion main avant la suivante. La refonte GoHighLevel reste une phase distincte après validation des parcours métier ; aucune nouvelle interface décorative n’est requise par cet audit.


## Correction de périmètre du 21 octobre 2026

La précision utilisateur remplace « un seul client au lancement » : Isolation conserve **un client unique permanent**, avec identité du setter visible sur les visites et actions autorisées. Le lot62 garantit une seule adhésion centrale de rôle client, même suspendue, et refuse sa réaffectation de rôle dans les parcours administratifs. Plusieurs conseillers Assurance restent possibles avec masquage du setter. Les tests négatifs du service métier peuvent simuler un autre client pour contrôler les frontières ; ils ne représentent pas une fonction de création multi-client. Le stockage externe reste reporté.


## Actualisation du 21 octobre 2026 — lot 63

Après le lot 61 Assurance, click-to-call backend Isolation livré pour le setter affecté, sous contrôle administratif et exclusions, désactivé par défaut. Contrat : ISOLATION_CLICK_TO_CALL.md. Cette actualisation ne transforme pas le module téléphonie complet en fonctionnalité terminée : boutons, audio navigateur, CDR et recette réelle restent absents. Prochaine tranche : disponibilité externe à la réservation.


## Actualisation du 21 octobre 2026 — lot 64

Le contrôle des occupations Google/Microsoft est intégré à la création et au déplacement Assurance, avec refus sur conflit ou échec d’agenda connecté. Aucun verrou fournisseur : contrôle instantané, agenda principal uniquement, recette réelle non effectuée. Isolation demeure la tranche suivante. Contrat et limites : BOOKING_EXTERNAL_CALENDARS.md.


## Actualisation du 21 octobre 2026 — lot 65

Le contrôle Google/Microsoft couvre maintenant les réservations et déplacements des deux espaces (Assurance lot 64, Isolation lot 65). Toujours une photographie de l’agenda principal, sans verrou fournisseur ni recette OAuth réelle. Client Isolation unique et auteurs préservés. Prochain écart prioritaire : MFA centrale ; limitation distribuée encore à livrer.
