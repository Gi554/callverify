# Mettre le CRM AMX en ligne

Ce guide installe le CRM sur un serveur, avec HTTPS automatique. Le serveur fait tourner 16 services Docker : trois bases PostgreSQL, Redis, l’API Isolation, le portail, Assurance, les tâches de fond, l’interface et Caddy pour le HTTPS. Aucun secret n’est stocké dans le dépôt.

## 1. Ce qu’il faut avant de commencer

| Élément | Détail |
|---|---|
| Un serveur Linux | Ubuntu 24.04, 2 processeurs, 4 Go de mémoire et 40 Go de disque au minimum. Par exemple un VPS OVH, Hetzner ou DigitalOcean, de préférence au Canada. |
| Un nom de domaine | Par exemple `crm.votre-entreprise.com`. |
| Un enregistrement DNS | Type **A** du domaine vers l’adresse IP du serveur, à créer chez votre registraire. |
| Un compte d’envoi d’e-mails (SMTP) | Pour les invitations, les mots de passe oubliés et les rappels : Google Workspace, Microsoft 365, Brevo, Mailgun… |
| Ports ouverts | 80 et 443 (web) et 22 (SSH) sur le pare-feu du serveur. |

## 2. Préparer le serveur (une seule fois)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # puis se reconnecter
git clone https://github.com/Gi554/callverify.git crm && cd crm
```

## 3. Créer la configuration (une seule fois)

```bash
python3 scripts/generate_production_env.py crm.votre-entreprise.com
```

Le script crée le fichier `.env` avec toutes les clés et tous les mots de passe internes, générés au hasard. Ensuite :

1. Ouvrez `.env` (par exemple avec `nano .env`) et complétez la section **E-mails** : serveur, identifiant et mot de passe SMTP.
2. **Copiez `.env` dans un coffre-fort** (gestionnaire de mots de passe de l’entreprise). Sans ce fichier, les données chiffrées, les sessions et les e-mails en attente sont perdus.
3. Laissez la téléphonie à `false` tant que les appels ne sont pas ouverts. Pour les activer plus tard, renseignez `NEWT_USERNAME`, `NEWT_PASSWORD` et `NEWT_CALLS_ENABLED=true`, puis relancez le déploiement.

## 4. Déployer

```bash
./scripts/deploy.sh
```

Le script vérifie la configuration, construit l’application, met à jour les trois bases de données, lance les contrôles de sécurité Django, puis démarre tout. Caddy obtient le certificat HTTPS automatiquement ; il faut que le DNS pointe déjà vers le serveur.

## 5. Créer le premier administrateur (une seule fois)

```bash
./scripts/create_admin.sh prenom.nom
```

Le mot de passe est demandé de façon masquée. Cet administrateur a accès à Assurance et à Isolation. Il invite ensuite tous les autres utilisateurs depuis le CRM (**Utilisateurs et accès → Invitations**). Chacun reçoit un e-mail et choisit son mot de passe.

## 6. Mettre à jour

Pour automatiser les mises à jour après validation de `main`, suivre [la configuration du CD](CD.md).
La pipeline reste désactivée jusqu’à la première installation, la recette HTTPS et la configuration SSH.

```bash
git pull
./scripts/deploy.sh
```

Les migrations sont appliquées automatiquement, et les données sont conservées dans les volumes Docker.

## 7. Sauvegardes (à mettre en place dès le premier jour)

- **Bases** : chaque nuit, `pg_dump -Fc` des trois bases (`db`, `portal-db`, `assurance-db`). Voir `docs/BACKUP_POSTGRES.md`.
- **Fichiers** : le volume `media` (documents importés).
- **Hors du serveur** : gardez les archives sur un autre stockage, avec le fichier `.env` dans le coffre-fort.
- **Restauration** : testez une restauration au moins une fois, sur une machine séparée.

## 8. En cas de souci

| Problème | Que faire |
|---|---|
| Voir l’état des services | `docker compose -f compose.yaml -f infra/compose.crm.yaml -f compose.production.yaml ps` |
| Lire les journaux d’un service | Même commande avec `logs -f portal` (ou `assurance`, `api`, `caddy`). |
| Le HTTPS ne s’obtient pas | Vérifiez que le DNS pointe bien vers le serveur et que les ports 80 et 443 sont ouverts, puis consultez les journaux de `caddy`. |
| Les e-mails ne partent pas | Vérifiez la section E-mails de `.env` et les journaux de `portal-mail`. |
