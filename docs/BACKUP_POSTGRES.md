# Sauvegarde PostgreSQL chiffrée et restauration de contrôle

## Portée

`scripts/crm_pg_backup.py` sauvegarde **une base PostgreSQL à la fois** sous forme d’archive custom `pg_dump`, chiffrée/authentifiée Fernet avec un manifeste (service, date UTC, empreinte et comptages par table). Répéter pour portail, Assurance et Isolation, en utilisant leurs connexions indépendantes. Les octets des documents Assurance sont inclus dans son dump. Les fichiers médias Isolation, le stockage S3, Redis, les rôles PostgreSQL, les tablespaces et les clés applicatives ne sont pas couverts par cette commande.

La commande de restauration crée une **nouvelle base** préfixée `crm_restore_` sur le serveur explicitement configuré ; elle refuse toute base existante et ne possède aucune commande de suppression ou remplacement. Elle révoque CONNECT/TEMPORARY à PUBLIC sur cette nouvelle base. Le compte opérateur reste propriétaire ; les superutilisateurs du serveur conservent leur accès. `pg_restore` fonctionne dans une transaction, sans rétablir propriétaires et droits d’origine, puis les comptages de tables sont comparés. Ne pas promouvoir cette base comme production : droits d’application, politiques, extensions, clés et parcours métier doivent encore être validés.

Un dump PostgreSQL peut exécuter du code SQL défini par sa source. Ne restaurer que des archives de confiance ; `--trusted-source` est une attestation opérateur, pas une analyse du SQL. Voir les documentations officielles [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) et [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).

## Prérequis et limites

- Outils officiels `pg_dump` et `pg_restore` dans PATH, compatibles avec la version du serveur. Recette CI : PostgreSQL 17 et clients 17. Ne pas utiliser un client plus ancien que le serveur.
- Python et dépendances du projet ; clé générée par `scripts/crm_backup.py keygen`, conservée en coffre séparé. Aucune valeur de mot de passe/clé affichée par l’outil.
- Connexion libpq privée via `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSFILE` ou `PGPASSWORD`, et paramètres TLS appropriés. Le programme **ne lit pas le .env** et ne déduit pas les connexions Django ; vérifier le serveur et les trois bases avant exécution. Privilégier un fichier de mots de passe protégé. Ne pas placer un secret dans la ligne de commande.
- Source : droits de lecture du schéma et des données. Cible de recette : compte autorisé à créer une base, connexion à la base administrative `postgres`. Choisir un serveur de recette isolé, sans accès aux fournisseurs.
- Arrêter les écritures et workers pour une cohérence entre comptages et dump, et entre les trois services/fichiers sauvegardés séparément. `--quiesced` atteste cet arrêt sans le contrôler. Une différence de comptages avant/après refuse l’archive, mais ne détecte pas toutes les écritures possibles à nombre constant.
- Limite de dump compressé : 256 Mio ; manifeste : 1 Mio ; processus dump/restauration : 120 secondes, connexion : 10 secondes et comptage : 60 secondes par requête. Contenu tenu en mémoire, marge mémoire importante nécessaire. Pas de fichier dump intermédiaire en clair. Ces bornes ne constituent pas une stratégie pour gros volumes.
- Ni copie externe, ni rotation, ni planification ou gestion de stockage objet dans ce lot. Garder clé et archive séparées, sur stockage privé chiffré ; les modes Unix de création ne configurent pas des ACL Windows.

## Commandes

Depuis la racine du projet, avec connexion source libpq déjà configurée dans un terminal privé et `.backups/` existant :

```powershell
# Génération une seule fois, chemin de coffre à adapter.
.venv/Scripts/python.exe scripts/crm_backup.py keygen --key-file .backups/cle-postgres.key

.venv/Scripts/python.exe scripts/crm_pg_backup.py create `
  --service assurance --source amx_assurance `
  --key-file .backups/cle-postgres.key `
  --output .backups/assurance-2026-10-20.pg.enc --quiesced

.venv/Scripts/python.exe scripts/crm_pg_backup.py verify `
  --archive .backups/assurance-2026-10-20.pg.enc `
  --key-file .backups/cle-postgres.key

# Reconfigurer les variables PG* vers le serveur ISOLÉ de recette avant cette commande.
.venv/Scripts/python.exe scripts/crm_pg_backup.py restore `
  --archive .backups/assurance-2026-10-20.pg.enc `
  --key-file .backups/cle-postgres.key `
  --target crm_restore_assurance_20261020 --trusted-source
```

Répéter `create` pour `--service portal --source amx_portal`, puis `--service isolation --source callverify`, avec les connexions source propres à chaque service et des sorties distinctes. Ces noms sont ceux par défaut du Compose ; utiliser les noms réellement configurés. L’exemple local de clé n’est pas une conservation indépendante suffisante : placer durablement la clé en coffre séparé des archives. Ne rien ajouter à Git.

`verify` valide le chiffrement, manifeste, taille, empreinte et signature custom PGDMP. **Il ne prouve pas à lui seul que le dump est restaurable.** Seul `restore`, suivi d’une recette métier, valide la reprise. Résumés sans contenu métier ni secret ; retour 0 en succès, 1 en erreur. En cas d’échec après création de la cible, elle est conservée pour diagnostic, sans suppression automatique ni autorisation de démarrer les services. Une interruption peut laisser une archive partielle : exécuter verify et utiliser une destination neuve en cas d’échec.

Après restauration : contrôler comptes, relations, données binaires, séquences, documents et droits avec la même version de code et les clés d’origine. Ne pas démarrer les workers/relais/calendriers/appels pendant la recette. Les sessions et travaux en attente sont copiés sans modification ; décider explicitement de leur traitement avant reprise. Sauvegarder et contrôler les médias Isolation séparément, à la même période de maintenance, avant d’envisager la reprise complète.

## Validation

Cinq tests simulés couvrent archive chiffrée/intégrité, source modifiée/maintenance, cible et confiance explicites, refus d’une base existante sans pg_restore et échecs dump/clé. Une recette réelle CI opt-in crée une base aléatoire, ses tables liées, données BYTEA et séquences ; exécute pg_dump/chiffrement/déchiffrement/pg_restore dans une deuxième base aléatoire ; contrôle octets, relations, compteurs, séquence, source intacte et refus de réutiliser la cible. Elle supprime uniquement ses deux bases jetables générées à cet effet. Ce nettoyage de test n’est pas une fonction du programme opérateur.

La restauration réelle de l’infrastructure client, ses trois bases, extensions et stockage privé reste une recette de déploiement distincte. Aucun test de charge, reprise PITR/WAL, rôle global, sauvegarde S3 ou copie hors site n’est déclaré livré ici.
