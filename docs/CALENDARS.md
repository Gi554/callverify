# Agendas Google et Microsoft

## Périmètre livré — connexion, disponibilité et publication des rendez-vous

Conseiller Assurance et client Isolation connectent leur propre agenda principal, un par espace. Administrateur/setter ne peuvent pas connecter un compte à leur place. Connexions séparées même si un compte possède les deux espaces. Interface : Mon compte et mes sessions → Mes agendas Google et Microsoft. Calendly est exclu à la demande du client.

Le propriétaire active explicitement la publication de ses rendez-vous CRM dans son agenda principal : création des rendez-vous futurs, report des horaires et retrait des événements annulés. Le CRM reste la référence. Synchroniser maintenant exécute un passage, le worker assure les suivants. Un conflit externe laisse le rendez-vous interne intact et affiche une erreur : la confirmation interne ne vérifie pas synchroniquement l’agenda externe. Les modifications externes ne changent jamais le CRM ni les résultats métier.

Les événements AMX ont un libellé neutre avec espace et référence numérique, une visibilité privée, sans nom, téléphone, setter, participant, invitation ni rappel. Seuls les événements portant la référence AMX sont modifiés. Les participants ajoutés manuellement bloquent modification/suppression ; un changement d’horaire externe bloque les mises à jour. Les écritures existantes exigent un ETag avec If-Match. Contrôle de disponibilité avant création/report, sans garantie atomique avec la réservation fournisseur. Agenda principal uniquement ; fenêtres de 31 jours maximum. Microsoft développe les occurrences (cinq pages de 1000 maximum), Google utilise freeBusy ou la liste des occurrences pour exclure son propre événement lors d’un report (cinq pages de 2500 maximum). Erreur ou réponse partielle ne signifie jamais libre. Aucun titre privé externe n’est affiché.

Une clé durable est enregistrée avant toute création externe : identifiant déterministe Google, transactionId et propriété étendue Microsoft. Après une réponse incertaine, recherche par clé ; aucun nouvel envoi aveugle si l’événement reste introuvable. « Création non confirmée » exige une inspection manuelle. Un conflit connu avant écriture peut être retenté. Une coupure pendant un report peut aussi nécessiter une inspection. L’agenda ne prouve jamais qu’un rendez-vous a été effectué.

Avant remplacement/déconnexion, retirer les événements AMX avec le bouton dédié, qui arrête la synchronisation. Retrait potentiellement partiel : consulter les erreurs. Si les droits sont révoqués ou une création incertaine, vérifier/retirer manuellement les événements, puis confirmer le nettoyage avec mot de passe actuel et révision. Cette confirmation ne supprime rien à distance ; elle conserve les références comme abandonnées et efface les jetons locaux. Nouveau consentement et activation explicite ensuite nécessaires.


## Configuration serveur

Variables privées : PORTAL_CALENDAR_KEY (clé Fernet dédiée et stable), GOOGLE_CALENDAR_CLIENT_ID, GOOGLE_CALENDAR_CLIENT_SECRET, MICROSOFT_CALENDAR_CLIENT_ID, MICROSOFT_CALENDAR_CLIENT_SECRET, MICROSOFT_CALENDAR_TENANT (common par défaut, organizations, consumers ou UUID). PORTAL_PUBLIC_URL doit être le domaine public HTTPS en production. Aucun secret OAuth ne doit être écrit dans le dépôt ou envoyé au navigateur. Le formulaire indique les fournisseurs non configurés ; une clé manquante en production désactive les connexions, sans désactiver les autres fonctions du portail. En DEBUG seulement, une clé dérivée du secret de développement est utilisée si aucune clé dédiée n’est fournie.

Google Cloud : activer Calendar API, créer un client OAuth application Web, configurer le consentement et les comptes de test selon l’état de publication. Redirection exacte : PORTAL_PUBLIC_URL + /crm/oauth/google. Scopes : calendar.events et calendar.events.freebusy (URI complets dans le code). L’accès hors ligne et le consentement sont demandés pour conserver un refresh token ; une réponse sans jeton de renouvellement est refusée.

Microsoft Entra : enregistrer une application Web compatible avec les comptes choisis (tenant/organisations/personnels), ajouter les permissions déléguées Calendars.ReadWrite et offline_access et la redirection exacte PORTAL_PUBLIC_URL + /crm/oauth/microsoft. Les règles de consentement du tenant peuvent exiger son administrateur. Utiliser un secret client serveur avec date d’expiration suivie.

Les URI locales sont http://127.0.0.1:5173/crm/oauth/google et http://127.0.0.1:5173/crm/oauth/microsoft si PORTAL_PUBLIC_URL conserve sa valeur de développement ; utiliser exactement l’hôte enregistré, sans mélanger localhost et 127.0.0.1. Le frontend doit être servi à ces chemins, avec fallback SPA. Le retour ne transporte qu’un code OAuth temporaire et un état, échangés par POST session/CSRF vers le backend ; aucun access/refresh token ne transite par JavaScript. Le code/état est retiré de l’URL avant les autres requêtes de la page. Le cookie Strict reste inchangé : le POST est même origine après chargement de la page de retour. Politique no-referrer ; le Nginx fourni journalise $uri sans paramètres. Ne pas activer des logs de corps POST ou de query OAuth dans les autres proxies/outils de suivi.

## Stockage, exploitation et limites

Appliquer les migrations portail jusqu’à 0010 avant démarrage. Access token, refresh token et vérificateur PKCE sont chiffrés Fernet dans la base centrale ; sauvegarder séparément la clé stable. L’état OAuth est aléatoire et seul son hash est conservé ; tentative liée au compte, fournisseur, espace et session, valable dix minutes et consommée une fois. Changement de session ou révocation impose de recommencer. Le vérificateur est effacé à la consommation/déconnexion. Prévoir la purge des tentatives expirées dans la politique de conservation ; elles ne sont jamais réutilisables.

Contrôles de rôle/session/CSRF à chaque commande, vingt requêtes par minute et par compte sur les routes agenda (cache local en développement ; limitation distribuée à valider en production). Les connexions ne figurent pas dans le journal public d’administration des accès : seuls des audits internes minimaux sont écrits, sans code, jeton ou agenda privé.

Le verrou de connexion sérialise les renouvellements de jeton et la déconnexion. Les appels HTTP sortants utilisent des hôtes fixes, timeout dix secondes, aucune redirection ; liens de pagination Microsoft limités au chemin attendu sur graph.microsoft.com. Une réponse mal formée, partielle ou en erreur ne donne aucun résultat libre. Un refus durable exige une reconnexion ; une panne transitoire garde les jetons pour une prochaine tentative. Les routes web ne relancent pas automatiquement une commande ayant échoué.

Déconnecter efface localement les jetons, invalide les consentements en attente et ne supprime aucun événement fournisseur. Cela ne révoque pas l’autorisation côté Google/Microsoft ; le propriétaire peut aussi retirer le consentement dans son compte fournisseur. Un agenda déconnecté/reconnecté pendant un ancien échange ne peut être remplacé par cet échange tardif. Les jetons restent inutilisables via l’application après perte du rôle requis, mais leur suppression définitive suit la déconnexion/politique de conservation.

Aucun compte réel, consentement réel ni appel fournisseur réel validé pendant les tests : identifiants OAuth et comptes de recette restent nécessaires. Les tests utilisent des réponses simulées et la CI PostgreSQL vérifie les courses de consommation/renouvellement. Ne pas présenter ces tests comme une validation réelle des consentements, des politiques de tenant ou de la disponibilité d’un compte client.

## Références fournisseurs

- [Google OAuth serveur](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google freeBusy](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query)
- [Microsoft OAuth authorization code](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Microsoft calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0)

## Worker et vérification du parcours

Configurer ISOLATION_INTERNAL_URL (développement http://127.0.0.1:8000), ASSURANCE_INTERNAL_URL et les clés de tickets métier du portail. Le compose CRM ajoute les hôtes internes à ALLOWED_HOSTS et active TRUST_PROXY côté Isolation. Les requêtes serveur portent X-Forwarded-Proto: https pour traverser sa redirection HTTPS ; garder ces services sur le réseau privé et leurs entrées publiques derrière le proxy de confiance. Hors compose, configurer ces paramètres explicitement. Le portail lit uniquement leurs API avec un ticket du propriétaire ; aucune lecture directe des bases métier. Découverte bornée à 200 pages de 25 rendez-vous futurs par connexion ; au-delà, passage refusé avant écriture. Les événements déjà connus, même passés/annulés, sont relus individuellement. Un dossier devenu inaccessible produit une erreur ; son absence ne déclenche jamais une suppression déduite.

Après migration : `python manage.py sync_calendars --settings=portal.backend.settings --loop --interval 60`. Un passage : même commande sans --loop. Le service portal-calendars du compose CRM utilise cette commande. La pause conserve les événements existants ; la reconnexion n’active jamais seule le worker. L’écran présente un historique paginé de 25 références et leurs derniers états/erreurs, sans jeton ni identifiant d’événement fournisseur. Les audits techniques conservent les actions ; la fiche de synchronisation représente le dernier contrôle. Pas de webhooks, synchronisation bidirectionnelle, invités ou invitations dans ce lot.

Recette réelle après configuration OAuth : connecter son compte de test, activer la publication, créer un rendez-vous CRM futur, synchroniser et contrôler l’événement privé sans participant. Reporter puis annuler côté CRM et resynchroniser. Créer un conflit externe et vérifier l’erreur sans suppression du rendez-vous interne. Tester pause/retrait/déconnexion. Les tests automatisés simulent les fournisseurs : aucune validation réelle de consentement, tenant ou quota fournisseur sans compte client.

- [Google création d’événement](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
- [Microsoft événement et transactionId](https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0)
- [Microsoft recherche par propriété étendue](https://learn.microsoft.com/en-us/graph/api/singlevaluelegacyextendedproperty-get?view=graph-rest-1.0)


## Confirmation Assurance (lot 64)

Les réservations et déplacements Assurance contrôlent maintenant les occupations externes côté serveur : voir BOOKING_EXTERNAL_CALENDARS.md. Cette règle remplace les mentions historiques de réservation uniquement interne pour Assurance. Absence de connexion distinguée de la disponibilité confirmée ; Isolation reste à intégrer.
