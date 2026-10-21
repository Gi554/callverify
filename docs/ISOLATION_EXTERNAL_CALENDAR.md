# Disponibilités externes des visites Isolation

## Comportement livré

Les créations et déplacements de visites interrogent maintenant l'agenda principal Google/Microsoft du **client Isolation unique**, après les contrôles de rôle, affectation, version et chevauchement interne. Aucun indicateur envoyé par le navigateur ne désactive ce contrôle. Le client ne réserve pas lui-même : les setters affectés et administrateurs conservent leurs droits existants. Le setter d'origine et l'auteur de réservation restent distincts et visibles selon les règles Isolation.

Créneau occupé : HTTP 409. Portail indisponible, fournisseur en erreur ou ancienne connexion perdue : HTTP 503 et aucune modification de visite ou de révision du prospect. L'UUID peut être repris après résolution d'un refus. Une réservation déjà confirmée est retrouvée sans nouvelle lecture externe. Annuler ne dépend pas du fournisseur. Sans connexion externe antérieure, le contrôle est explicitement `internal_only` et ne certifie aucune disponibilité externe.

Lors d'un déplacement, seul l'événement AMX de cette visite dans la connexion de ce client peut être exclu. Le registre synchronisé, le fournisseur, l'identifiant, la marque AMX et l'intervalle attendu doivent correspondre. Un état ambigu bloque le contrôle. Le navigateur ne choisit aucun événement à ignorer. L'audit métier conserve le résultat et la date du contrôle ; aucun titre, participant ou contenu d'événement externe n'est transmis au setter ni enregistré dans cet audit.

## Configuration et utilisation

Isolation doit joindre le portail à `PORTAL_INTERNAL_URL` : `http://127.0.0.1:8090` en développement ; `http://portal:8000` dans Compose. Pas de repli silencieux en cas d'échec. Secrets OAuth sur le portail uniquement ; clés de signature distinctes par espace, déjà requises pour les tickets. Preuve de service limitée à 120 secondes, liée à l'espace, acteur, rôle, client, intervalle et éventuelle visite d'origine. Un ticket métier ou une preuve Assurance ne sont pas acceptés sur `/api/portal/internal/isolation/calendar-check/`.

Le contrat public des visites ne change pas. Après préparation d'un ticket Isolation et du JSON privé habituel (preuve de réservation centrale, prospect, version, dates/fuseau et UUID) :

```powershell
curl.exe --fail-with-body -H "Authorization: Bearer $ticket" -H "Content-Type: application/json" --data-binary "@$privateVisitBody" http://127.0.0.1:5173/api/isolation/visits/
```

Le proxy `/api/isolation/` réécrit vers `/api/` du service. Dates avec décalage explicite cohérent avec le fuseau, intervalle positif limité à 31 jours. La réponse conserve `calendar=internal` : le CRM reste l'autorité ; publication externe facultative distincte. Les preuves de service ne sont ni fournies ni demandées au navigateur. Pas de nouvelle migration ou interface.

## Vérifications et limites

Tests publics : refus occupé/indisponible avec rollback, réutilisation de l'UUID, rejeu sans réseau, déplacement de la bonne visite, annulation hors ligne, conservation des participants et audit. Tests centraux : espaces/preuves distincts, client actif unique, interne/libre/occupé, échec fournisseur et exclusion contrôlée. Régressions Assurance et suites complètes exécutées. Test PostgreSQL de renouvellement concurrent du jeton Isolation et de réservations concurrentes dans la CI. Fournisseurs simulés exclusivement, aucun appel téléphonique ni recette OAuth réelle.

Les mêmes limites que [la confirmation Assurance](BOOKING_EXTERNAL_CALENDARS.md) s'appliquent : photographie sans verrou chez le fournisseur, agenda principal uniquement, transactions ouvertes pendant lecture réseau, timeout du serveur web à dimensionner, quota local de 20 contrôles/minute par IP partagé sur les routes d'agenda. Ce contrôle ne réserve ni ne publie lui-même un événement externe ; un changement immédiatement après la lecture reste possible. Réseau interne de confiance ou HTTPS requis. Interface finale, Calendly, synchronisation bidirectionnelle et recette réelle des connexions restent distincts.
