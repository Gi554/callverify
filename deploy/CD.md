# Déploiement continu sur Ubuntu

La pipeline `.github/workflows/cd.yml` met à jour une **installation déjà initialisée**.
Elle reste désactivée tant que la variable GitHub `CD_ENABLED` n’est pas `true`.
Le VPS n’est pas configuré par la présence de ce workflow dans le dépôt.

## Première installation

1. Choisir un domaine ou sous-domaine et faire pointer son DNS A vers le VPS.
2. Vérifier la version d’Ubuntu et installer Docker Compose v2, Git, curl, tar et util-linux (`flock`).
3. Créer un utilisateur SSH dédié au déploiement, par exemple `amx-deploy`, puis lui permettre
   d’utiliser Docker. Cet accès Docker donne des pouvoirs élevés sur le serveur : conserver sa clé
   uniquement dans le secret GitHub prévu, sans la publier ni la coller dans le chat.
4. Cloner le dépôt dans un chemin fixe sans espaces, par exemple `/opt/amx-crm` ; ce dossier,
   son `.git`, ses fichiers de configuration et ses sauvegardes doivent appartenir à cet utilisateur.
   Conserver une copie indépendante de la clé d’accès administrateur du VPS.
5. Suivre [README.md](README.md) pour créer le `.env` privé, configurer SMTP et faire
   le premier `bash scripts/deploy.sh`, puis créer le premier administrateur.
6. Vérifier manuellement `https://DOMAINE/crm`, la connexion et les deux espaces.
   La téléphonie reste désactivée tant qu’elle n’a pas été explicitement configurée.

Une IP et un compte root ne suffisent pas à activer le CD : il faut aussi l’accès SSH par clé,
l’identité du serveur vérifiée, le domaine HTTPS et la première installation fonctionnelle.
Ne pas désactiver HTTPS ou le contrôle de clé hôte pour contourner cette préparation.

## Configuration GitHub

Créer l’environnement **production** dans Settings → Environments. Des approbateurs peuvent
y être configurés si souhaité ; ils seront sollicités par GitHub avant le déploiement.

Variables de dépôt (Settings → Secrets and variables → Actions → Variables) :

| Variable | Valeur |
|---|---|
| `CD_ENABLED` | Laisser absent ou `false` jusqu’à la recette initiale ; `true` pour activer |
| `CD_HOST` | IP ou nom SSH du VPS |
| `CD_PORT` | Port SSH, `22` par défaut |
| `CD_USER` | Utilisateur dédié, par exemple `amx-deploy` |
| `CD_PATH` | Chemin absolu du clone, par exemple `/opt/amx-crm` |

`CD_ENABLED` doit être une variable de dépôt : le garde-fou est évalué avant l’ouverture
de l’environnement `production`, donc ne pas la définir uniquement dans cet environnement.

Secrets de l’environnement **production** :

| Secret | Contenu |
|---|---|
| `CD_SSH_KEY` | Clé privée dédiée, correspondant à une clé publique autorisée sur le VPS |
| `CD_KNOWN_HOSTS` | Ligne(s) known_hosts du serveur vérifiées par un canal de confiance |

Vérifier l’empreinte SSH depuis la console du fournisseur ou une connexion déjà approuvée
avant d’enregistrer `CD_KNOWN_HOSTS`. Une collecte réseau seule ne constitue pas cette vérification.
Pour un port non standard, la ligne doit correspondre à `[hôte]:port`.
Le workflow impose `StrictHostKeyChecking=yes` et n’exécute pas de `ssh-keyscan` automatique.
Les secrets métier (base, SMTP, NEWT, agendas) restent dans le `.env` du VPS, jamais dans Git.

## Ce qui se passe à chaque mise à jour

Après une fusion dans `main`, le workflow **Validate CRM services** doit réussir sur le push.
Les validations de PR, branches et dépôts externes ne peuvent pas déclencher le CD.
Le workflow vérifie que le commit validé est encore la tête de `main`, puis se connecte par SSH
et transmet `scripts/deploy-release.sh` depuis ce commit. Aucun artefact de PR n’est exécuté.

Sur le serveur, le script :

1. Prend un verrou ; refuse un clone avec des modifications de fichiers suivis.
2. Récupère `main` et vérifie à nouveau le SHA exact ; ignore les commits dépassés.
3. Refuse une installation dont les bases ou l’API ne tournent pas.
4. Sauvegarde les trois bases (`pg_dump -Fc`, table des matières relue par `pg_restore`),
   les fichiers importés et le `.env` dans `.backups/DATE-SHA-PID`, avec accès privé.
   Les commits précédent et cible sont enregistrés. Les sauvegardes sont exclues de Git et du build Docker.
5. Passe au commit validé, reconstruit, migre et relance via `scripts/deploy.sh`.
   Compose attend les services jusqu’à 180 secondes.
6. Contrôle `/crm` sur le HTTPS public et les réponses non authentifiées attendues (401/403)
   des trois API. Le SHA est marqué réussi uniquement après ces contrôles.

Un déploiement n’est pas interrompu par une fusion suivante ; un verrou serveur protège aussi
contre les exécutions concurrentes hors GitHub. Si une exécution échoue après le checkout,
relancer la validation du commit courant permet une nouvelle tentative : seul un SHA déjà
marqué réussi est ignoré. Un ancien SHA n’est pas déployé si `main` a avancé.

## Échec et restauration

En cas d’échec de sauvegarde, le checkout et les migrations ne commencent pas.
En cas d’échec de migration ou de contrôle HTTP, la pipeline échoue et les sauvegardes restent
sur le serveur. Le commit précédent n’est **pas** remis automatiquement : une migration peut
avoir changé les données et rendre l’ancien code incompatible.

Pour restaurer, examiner d’abord l’état des bases et les journaux, suspendre les écritures,
puis choisir une restauration cohérente des bases, des fichiers et du code selon
[BACKUP_POSTGRES.md](../docs/BACKUP_POSTGRES.md). Tester la procédure sur une copie avant
de remplacer des données actives. Garder le `.env` original et ses clés avec les archives.

Limites : reconstruction sur le VPS, possible interruption pendant les migrations ; pas de
déploiement sans interruption ni rollback automatique. Les sauvegardes sont faites sur une
application en fonctionnement : elles ne constituent pas un instantané atomique entre les
trois bases et les fichiers. Leur copie hors serveur, chiffrement, rétention et restauration
périodique doivent être configurés séparément. Les contrôles HTTP testent la disponibilité
des routes, pas tous les parcours authentifiés. La première recette sur le VPS reste nécessaire.
