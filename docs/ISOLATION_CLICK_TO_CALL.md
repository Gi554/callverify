# Click-to-call Isolation — contrat backend

Un setter actif peut demander explicitement un appel pour un prospect qui lui est attribué. Le numéro provient exclusivement de la relation téléphonique normalisée du prospect ; le poste provient de l'association centrale du compte. Administrateur, client et autre setter ne peuvent pas appeler en son nom. La règle du client Isolation unique et les auteurs des activités partagées restent inchangés.

## Configuration et commandes

Migration portail `0015_phonecallattempt_workspace` requise : les commandes historiques sont rattachées à Assurance. Secrets NEWT sur le portail seulement. **NEWT_CALLS_ENABLED=false et NEWT_ISOLATION_CALLS_ENABLED=false** par défaut ; les deux doivent être activés pour une recette Isolation expressément autorisée. Aucune activation ni émission réelle dans ce lot.

1. Ouvrir une session centrale de setter et demander `POST /api/portal/access/isolation/` avec `{}`.
2. Avec son ticket Bearer, consulter `GET /api/isolation/work-queue/<id>/` et conserver `assignment_revision`.
3. Générer un UUID une seule fois, puis demander l'autorisation :

```http
POST /api/isolation/work-queue/<id>/call-intent/
Authorization: Bearer <ticket-isolation>
Content-Type: application/json

{"revision":<assignment_revision>,"request_id":"<uuid>"}
```

Le proxy expose `/api/isolation/` ; la route native du service est `/api/work-queue/`. Réponse privée : `proof`, `expires_in: 60`, `request_id`. Preuve signée liée à l'espace, au compte, prospect, numéro, révision et UUID. Ne pas la journaliser, exporter ou conserver dans Git. Aucun numéro, poste ou paramètre fournisseur arbitraire accepté.

Le prospect doit être attribué au setter, avoir `compliance=allowed`, une validité différente de `invalid`, un téléphone nord-américain normalisé et ne pas figurer dans les exclusions. Une validité inconnue n'est pas transformée en validité confirmée : cette autorisation administrative ne prouve ni activité ni joignabilité de la ligne. Aucun Lookup déclenché, résultat technique ou auteur d'origine modifié.

4. **Peut faire sonner le poste uniquement après activation explicite** :

```http
POST /api/portal/isolation/calls/
Cookie: <session-centrale>
X-CSRFToken: <csrf-central>
Content-Type: application/json

{"proof":"<preuve>"}
```

Exemple opérateur, après préparation privée des cookies et du JSON de preuve :

```powershell
curl.exe --fail-with-body -b $cookieFile -H "X-CSRFToken: $csrf" -H "Content-Type: application/json" --data-binary "@$privateProofBody" http://127.0.0.1:5173/api/portal/isolation/calls/
```

5. Consulter sans réémettre : `GET /api/portal/isolation/calls/<uuid>/` avec la session centrale du setter propriétaire. Réponse : UUID, `workspace=isolation`, `prospect_id`, état et dates, sans poste ni réponse fournisseur brute. Un accès par l'espace Assurance est refusé.

## Garanties et limites

Registre durable avant réseau, sérialisation par compte, UUID unique et contenu identique requis pour un rejeu. Même demande valide : retour du registre sans nouvel envoi. Après expiration de preuve, utiliser le GET ; ne pas compenser une réponse ambiguë par un nouvel UUID. Espacement de 60 secondes partagé avec Assurance pour le même compte, sans garantie de disponibilité physique du poste.

Avant émission, relecture serveur-à-serveur de `call-intent-check` : affectation, version, numéro, conformité et exclusions toujours favorables. Preuve d'un autre espace refusée. Contrôle négatif ou erreur bloque l'émission. Transactions séparées entre services : une modification immédiatement après cette relecture reste possible. Réseau interne de confiance ou HTTPS requis.

Adaptateur 245 partagé avec Assurance, sans auto-answer, retry, redirection, message vocal, campagne ou audio navigateur. `accepted` signifie seulement commande acceptée, jamais sonnerie ou décrochage ; `blocked` signifie contrôle final défavorable ; `rejected` réponse Failure corrélée ; `unknown` résultat ambigu ; `dispatching` réservation en cours ou interrompue. Aucun de ces deux derniers états n'est relancé automatiquement. Une interruption peut nécessiter un examen manuel ; aucun rapprochement CDR livré (511 reste bloqué en recette fournisseur).

Audit métier d'autorisation conservant identifiant et nom du setter, prospect, UUID et révision, sans preuve ni numéro. Audit central de réservation/résultat et registre privés au setter par ces routes. Pas de nouvel historique d'appels partagé au client : visibilité des auteurs existants préservée, sans publier le registre technique. Durée, décrochage et résultat commercial non déduits. Conservation à préciser avant production.

## Vérification

Six tests métier : affectation/rôle/espace, source et révision, paramètres injectés, conformité/exclusion/téléphone, changement avant contrôle final, preuve expirée ou d'un autre espace. Cinq tests centraux : registre privé/idempotence, flags/rôle/espace, relecture ciblée, blocage sans réémission et délai partagé. Régression Assurance et suites core/portail exécutées ; concurrence centrale PostgreSQL existante et tests métier intégrés à la CI PostgreSQL. Tous les fournisseurs simulés. Aucun bouton frontend, historique CDR, raccrochage ou recette réelle des nouveaux endpoints livré.
