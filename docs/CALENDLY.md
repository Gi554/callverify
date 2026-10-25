# Calendly — connexion personnelle du conseiller Assurance

> Mise à jour réservation : le parcours ajoute le choix de créneaux et la création depuis les
> fiches Assurance, avec qualification conservée dans Orvia. Les webhooks restent au lot suivant.
> Scopes actuels : **users:read**, **event_types:read**, **availability:read**,
> **scheduled_events:write**, **webhooks:write**. Les anciennes connexions doivent être
> réautorisées. Le parcours impose Montréal (`America/Toronto`), indépendamment de l’heure du PC.
> Les demandes incertaines se retrouvent par « Vérifier la réservation », sans recréation.
> Les sections historiques ci-dessous décrivent le périmètre initial de connexion, remplacé
> pour la réservation par cette mise à jour et par le suivi `docs/DELIVERY.md`.

## Parcours livré

Dans **Mon agenda et mes disponibilités → Mes agendas connectés**, ou dans les agendas de
**Mon compte**, le conseiller Assurance connecte son propre compte Calendly par OAuth.
Il voit son profil et ses pages individuelles actives, choisit une page préférée, l’ouvre
sur Calendly, actualise ses pages et peut déconnecter le compte. La connexion est indépendante
de Google/Microsoft : elle ne remplace pas le calendrier principal et ne publie pas d’événement.

Un seul client OAuth Orvia dessert les comptes indépendants des conseillers. Il ne crée ni
utilisateur, ni invitation à une organisation, ni place payante Calendly. Le forfait et sa
facturation restent gérés entre chaque conseiller et Calendly. Le connecteur ne prétend pas
détecter le forfait d’un compte ; aucun champ de l’API utilisé ici ne garantit cette information.

## Activation du client OAuth

Créer une application **Web** dans le [portail développeur Calendly](https://developer.calendly.com/).
Pour la production, enregistrer exactement :

```
https://orvia-crm.com/crm/oauth/calendly
```

Choisir uniquement les scopes **`users:read`** et **`event_types:read`** pour ce parcours.
Renseigner côté serveur, hors Git et hors navigateur :

```
CALENDLY_CLIENT_ID=
CALENDLY_CLIENT_SECRET=
```

Le portail utilise aussi `PORTAL_PUBLIC_URL` et la clé de chiffrement existante
`PORTAL_CALENDAR_KEY`. Ne pas remplacer cette clé : les comptes Google/Microsoft déjà
connectés en dépendent. Le compose transmet les deux nouvelles variables au portail.
Recréer le service portail après modification de l’environnement serveur. Sans ces identifiants,
le bouton reste désactivé avec une explication ; aucune donnée de démonstration n’est présentée
comme un compte réellement connecté.

Pour la recette locale, créer une application **Sandbox** distincte, avec le callback
`http://localhost:5174/crm/oauth/calendly` et le `PORTAL_PUBLIC_URL` correspondant. Ne pas
réutiliser les secrets de production dans la recette partagée.

## Recette manuelle après configuration

1. Se connecter comme conseiller Assurance, ouvrir les agendas connectés, cliquer sur Calendly.
2. Autoriser son propre compte sur le domaine Calendly ; vérifier le retour vers Orvia et le nom.
3. Choisir une page personnelle active, enregistrer, recharger la page et ouvrir le lien préféré.
4. Désactiver cette page dans Calendly puis actualiser : elle disparaît et le choix est effacé.
5. Déconnecter : profil, pages, préférence et jetons locaux sont effacés ; Google reste connecté.
6. Vérifier également refus de consentement, retour expiré et utilisateur setter/administrateur
   (pas de connexion d’un conseiller à sa place).

Ces opérations ne créent pas de rendez-vous. Tester une réservation réelle seulement dans
un lot ultérieur explicitement dédié à la réservation et à son rapprochement avec le CRM.

## Sécurité et limites

- PKCE S256, état aléatoire stocké sous forme d’empreinte, session/utilisateur liés,
  validité de dix minutes, retour à usage unique, révision contre les retours obsolètes.
- Secret uniquement serveur ; jetons, profil et pages chiffrés avec Fernet ; aucun jeton
  ni secret dans les réponses ou dans les audits. Pas de collecte d’avatar, courriel,
  organisation, questions ou notes internes Calendly dans ce lot.
- Renouvellement sérialisé en base. Le nouveau jeton remplace immédiatement l’ancien,
  même si la lecture suivante échoue. En cas d’échec ambigu du renouvellement, la connexion
  est effacée et doit être autorisée à nouveau ; l’ancien jeton n’est pas réessayé.
- Lectures sur des endpoints fixes, redirections HTTP interdites ; aucun suivi d’URL de
  pagination fournie par le prestataire. Limite de trois pages de cent types, erreur si
  davantage ; seuls les types personnels `solo` du propriétaire sont proposés.
- Déconnexion locale : elle ne révoque pas le consentement distant et ne supprime pas de
  rendez-vous. Une révocation complémentaire se fait dans le compte Calendly du conseiller.
- Les pages sont un instantané à actualiser. Leur ouverture ne prouve pas la disponibilité
  d’un créneau et n’enregistre aucun rendez-vous dans Orvia.

## À livrer séparément

Le partage du lien au setter selon son association au conseiller, les créneaux dans Orvia,
la réservation par API, la liaison au prospect et les webhooks de création/annulation/report
ne sont pas implémentés par ce lot. Aucun indicateur de rendez-vous, quota ou statut CRM n’est
modifié lors d’une ouverture de page Calendly. Les notes de qualification restent dans Orvia.

La [Scheduling API](https://developer.calendly.com/api-docs/calendly-api/scheduled-events/create-event-invitee)
exige un forfait compatible pour le compte concerné. Il faudra prévoir un parcours par page
de réservation pour les comptes sans cette capacité, et une confirmation fiable avant toute
création ou modification d’un rendez-vous CRM. Les scopes et signatures webhooks seront
configurés dans le lot correspondant, sans demander des droits inutilisés dès maintenant.

Références : [OAuth et PKCE](https://developer.calendly.com/docs/authentication/creating-an-oauth-app),
[rotation des jetons](https://developer.calendly.com/docs/authentication/refresh-token-rotation-guide),
[scopes](https://developer.calendly.com/docs/authentication/scopes),
[types d’événements](https://developer.calendly.com/api-docs/calendly-api/event-types/list-event-types).
