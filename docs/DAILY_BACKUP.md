# Sauvegarde quotidienne du VPS et restauration isolée

`scripts/daily_crm_backup.py` est destiné au VPS Linux existant, avec Docker Compose et Python/cryptography système. Il capture chaque base via `pg_dump -Fc`, puis médias privés et configuration, sans arrêt des services ni appel fournisseur. Chaque composant est chiffré/authentifié Fernet avant écriture ; le manifeste chiffré conserve tailles et empreintes. Seule une archive portant le marqueur `complete` est reconnue. Les captures partielles restent diagnostiquables mais ne sont pas restaurables par le programme.

```sh
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --verify-restore
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --install-cron
```

La planification conserve les autres entrées du crontab de l’utilisateur de déploiement et ne remplace que sa ligne marquée. Elle s’exécute chaque jour à **04:15 heure du serveur**, avec restauration de contrôle. Sortie dans `.git/crm-daily-backup.log`. Le verrou est partagé avec les déploiements : une exécution concurrente refuse le travail plutôt que croiser migrations et capture ; elle doit être relancée après un échec. La clé reste dans `.git/crm-daily-backup.key` (600), les archives dans `.daily-backups/` (700, fichiers 600), hors Git. Aucune valeur de clé, configuration, donnée métier ou dump clair n’est affichée.

La restauration crée un conteneur neuf depuis l’image déjà utilisée par la base du CRM, avec `--network none`, sans port exposé, sans volume de production et sans démarrage d’application. Les trois dumps sont restaurés dans trois bases neuves par transactions ; tables publiques, migrations et lecture de chaque table sont contrôlées. Le contenu du tar média et l’intégrité de la configuration sont vérifiés sans extraction. Seul le conteneur généré pour ce contrôle et ses volumes temporaires sont supprimés. Le résultat JSON conserve date et compteurs techniques, sans données personnelles.

Pour recontrôler une archive complète :

```sh
python3 scripts/daily_crm_backup.py --root /opt/amx-crm --archive /opt/amx-crm/.daily-backups/NOM-ARCHIVE --verify-restore
```

Limites : instantané cohérent par base PostgreSQL, mais captures successives des bases/médias/configuration, sans cohérence transactionnelle entre services. Les écritures continuent pendant la capture ; pour une reprise coordonnée sans écart interservices, prévoir une maintenance et le parcours existant de sauvegarde arrêté. Ce contrôle ne restaure jamais la production, ne rejoue aucun job/appel/courriel, et ne garantit pas un objectif de reprise contractuel. Chaque composant est limité à 256 Mio et reste en mémoire. Aucun stockage distant, purge automatique ni sauvegarde de Redis, rôles globaux et objets externes : les archives sont locales au VPS et leur clé doit être conservée séparément avant tout sinistre du serveur. Les anciennes sauvegardes de prédéploiement restent distinctes, privées et gérées par leur propre conservation.
