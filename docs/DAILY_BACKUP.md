# Sauvegarde quotidienne du VPS et restauration isolée

`scripts/daily_crm_backup.py` est destiné au VPS Linux existant, avec Docker Compose et Python/cryptography système. Il capture chaque base via `pg_dump -Fc`, puis médias privés et configuration, sans arrêt des services ni appel fournisseur. Chaque composant est chiffré/authentifié Fernet avant écriture ; le manifeste chiffré conserve tailles et empreintes. Seule une archive portant le marqueur `complete` est reconnue. Les captures partielles restent diagnostiquables mais ne sont pas restaurables par le programme.

Quand une destination `CRM_BACKUP_S3_*` est complète dans le fichier privé `.git/crm-backup-s3.env`, chaque exécution vérifie d’abord la restauration dans un conteneur sans réseau, puis envoie uniquement les composants chiffrés. Chaque objet est relu depuis le stockage et son SHA-256 comparé avant l’écriture du marqueur distant `complete`. Une copie incomplète n’est donc jamais présentée comme valide. Les credentials ne sont pas ajoutés au `.env` partagé avec les conteneurs applicatifs. Sans configuration distante, le cron actuel continue la sauvegarde/restauration locale et son rapport indique explicitement `uploaded: false`.

```sh
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --verify-restore
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --install-cron
```

La planification conserve les autres entrées du crontab de l’utilisateur de déploiement et ne remplace que sa ligne marquée. Elle s’exécute chaque jour à **04:15 heure du serveur**, avec restauration de contrôle. Sortie dans `.git/crm-daily-backup.log`. Le verrou est partagé avec les déploiements : une exécution concurrente refuse le travail plutôt que croiser migrations et capture ; elle doit être relancée après un échec. La clé reste dans `.git/crm-daily-backup.key` (600), les archives dans `.daily-backups/` (700, fichiers 600), hors Git. Aucune valeur de clé, configuration, donnée métier ou dump clair n’est affichée.

La restauration crée un conteneur neuf depuis l’image déjà utilisée par la base du CRM, avec `--network none`, sans port exposé, sans volume de production et sans démarrage d’application. Les trois dumps sont restaurés dans trois bases neuves par transactions ; tables publiques, migrations et lecture de chaque table sont contrôlées. Le contenu du tar média et l’intégrité de la configuration sont vérifiés sans extraction. Seul le conteneur généré pour ce contrôle et ses volumes temporaires sont supprimés. Le résultat JSON conserve date et compteurs techniques, sans données personnelles.

## Configuration de la destination S3 hors site

Créer chez un fournisseur S3 ou compatible un bucket privé réservé aux sauvegardes, bloquer l’accès public, activer le chiffrement par défaut et prévoir une règle de conservation (par exemple 90 jours). Créer une clé d’accès dédiée limitée à `GetObject` et `PutObject` sous le préfixe choisi ; aucune permission de suppression n’est utilisée. Ne pas réutiliser le bucket média du CRM. Le serveur Linux doit disposer de `python3-boto3` (`sudo apt install python3-boto3`) et continuer à fournir `cryptography` au Python système.

Créer `/opt/amx-crm/.git/crm-backup-s3.env` avec ces variables ; ne jamais les coller dans le chat ni dans Git :

```dotenv
CRM_BACKUP_S3_BUCKET=nom-du-bucket-prive
CRM_BACKUP_S3_REGION=ca-central-1
CRM_BACKUP_S3_ENDPOINT_URL=https://endpoint-du-fournisseur
CRM_BACKUP_S3_PREFIX=orvia-crm-backups
CRM_BACKUP_S3_ACCESS_KEY_ID=identifiant-dedie
CRM_BACKUP_S3_SECRET_ACCESS_KEY=secret-dedie
```

Puis verrouiller ce fichier : `chmod 600 /opt/amx-crm/.git/crm-backup-s3.env`.

Pour AWS S3, laisser `CRM_BACKUP_S3_ENDPOINT_URL` vide. Pour un fournisseur compatible, utiliser son endpoint HTTPS et la région documentée. Le programme refuse un fichier de configuration lisible par le groupe ou le public sous Linux. Le bucket du stockage média n’est pas utilisé.

Avant activation, conserver **séparément du VPS et du bucket** une copie protégée de `.git/crm-daily-backup.key` (gestionnaire de mots de passe ou coffre hors ligne). Cette clé Fernet est indispensable au déchiffrement ; elle n’est jamais envoyée dans le bucket. Sans elle, les sauvegardes distantes sont indéchiffrables. Ne pas l’envoyer par courriel ou dans le chat. La sauvegarde hors site n’est opérationnelle qu’après le premier résultat `uploaded: true` et la vérification du marqueur `complete` dans le bucket.

Après configuration, lancer manuellement le parcours complet avant d’attendre le cron :

```bash
cd /opt/amx-crm
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --verify-restore --require-offsite
```

Le cron quotidien détecte automatiquement une configuration complète et fait le même contrôle avant upload. Les erreurs d’identifiants, réseau, intégrité ou endpoint font échouer le cron. Les objets distants ne sont pas supprimés par ce programme ; la rétention doit être définie par une politique du fournisseur sur le préfixe dédié. La taille reste bornée à 256 Mio par composant, comme pour la sauvegarde locale.

Pour recontrôler une archive complète :

```sh
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --archive /opt/amx-crm/.daily-backups/NOM-ARCHIVE --verify-restore
```

Limites : instantané cohérent par base PostgreSQL, mais captures successives des bases/médias/configuration, sans cohérence transactionnelle entre services. Les écritures continuent pendant la capture ; pour une reprise coordonnée sans écart interservices, prévoir une maintenance et le parcours existant de sauvegarde arrêté. Ce contrôle ne restaure jamais la production, ne rejoue aucun job/appel/courriel, et ne garantit pas un objectif de reprise contractuel. Chaque composant est limité à 256 Mio et reste en mémoire. Redis, rôles globaux et objets externes ne sont pas sauvegardés ; les anciennes sauvegardes de prédéploiement restent distinctes et privées. La copie S3 reste inactive jusqu’à configuration du bucket/identifiants et conservation séparée de la clé Fernet.
