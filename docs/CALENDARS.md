# Agendas Google et Microsoft

## Périmètre livré — connexion et disponibilité

Conseiller Assurance et client Isolation connectent leur propre agenda principal, un par espace. Administrateur/setter ne peuvent pas connecter un compte à leur place. Connexions séparées même si un compte possède les deux espaces. Interface : Mon compte et mes sessions → Mes agendas Google et Microsoft. Calendly est exclu à la demande du client.

Cette première étape ne crée, ne reporte ni n’annule les rendez-vous CRM chez le fournisseur. Les réservations restent explicitement internes jusqu’au lot de synchronisation. Une fenêtre occupée est une observation à l’instant du contrôle, sans réservation externe ni garantie contre une modification concurrente chez le fournisseur. Seul l’agenda principal est consulté, pas tous les agendas partagés/secondaires. Fenêtre maximale : 31 jours ; Microsoft : cinq pages de 1000 événements maximum, sinon échec sans déduire un agenda libre. Événements libres/annulés Microsoft exclus, occurrences développées via calendarView ; Google utilise freeBusy. Aucun titre, participant, organisateur ou description ne quitte l’adaptateur.

## Configuration serveur

Variables privées : PORTAL_CALENDAR_KEY (clé Fernet dédiée et stable), GOOGLE_CALENDAR_CLIENT_ID, GOOGLE_CALENDAR_CLIENT_SECRET, MICROSOFT_CALENDAR_CLIENT_ID, MICROSOFT_CALENDAR_CLIENT_SECRET, MICROSOFT_CALENDAR_TENANT (common par défaut, organizations, consumers ou UUID). PORTAL_PUBLIC_URL doit être le domaine public HTTPS en production. Aucun secret OAuth ne doit être écrit dans le dépôt ou envoyé au navigateur. Le formulaire indique les fournisseurs non configurés ; une clé manquante en production désactive les connexions, sans désactiver les autres fonctions du portail. En DEBUG seulement, une clé dérivée du secret de développement est utilisée si aucune clé dédiée n’est fournie.

Google Cloud : activer Calendar API, créer un client OAuth application Web, configurer le consentement et les comptes de test selon l’état de publication. Redirection exacte : PORTAL_PUBLIC_URL + /crm/oauth/google. Scopes : calendar.events et calendar.events.freebusy (URI complets dans le code). L’accès hors ligne et le consentement sont demandés pour conserver un refresh token ; une réponse sans jeton de renouvellement est refusée.

Microsoft Entra : enregistrer une application Web compatible avec les comptes choisis (tenant/organisations/personnels), ajouter les permissions déléguées Calendars.ReadWrite et offline_access et la redirection exacte PORTAL_PUBLIC_URL + /crm/oauth/microsoft. Les règles de consentement du tenant peuvent exiger son administrateur. Utiliser un secret client serveur avec date d’expiration suivie.

Les URI locales sont http://127.0.0.1:5173/crm/oauth/google et http://127.0.0.1:5173/crm/oauth/microsoft si PORTAL_PUBLIC_URL conserve sa valeur de développement ; utiliser exactement l’hôte enregistré, sans mélanger localhost et 127.0.0.1. Le frontend doit être servi à ces chemins, avec fallback SPA. Le retour ne transporte qu’un code OAuth temporaire et un état, échangés par POST session/CSRF vers le backend ; aucun access/refresh token ne transite par JavaScript. Le code/état est retiré de l’URL avant les autres requêtes de la page. Le cookie Strict reste inchangé : le POST est même origine après chargement de la page de retour. Politique no-referrer ; le Nginx fourni journalise $uri sans paramètres. Ne pas activer des logs de corps POST ou de query OAuth dans les autres proxies/outils de suivi.

## Stockage, exploitation et limites

Appliquer la migration portail 0009 avant démarrage. Access token, refresh token et vérificateur PKCE sont chiffrés Fernet dans la base centrale ; sauvegarder séparément la clé stable. L’état OAuth est aléatoire et seul son hash est conservé ; tentative liée au compte, fournisseur, espace et session, valable dix minutes et consommée une fois. Changement de session ou révocation impose de recommencer. Le vérificateur est effacé à la consommation/déconnexion. Prévoir la purge des tentatives expirées dans la politique de conservation ; elles ne sont jamais réutilisables.

Contrôles de rôle/session/CSRF à chaque commande, vingt requêtes par minute et par compte sur les routes agenda (cache local en développement ; limitation distribuée à valider en production). Les connexions ne figurent pas dans le journal public d’administration des accès : seuls des audits internes minimaux sont écrits, sans code, jeton ou agenda privé.

Le verrou de connexion sérialise les renouvellements de jeton et la déconnexion. Les appels HTTP sortants utilisent des hôtes fixes, timeout dix secondes, aucune redirection ; liens de pagination Microsoft limités au chemin attendu sur graph.microsoft.com. Une réponse mal formée, partielle ou en erreur ne donne aucun résultat libre. Un refus durable exige une reconnexion ; une panne transitoire garde les jetons pour une prochaine tentative. Les routes web ne relancent pas automatiquement une commande ayant échoué.

Déconnecter efface localement les jetons, invalide les consentements en attente et ne supprime aucun événement fournisseur. Cela ne révoque pas l’autorisation côté Google/Microsoft ; le propriétaire peut aussi retirer le consentement dans son compte fournisseur. Un agenda déconnecté/reconnecté pendant un ancien échange ne peut être remplacé par cet échange tardif. Les jetons restent inutilisables via l’application après perte du rôle requis, mais leur suppression définitive suit la déconnexion/politique de conservation.

Aucun compte réel, consentement réel ni appel fournisseur réel validé pendant les tests : identifiants OAuth et comptes de recette restent nécessaires. Les tests utilisent des réponses simulées et la CI PostgreSQL vérifie les courses de consommation/renouvellement. Ne pas présenter ces tests comme une validation réelle des consentements, des politiques de tenant ou de la disponibilité d’un compte client.

## Références fournisseurs

- [Google OAuth serveur](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google freeBusy](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query)
- [Microsoft OAuth authorization code](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Microsoft calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0)
