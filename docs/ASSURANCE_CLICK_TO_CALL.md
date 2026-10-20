# Click-to-call Assurance — contrat backend

## Portée

Un setter Assurance actif peut demander explicitement un appel depuis une fiche qu’il a prise en charge. Le portail utilise **son propre poste associé** ; le numéro est exclusivement celui de la fiche. Administrateur et conseiller ne peuvent pas appeler à sa place. Aucun nouveau panneau frontend, émission en masse, audio navigateur, auto-answer, raccrochage ou historique CDR n’est livré ici.

Activation centrale **NEWT_CALLS_ENABLED=false** par défaut. Les secrets `NEWT_USERNAME`/`NEWT_PASSWORD` restent sur le portail. Migration centrale `0013_phonecallattempt` requise. Le service Assurance ne reçoit pas ces identifiants et n’accède pas à la base centrale. La configuration Compose transmet le flag au portail et aux workers héritant de son environnement ; aucun worker n’appelle NEWT en arrière-plan.

## Parcours HTTP explicite

Les commandes ci-dessous sont des modèles opérateur, à exécuter uniquement pour un test autorisé, depuis une session de setter. Remplacer les variables par les valeurs de cette session ; ne pas les enregistrer dans Git. Le poste doit avoir été associé par l’administration. Aucun compte ou poste n’est créé automatiquement.

1. Connexion centrale normale (CSRF + session), puis `POST /api/portal/access/assurance/` avec `{}` : ticket métier court de la session.
2. Avec `Authorization: Bearer <ticket>` : `GET /api/assurance/contacts/<id>/` puis `POST /api/assurance/contacts/<id>/lease/` avec `{}`. Conserver le jeton de prise en charge et la révision actuelle. Si la fiche est déjà en charge par ce navigateur, réutiliser le jeton courant au lieu de la réclamer une seconde fois.
3. Générer un UUID **une seule fois pour cette demande**, puis :

```http
POST /api/assurance/contacts/<id>/call-intent/
Authorization: Bearer <ticket>
Content-Type: application/json

{"request_id":"<uuid>","token":"<jeton-prise-en-charge>","contact_revision":<revision>}
```

Réponse : `proof`, `expires_in: 60`, `request_id`. Preuve signée liée au compte, fiche, version, numéro de composition, jeton de prise en charge et UUID. Elle contient des données de la fiche déjà autorisée : la traiter comme privée et ne pas la journaliser. Ni numéro, ni extension, ni fonction fournisseur ne sont acceptés en paramètres. Le formatage de composition accepte dix chiffres nord-américains ou onze commençant par 1, avec séparateurs usuels ; il ne modifie pas la fiche et n’établit pas la validité ou l’activité de la ligne. Extensions téléphoniques et numéros hors de ce format sont refusés.

4. **Cette commande peut faire sonner le poste si le flag est activé** :

```http
POST /api/portal/assurance/calls/
Cookie: <session-centrale>
X-CSRFToken: <csrf-central>
Content-Type: application/json

{"proof":"<preuve-de-la-fiche>"}
```

Exemple curl après préparation de la session dans un fichier de cookies privé et variables de terminal (pas de relance automatique) :

```powershell
curl.exe --fail-with-body -b $cookieFile -H "X-CSRFToken: $csrf" -H "Content-Type: application/json" --data-binary "@$privateProofBody" http://127.0.0.1:5173/api/portal/assurance/calls/
```

`$privateProofBody` contient seulement le JSON `proof` généré à l’étape précédente. Le flag désactivé renvoie 503 avant réservation/envoi. Une association de poste absente est refusée. Les commandes distinctes du même compte sont espacées d’au moins 60 secondes ; ce délai ne prouve pas que le poste est libre.

5. Pour vérifier la commande sans jamais la relancer :

```http
GET /api/portal/assurance/calls/<uuid>/
Cookie: <session-centrale>
```

Lecture limitée au setter actif propriétaire. Le même POST avec une preuve valide et le même contenu/UUID retourne le registre existant **sans nouvelle commande**. Si la preuve a expiré, consulter par GET ; ne pas créer un nouvel UUID pour compenser une erreur réseau ambiguë. Un changement de contenu sous le même UUID renvoie 409. Ne pas conserver les preuves dans l’historique du navigateur ou un export.

## Protections et sémantique

Réservation durable `dispatching` dans la base centrale **avant** le contact fournisseur, sérialisée par compte et UUID unique. Puis relecture serveur-à-serveur de `call-intent-check` avec ticket Assurance : compte lié à la preuve, fiche, version, numéro et verrou encore détenu/non expiré. Le navigateur ne choisit pas l’URL de relecture. Refus/erreur de cette relecture bloque l’envoi. Les deux bases ne participent pas à une transaction distribuée : une modification immédiatement après ce dernier contrôle reste possible ; la commande emploie le snapshot autorisé. Le réseau interne Assurance doit être de confiance ou protégé par HTTPS.

Un seul GET fournisseur 245 avec source associée, destination autorisée, timeout de sonnerie 30 secondes et corrélation aléatoire. Pas d’auto-answer ni redirection/retry. Réponse bornée à 4 Kio et vérification du CSV, du poste, du numéro et de la corrélation. Une réponse vide, inconnue, HTTP non200 ou une exception n’est jamais considérée comme un succès.

| État | Signification |
|---|---|
| dispatching | Commande réservée ; envoi en cours ou processus interrompu. Pas une preuve d’appel en cours. |
| blocked | Contrôle métier final non favorable ; aucun appel envoyé par ce parcours. |
| accepted | Réponse fournisseur Success corrélée ; acceptation uniquement, pas sonnerie/décrochage. |
| rejected | Réponse fournisseur Failure corrélée. |
| unknown | Résultat ambigu ; ne pas relancer automatiquement. |

Une interruption après réservation ou une erreur de persistance après envoi peut laisser `dispatching`. Aucune reprise automatique n’envoie un second appel. Il n’existe pas encore de rapprochement CDR pour résoudre cet état : examen manuel, conservation de l’UUID et vérification côté poste/fournisseur. Le délai entre commandes n’interdit pas à un utilisateur d’initier volontairement un nouvel UUID après 60 secondes ; ce n’est pas une détection fiable de ligne occupée ni un verrou pendant toute la conversation.

Audit Assurance d’autorisation lié au dossier et à sa version, sans preuve/numéro/jeton. Registre central conservant compte, dossier, extension au moment de l’envoi, empreinte et états ; audit central réservation/résultat sans secrets ni numéro. Réponse au setter : UUID, dossier, état et dates, sans extension ni données fournisseur brutes. Ces deux journaux ne sont pas fusionnés en timeline d’appels du dossier ; pas de durée, résultat commercial ou décrochage déduit. La politique de conservation est à finaliser avant production.

## Vérifications

Tests Assurance : source exclusivement issue de la fiche, non-altération des coordonnées, rôle/espace, lease/version, vérification finale, paramètres interdits et format non composable. Tests portail : poste du compte, flag, CSRF, idempotence, demande en cours/échec ambigu, relecture refusée, preuve expirée, cooldown, statut privé, authentification de la relecture. Adaptateur fournisseur : arguments fixes, corrélation, réponse inconnue et absence de retry/auto-answer. Test de concurrence réelle PostgreSQL : deux soumissions simultanées, une seule émission simulée.

Tous les appels sont **simulés** dans ce lot. La recette manuelle antérieure de 245 ne vaut pas validation réelle de ces nouveaux endpoints. Aucun flag activé ni nouvel appel demandé par leur développement. Isolation, bouton frontend et historique CDR restent des tranches distinctes.
