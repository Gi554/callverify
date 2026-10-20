# Exploitation et recette

## Contrôles exécutables

```powershell
$env:DEBUG='true'
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe manage.py test
```

Les tests vérifient les frontières d'accès, la MFA obligatoire, le chiffrement et les codes de secours, le CSRF, les imports, les budgets, l'outbox, les exports, la purge, les autorisations et les webhooks. Twilio est simulé. La suite a été exécutée sur SQLite et PostgreSQL ; les tests de concurrence et de charge au volume cible restent à compléter.

## Après une interruption

Rétablir PostgreSQL et Redis, puis :

```sh
python manage.py requeue_jobs
```

Imports déjà terminés : aucun retraitement. Lookup : les `pending` peuvent être redispatchés, les `running` demandent une vérification fournisseur. Beat redispatche l'outbox toutes les 30 secondes et purge les fichiers expirés chaque heure. Après 25 échecs de publication, la demande passe en `failed` et nécessite un examen. Les imports invalides demandent une correction ; une relance explicite est disponible depuis l'interface.

## Sauvegarde et restauration avant production

Le parcours PostgreSQL unitaire chiffré avec restauration en base neuve est décrit dans [BACKUP_POSTGRES.md](BACKUP_POSTGRES.md). Il ne couvre pas encore les médias externes, la copie hors site ou la recette de l’hébergement client.

Pour les trois bases **SQLite locales** et les fichiers privés, utiliser le parcours chiffré avec restauration sans écrasement décrit dans [BACKUP_LOCAL.md](BACKUP_LOCAL.md). Ce parcours est testé sur données jetables ; il ne couvre pas PostgreSQL/S3 ou la sauvegarde externe de production décrite ci-dessous.

1. Sauvegarder PostgreSQL avec `pg_dump` dans un dépôt chiffré privé.
2. Sauvegarder le volume média ou activer le versionnage du stockage objet privé.
3. Restaurer la base et les fichiers dans un environnement isolé.
4. Contrôler les comptes, nombres de campagnes/imports/lignes et téléchargements privés.
5. Garder Lookup désactivé pendant la restauration ; ne pas rejouer de travail fournisseur ambigu.
6. Consigner les résultats et les durées de reprise. Une sauvegarde `pg_dump -Fc` et une restauration `pg_restore` ont été exécutées sur une base PostgreSQL jetable. Répéter cette procédure avec votre stockage média et le chiffrement de l'hébergement retenu.

## Exposition publique

Prévoir un reverse proxy HTTPS configuré pour le nom de domaine réel. Les URL vues par Django doivent correspondre aux URL signées par Twilio. Configurer l'en-tête du proxy uniquement si le proxy le supprime et le réécrit lui-même. Ne pas désactiver la validation de signature pour contourner une mauvaise configuration.

Exécuter `python manage.py check --deploy` avec la configuration finale. Les secrets Twilio et SMTP restent exclusivement dans l'environnement serveur. Chiffrer la base et les sauvegardes contenant les secrets MFA.
