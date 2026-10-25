# Calendly dans Orvia — Assurance

## Parcours livré

Un seul client OAuth Orvia permet à chaque conseiller de connecter son propre compte Calendly,
sans l’ajouter à une organisation ni acheter une place dans un abonnement central. Le forfait
reste celui de chaque conseiller. La connexion coexiste avec Google/Microsoft.

Le conseiller ouvre **Mon agenda → Mes agendas connectés → Calendly**, connecte son compte,
choisit une page personnelle active puis clique **Activer la synchronisation**. Le setter ou
administrateur ouvre une fiche prospect, complète/enregistre sa qualification, choisit **Calendly**,
son conseiller attribué, une date et un créneau proposé, puis confirme. Un courriel valide est
nécessaire. Calendly reçoit nom, courriel et identifiant opaque ; qualification et notes restent
dans Orvia et sont accessibles au conseiller via le rendez-vous rattaché au prospect.

Le parcours utilise exclusivement **America/Toronto (Montréal)**. Les instants et décalages réels
sont conservés, y compris les passages été/hiver et l’heure répétée en novembre. L’heure du PC
ne sert pas à interpréter un créneau. La durée vient de la page Calendly choisie.

La confirmation Calendly crée le rendez-vous CRM ; une réponse réseau ambiguë reste en attente,
sans nouvelle tentative de création. La fiche retrouve cette demande après rechargement.
**Vérifier la réservation** relit la même demande. Aucun événement Google/Microsoft supplémentaire
n’est publié pour ce rendez-vous, afin d’éviter une double entrée dans le calendrier connecté.

Les liens **Reporter sur Calendly** et **Annuler sur Calendly** ouvrent les actions du prestataire.
Les notifications signées répercutent ensuite la modification dans Orvia, avec le même dossier,
la même qualification et un historique. Les commandes internes de report/annulation sont bloquées
pour ce fournisseur : une modification uniquement locale ferait diverger les calendriers.

## Activation serveur

Créer une application OAuth **Web / Production** dans le [portail développeur Calendly](https://developer.calendly.com/).
Retour exact : `https://orvia-crm.com/crm/oauth/calendly`.

Scopes requis :

- `users:read`
- `event_types:read`
- `availability:read`
- `scheduled_events:write`
- `webhooks:write`

Les droits d’écriture incluent la lecture correspondante. Ne pas sélectionner organisations,
contacts, transcription, conformité ou modification des disponibilités : ils ne sont pas utilisés.
Les connexions initiales limitées à la lecture doivent être autorisées à nouveau.

Installer hors Git, côté serveur : `CALENDLY_CLIENT_ID`, `CALENDLY_CLIENT_SECRET` et
`CALENDLY_WEBHOOK_SIGNING_KEY`. Conserver `PORTAL_PUBLIC_URL` et la clé Fernet existante
`PORTAL_CALENDAR_KEY` : la remplacer sans migration couperait les connexions déjà chiffrées.
Recréer le portail et les workers concernés après changement d’environnement. Aucun secret
ne doit être collé dans une commande enregistrée, une PR ou un message de recette.

La souscription webhook est créée depuis Orvia pour le seul utilisateur connecté, avec une URL
propre générée par le serveur. Aucun collage manuel d’URL webhook n’est nécessaire. Après un
timeout d’activation, Orvia recherche la souscription existante ; il ne la recrée pas à l’aveugle.
La réservation reste bloquée tant que la synchronisation n’est pas activée. Sans identifiants,
les commandes de connexion/activation restent indisponibles et aucun faux compte n’est affiché.

## Traitement et exploitation

Le service compose `portal-calendly` exécute `sync_calendly --loop --interval 30`. Il consomme les
notifications persistées, avec reprises après panne, puis rapproche périodiquement les rendez-vous
connus. Les événements peuvent arriver plusieurs fois ou dans un ordre différent : les empreintes,
références d’invités, versions et verrous empêchent un double traitement ou un retour à un ancien
créneau. Une chaîne de reports est vérifiée via l’API Calendly avant mise à jour.

Contrôle ponctuel : `python manage.py sync_calendly --settings=portal.backend.settings`.
Le rapprochement des références connues est relancé environ toutes les cinq minutes, dans les
limites du lot traité et de la disponibilité des services. Les rendez-vous anciens déjà livrés
ne sont plus interrogés périodiquement au-delà de trente jours ; une notification reçue reste
traitable. Les erreurs sont reprises avec délai croissant, puis signalées pour vérification.
Après correction de la configuration, **Vérifier la synchronisation** relance les notifications
signalées pour ce compte. Les comptes rendus clôturés restent protégés pendant ces reprises.

Si la réponse de création ET la notification ont été perdues, un opérateur peut retrouver la
référence exacte chez Calendly puis utiliser :

```
python manage.py sync_calendly --settings=portal.backend.settings --recover-request UUID_ORVIA --invitee https://api.calendly.com/scheduled_events/ID/invitees/ID
```

Cette commande ne crée aucun rendez-vous externe. Elle vérifie le compte, la page, le courriel
attendu et le créneau d’origine avant rapprochement. Une correspondance incertaine est refusée.
Ne pas recréer une demande pour contourner un état en attente.

## Sécurité et limites

OAuth PKCE S256, état lié à la session à usage unique, jetons chiffrés, rotation sérialisée des
jetons à usage unique. Signature HMAC sur les octets exacts des notifications et tolérance de
180 secondes, taille bornée, empreinte de réception unique. La réception ne conserve ni courriel,
ni notes, ni questions Calendly ; seul le minimum technique est gardé chiffré puis effacé après
traitement. Les endpoints et URI API sont contrôlés, sans suivre d’URL de pagination externe.
Les transferts entre portail et Assurance sont signés et les routes internes ne sont pas publiques.

Seuls les rendez-vous liés à une demande Orvia sont rapprochés : aucun prospect n’est deviné à
partir d’un événement personnel du conseiller. Les types d’équipe/round-robin ne sont pas proposés.
La réservation directe dépend du forfait du conseiller ; Calendly la réserve aux forfaits Standard
et supérieurs. Une page exigeant des champs additionnels non fournis par ce formulaire peut refuser
la réservation : choisir une page personnelle compatible. Un refus ne crée aucun rendez-vous CRM.

Un conflit introduit par un report externe est reflété avec une alerte ; il n’est pas masqué.
Un changement touchant un rendez-vous ayant déjà un compte rendu est signalé pour examen, sans
effacer ce compte rendu. La qualification d’origine reste conservée. Les acteurs externes sont
tracés comme système Calendly, et non comme une action du setter.

La déconnexion efface profil/pages/jetons locaux et arrête le suivi des notifications ; elle ne
supprime ni les rendez-vous externes ni l’historique CRM. Révoquer aussi l’application depuis le
compte Calendly pour supprimer son autorisation distante. Un compte ayant des réservations liées
doit reconnecter le même Calendly d’origine afin de conserver leur traçabilité.

## Recette

Les tests automatisés couvrent bail, attribution, droits, révisions, conflits, confirmation,
refus/timeout, reprise après réouverture de fiche, signatures, doublons, perte de réponse,
report/annulation désordonnés, livraison rejouée, compte rendu préservé et changements d’heure.
Les tests de concurrence PostgreSQL sont exécutés dans la CI. Les réponses externes sont simulées.

Recette réelle après installation des identifiants : connecter un conseiller, activer sa
synchronisation, réserver un prospect de test autorisé, vérifier son calendrier et sa qualification
Orvia, reporter puis annuler via les liens Calendly et vérifier le même dossier dans Orvia.
Aucun rendez-vous réel n’a été créé durant le développement ; le consentement du titulaire et
les identifiants sont encore nécessaires. Utiliser une application Sandbox distincte pour la
recette locale (`http://localhost:5174/crm/oauth/calendly`), sans secrets de production.
Pour recevoir de vraies notifications, prévoir aussi une adresse HTTPS de préproduction
accessible à Calendly : une URL localhost seule ne peut pas les recevoir.

Références : [OAuth](https://developer.calendly.com/docs/authentication/creating-an-oauth-app),
[scopes](https://developer.calendly.com/docs/authentication/scopes),
[Scheduling API](https://developer.calendly.com/api-docs/calendly-api/scheduled-events/create-event-invitee),
[signatures](https://developer.calendly.com/api-docs/overview/webhooks/webhook-signatures).
