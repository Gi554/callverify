# Confirmation avec contrôle d'agenda externe — Assurance

## Parcours livré

Les API existantes de création et déplacement de rendez-vous Assurance consultent désormais le portail **côté serveur** après leurs contrôles métier et de chevauchement interne, avant de confirmer en base. Le navigateur ne fournit aucun indicateur permettant de sauter ce contrôle. Annuler un rendez-vous ne consulte pas l'agenda externe ; rejouer une création déjà confirmée retrouve la réservation sans nouveau contrôle réseau.

Le conseiller actif reste le propriétaire de son agenda Google ou Microsoft principal. Le setter ou administrateur actif peut réserver sans connaître ses identifiants OAuth ni les détails de ses événements. Un conflit renvoie HTTP 409 ; un fournisseur, une connexion ou le portail indisponible renvoie 503 et aucune réservation/modification n'est confirmée. L'échec ne consomme pas l'UUID de création, qui peut être réutilisé après résolution du problème.

Sans connexion externe antérieure, le contrôle retourne explicitement `internal_only` : seules les réservations internes sont rapprochées. Un compte autrefois connecté mais déconnecté doit être reconnecté ; il n'est jamais traité comme libre. Les périodes sont limitées à 31 jours. Le champ de réponse métier `calendar=internal` est conservé : l'autorité reste le CRM et cette vérification ne publie pas elle-même d'événement externe.

En cas de déplacement, seul l'événement AMX correspondant à ce rendez-vous et à ce conseiller peut être exclu de la recherche des occupations : registre synchronisé, fournisseur, identifiant, marque AMX et intervalle attendu contrôlés. Un registre actif ambigu ou un événement modifié bloque la confirmation ; aucun identifiant d'événement arbitraire reçu du navigateur. La publication unidirectionnelle existante reste distincte et facultative.

## Configuration et commandes

Assurance : `PORTAL_INTERNAL_URL=http://127.0.0.1:8090` en développement, adresse HTTP interne du portail dans Compose. Valeur obligatoire en production, aucun repli permettant de contourner le contrôle. Les secrets OAuth restent exclusivement sur le portail. Les deux services partagent la clé de tickets Assurance déjà requise. Le réseau interne doit être de confiance ou utiliser HTTPS. Le nom `portal` est autorisé dans le Compose.

Le contrat public de réservation est inchangé, voir la documentation des rendez-vous existants. Exemple de commande depuis une session/ticket setter préparés, JSON privé contenant les paramètres métier et la preuve centrale habituelle :

```powershell
curl.exe --fail-with-body -H "Authorization: Bearer $ticket" -H "Content-Type: application/json" --data-binary "@$privateBookingBody" http://127.0.0.1:5173/api/assurance/appointments/
```

Le portail reçoit uniquement une preuve de service signée de 120 secondes sur `POST /api/portal/internal/assurance/calendar-check/`. Elle lie acteur, rôle, conseiller, intervalle et éventuel rendez-vous d'origine. Un ticket de session/espace n'est pas une preuve de service. Réponse bornée sans événement, secret, titre ou participant : `result` (`free`, `busy`, `internal_only`) et `checked_at`. Aucun appel à cette route n'est nécessaire depuis le navigateur. Limitation actuelle de 20 contrôles/minute par IP de service, dans le cache local du portail ; une limite atteinte bloque la confirmation, sans repli interne silencieux.

Une preuve de contrôle libre n'est pas remise au navigateur pour être réutilisée : le service appelle directement lors de chaque nouvelle confirmation. Audit métier de création/déplacement : résultat et date du contrôle. Audit central minimal : acteur, conseiller, source et résultat ; pas d'horaires privés issus des événements. Les erreurs de renouvellement peuvent désactiver la connexion et nécessiter une reconnexion.

## Vérification et limites

Tests : réservation/déplacement bloqués et annulés transactionnellement, rejouabilité de l'UUID après refus, idempotence après succès, absence de contrôle pour annulation, audit, transport signé/strict, Google/Microsoft occupé/libre, compte jamais connecté/déconnecté, expiration/rôles, fournisseur indisponible et exclusion d'un seul événement AMX vérifié. Concurrence PostgreSQL : deux contrôles renouvellent une seule fois le jeton expiré ; réservations internes concurrentes toujours sérialisées. Fournisseurs simulés exclusivement, aucune recette OAuth réelle ni nouvel appel téléphonique.

Le contrôle lit une photographie de l'agenda principal, sans poser de verrou chez Google/Microsoft. Une modification externe juste après le contrôle peut encore créer un conflit. Les transactions internes restent ouvertes pendant la lecture réseau ; le client interservice attend au maximum 90 secondes d'inactivité réseau, sans retry ni redirection, et le serveur web peut interrompre plus tôt selon son timeout. Dimensionnement des workers, limitation distribuée, surveillance, recette fournisseur et éventuelles améliorations asynchrones restent nécessaires pour la production. Aucun détail d'agenda du conseiller n'est publié au setter. Isolation reste la prochaine tranche ; Calendly, interface finale et synchronisation bidirectionnelle restent reportés.


## Extension Isolation (lot 65)

La tranche Isolation a ensuite été livrée : ISOLATION_EXTERNAL_CALENDAR.md. Le transport commun et le protocole sont partagés, avec clés, signatures et connexions séparées par espace ; le propriétaire est le client Isolation unique. Les limites ci-dessus restent applicables aux deux espaces.
