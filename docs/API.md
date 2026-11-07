# API CallVerify

## Authentification du portail CRM central

Les routes centrales utilisent `/api/portal/` et sont distinctes de l’ancienne authentification CallVerify décrite ci-dessous. Lorsque `MFA_ENABLED=true` (défaut), les administrateurs centraux doivent activer une application TOTP avant d’ouvrir leur espace ; une connexion protégée demande le code TOTP à six chiffres. Chaque code TOTP ne peut être réutilisé. Dix codes de secours à usage unique sont remis lors de l’activation ; les secrets sont chiffrés avec `MFA_ENCRYPTION_KEY`, et les codes de secours sont hachés. Une nouvelle série exige le mot de passe et un nouveau code TOTP. `MFA_ENABLED=false` désactive les demandes MFA sur le portail et l’API d’enrôlement; les facteurs existants restent stockés pour une éventuelle réactivation.

| Méthode | Route | Utilisation |
| --- | --- | --- |
| POST | `/api/portal/mfa/` | Session centrale authentifiée : `{action: "enroll"}` retourne URI TOTP et QR privés ; `{action: "confirm", code}` active la MFA et retourne les codes de secours une seule fois ; `{action: "backup", password, code}` renouvelle les codes. |
| POST | `/api/portal/login/` | `{username, password, workspace?, code?}` ; si MFA activée, un TOTP ou code de secours est requis. Un administrateur sans MFA est dirigé vers l’activation avant accès aux routes CRM. |

En production, `MFA_ENCRYPTION_KEY` doit être configurée avec une clé Fernet stable et conservée hors Git. Toute rotation de cette clé nécessite de ré-encrypter les secrets MFA avant de remplacer l’ancienne clé. Les codes et QR ne sont pas mis en cache.

La MFA centrale est livrée pour les comptes administrateurs. Les clés de sécurité WebAuthn, le SSO, une console administrateur de réinitialisation et les facteurs MFA des rôles non administrateurs ne sont pas inclus.

## API CallVerify historique

Base : `/api/`. Toutes les routes métier demandent un administrateur actif. Un administrateur accède à ses campagnes ; un superadministrateur accède à toutes. Les listes renvoient `{count, next, previous, results}` : 25 lignes par défaut, `page_size` configurable jusqu'à 100, navigation via `page`. La liste d'administrateurs est un tableau non paginé.

| Méthode | Route | Utilisation |
| --- | --- | --- |
| GET | auth/csrf/ | Cookie et token CSRF |
| POST | auth/login/ | `{username, password, code?}` ; code TOTP obligatoire pour superadmin lorsque `MFA_ENABLED=true` |
| GET | auth/session/ | Identité courante |
| POST | auth/session/ | Déconnexion |
| POST | auth/mfa/ | `{action: "enroll"}` puis `{code: "123456"}` |
| POST | auth/reset/request/ | `{email}` ; réponse générique, email envoyé par SMTP configuré |
| POST | auth/reset/confirm/ | `{uid, token, password}` ; lien valable une heure, usage unique |
| GET/POST | administrators/ | Superadmin ; création `{username, email, password}` ou `{username, email, invite: true}` |
| PATCH | administrators/ | Superadmin ; suspension `{id, is_active: false}` |
| GET/POST | campaigns/ | Création `{name, purpose, source, budget}` |
| GET/PATCH | campaigns/{id}/ | Lecture / modification de la campagne |
| POST | campaigns/{id}/archive/ | Archivage ; suppression physique interdite |
| POST | campaigns/{id}/lookup/ | `{force: false}` ; retourne scheduled, cached, cost_type |
| GET | dashboard/ | Compteurs limités aux campagnes visibles |
| POST | imports/ | Multipart : `campaign`, `file`, `sheet` facultatif ; retourne id, headers, preview, rows, sheets |
| POST | imports/{id}/confirm/ | `{mapping: {phone: "telephone", name: "nom", reference: "reference"}}` |
| GET | imports/{id}/ | Statut et rapport total/valid/invalid/duplicates/empty |
| GET | prospects/ | Filtres campaign, validity, compliance, phone__line_status, search |
| GET | prospects/{id}/ | Contact et classifications |
| GET | prospects/{id}/history/ | Vérifications de ce numéro dans cette campagne |
| GET | lookups/ | Résultats, réponses Basic, erreurs et réserves de coûts |
| POST | consents/ | `{prospect, basis, evidence, expires_at}` ; conserve la preuve sans autoriser automatiquement |
| GET/POST/PATCH/DELETE | suppressions/ | Superadmin ; `{e164, reason}` ; PATCH/DELETE sur suppressions/{id}/ |
| POST | calls/ | `{campaign, configuration: {...}}` ; préparation uniquement |
| POST | calls/{id}/start/ | HTTP 409, appels réels non activés |
| POST | calls/{id}/stop/ | Arrêt de la préparation |
| POST | webhooks/twilio/voice/ | Form-urlencoded signé par Twilio ; compte et CallSid connus requis |
| POST | exports/ | `{campaign, format: "csv", columns: [...], filters: {...}}` |
| GET | exports/{id}/ | Statut, expiration et éventuelle erreur |
| GET | exports/{id}/download/ | Téléchargement privé tant que le fichier est disponible et non expiré |
| GET | audit/ | Superadmin ; journal immuable via l'API |

Colonnes d'export : `name`, `reference`, `raw_phone`, `e164`, `validity`, `line_status`, `compliance`, `reason`, `checked_at`. Filtres d'export : `validity`, `compliance`, `phone__line_status`.

Invitation : la réponse de création fournit `invitation: {uid, token}`. Construire un lien vers la page de définition de mot de passe et le transmettre par un canal privé. La plateforme ne transmet pas elle-même l'invitation. Aucun secret d'invitation ne figure dans l'audit.

Validité locale : `valid` ou `invalid` ; défaut du modèle `indeterminate`. Joignabilité : `unknown` tant qu'aucune source ne la justifie. Conformité : `review` par défaut ; aucun endpoint ne transforme une preuve brute en permission automatique.

Erreurs attendues : 400 saisie invalide, 401 identifiants invalides, 403 permission/CSRF/signature, 404 objet non visible, 409 lancement Voice bloqué, 429 limite de débit. Les téléchargements expirés répondent 400.

Les tâches de production répondent 202 ; interroger ensuite leur détail. En mode local eager, elles s'exécutent avant le retour et le détail peut déjà indiquer `completed`.

Fonctions complémentaires : `POST imports/{id}/preview/` avec `{sheet}`, `GET imports/{id}/report/`, `POST imports/{id}/retry/`, `POST prospects/{id}/classify/` avec `{compliance, reason}`, `GET calls/{id}/eligibility/`, `GET/PATCH settings/` (superadmin), `GET notifications/`, `GET health/` (sans authentification). `POST lookups/{id}/reconcile/` demande un superadmin et `{actual_cost, invoice_reference}` ; la réserve et le coût facturé restent séparés.

`auth/mfa/` : enroll retourne secret, URI et QR SVG ; confirmer avec `{code}` retourne dix codes de secours affichés une seule fois. Leur renouvellement demande `{action: "backup", password, code}` avec un nouveau TOTP. Les codes sont hachés en base et consommés au login. Les secrets MFA sont chiffrés avec Fernet.

`PATCH administrators/` accepte également `{id, role: "administrator" | "superadministrator"}`. Une promotion exige un MFA actif ; le compte courant ne peut pas modifier son propre rôle/état. Lookup conserve `checked_at`, les réponses des packages facultatifs et leurs codes d'erreur. Les exports acceptent aussi carrier, line_type et compliance_reason.

Références fournisseur : [Twilio Line Type Intelligence](https://www.twilio.com/docs/lookup/v2-api/line-type-intelligence) et [Twilio Line Status](https://www.twilio.com/docs/lookup/v2-api/line-status). Leur disponibilité et leur tarification canadiennes doivent être confirmées sur le compte utilisé.
