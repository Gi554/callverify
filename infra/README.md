# Démarrage du socle CRM

Le portail est une première tranche de développement, pas une version de production complète. Voir docs/CRM_AMX_PLAN.md pour les limites et les lots métier restants.

## Local

Dans des terminaux distincts à la racine :

```powershell
./scripts/dev.ps1
./scripts/crm.ps1 -Service portal
./scripts/crm.ps1 -Service assurance
./scripts/frontend.ps1
```

Accès : http://127.0.0.1:5173/crm. L'application historique reste sur /. Le portail n'affiche que les espaces explicitement attribués ; un seul espace entraîne une redirection directe. Les rôles setter/client Isolation restent bloqués jusqu'au développement de leurs routes métier.

Les bases locales db.sqlite3 (Isolation), assurance.sqlite3 et portal.sqlite3 sont distinctes et ignorées par Git. Les secrets de développement sont des valeurs locales explicites ; en production les clés indépendantes sont obligatoires.

Créer un compte central avec `manage.py createsuperuser --settings=portal.backend.settings` (saisie privée). En local seulement, `manage.py import_local_account NOM --settings=portal.backend.settings` copie le hash d'un compte historique existant sans écraser un compte central. Aucun droit métier n'est accordé par la copie.

```powershell
./.venv/Scripts/python.exe manage.py grant_workspace NOM assurance administrator --settings=portal.backend.settings
./.venv/Scripts/python.exe manage.py grant_workspace NOM isolation administrator --settings=portal.backend.settings
```

Les administrateurs centraux ne disposent pas automatiquement des données métier. La procédure locale ne remplace pas une migration des comptes et des MFA en production.

## Conteneurs

Ajouter les variables de .env.crm.example au .env privé puis :

```bash
docker compose -f compose.yaml -f infra/compose.crm.yaml up --build -d
docker compose -f compose.yaml -f infra/compose.crm.yaml exec portal python manage.py migrate --settings=portal.backend.settings
docker compose -f compose.yaml -f infra/compose.crm.yaml exec assurance python manage.py migrate --settings=apps.assurance.backend.settings
```

Les services utilisent des bases et identifiants PostgreSQL indépendants. Aucun port PostgreSQL n'est publié sur l'hôte. Ajouter compose.production.yaml et le domaine pour la configuration HTTPS. La production reste conditionnée aux exigences MFA, récupération, invitations, sauvegardes, contrôle des sessions et recette métier.
