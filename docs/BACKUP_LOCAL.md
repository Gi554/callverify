# Sauvegarde locale chiffrée et restauration isolée

## Périmètre livré

`scripts/crm_backup.py` sauvegarde **trois bases SQLite locales distinctes** (portail, Assurance, Isolation) et un dossier de fichiers privés. Les documents binaires Assurance et leurs liens sont dans la base Assurance ; les imports/exports locaux Isolation sont dans le dossier média. Toutes les tables sont conservées, y compris comptes, historiques, fichiers binaires et tâches en attente. L’outil ne lance aucun service, migration, appel, e-mail ou travail fournisseur.

Ce lot ne sauvegarde **pas PostgreSQL, Redis ou S3** et ne constitue pas une sauvegarde externe de production. Il n’installe aucune planification, rétention ou copie distante. PostgreSQL, stockage objet et restauration sur l’hébergement retenu restent à livrer/recetter séparément.

Le programme fonctionne avec Python 3.12+ et les dépendances existantes du projet. Copie SQLite via l’[API de sauvegarde](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup), y compris les transactions validées en WAL ; normalisation des en-têtes du snapshot conformément à la [documentation SQLite de désérialisation](https://www.sqlite.org/c3ref/deserialize.html). Il n’effectue pas une simple copie des fichiers ouverts. L’archive ZIP et son manifeste sont chiffrés/authentifiés avec [Fernet](https://cryptography.io/en/latest/fernet/) ; aucun fichier ZIP ou snapshot intermédiaire en clair n’est écrit sur disque. La restauration écrit nécessairement les bases et fichiers en clair dans le dossier privé cible.

## Avant de sauvegarder

1. Arrêter les serveurs Django, workers, ordonnanceurs et relais qui peuvent modifier ces bases ou leurs fichiers. Les garder arrêtés jusqu’à la fin de `create`. `--quiesced` atteste cet arrêt ; le programme ne peut pas le vérifier. Les trois instantanés et fichiers sont séquentiels, pas une transaction commune.
2. Vérifier les chemins réels : `portal.sqlite3`, `assurance.sqlite3` et `db.sqlite3`, à la racine selon les réglages locaux actuels ; utiliser les chemins effectifs si une instance de recette les redéfinit.
3. Choisir un emplacement privé pour la clé, **hors du dossier média**. Déposer la clé durable dans un coffre séparé des archives. Sa perte empêche la restauration ; quiconque possède clé et archive peut lire les données.
4. Choisir un fichier de sortie neuf, hors du dossier média et des bases. `.backups/` est ignoré par Git mais cela ne remplace pas le contrôle d’accès du disque. Sous Windows, les modes Unix ne configurent pas une ACL : utiliser un dossier protégé par le compte utilisateur et un disque chiffré.
5. Limites locales : 256 Mio de bases/fichiers décompressés, 10 000 fichiers (trois snapshots compris), manifeste de 1 Mio et archive ZIP de 256 Mio. Fernet et les contrôles travaillent en mémoire : prévoir une marge mémoire importante, de l’ordre de plusieurs fois le volume accepté. Le programme refuse les dépassements ; ne pas augmenter ces bornes pour remplacer une stratégie de sauvegarde de production.

Les noms de fichiers/dossiers doivent être portables Windows/Linux. Liens symboliques, jonctions et noms ambigus ou réservés sont refusés. Le dossier média doit exister, même vide. Son contenu est sauvegardé intégralement : ne pas y mélanger des dossiers de recette, journaux sans utilité ou archives volumineuses. Les autres dossiers et le `.env` à la racine ne sont pas ajoutés automatiquement.

## Commandes PowerShell

Depuis la racine, créer manuellement le dossier de destination privé si nécessaire. Exemple local ; adapter tous les chemins avant usage. Aucune clé n’est affichée :

```powershell
New-Item -ItemType Directory -Path .backups -Force
# Une seule fois : choisir un chemin privé de clé, idéalement dans un coffre.
.venv/Scripts/python.exe scripts/crm_backup.py keygen --key-file .backups/cle-locale.key

# Services et workers arrêtés ; archive située hors de private-media.
.venv/Scripts/python.exe scripts/crm_backup.py create `
  --portal portal.sqlite3 `
  --assurance assurance.sqlite3 `
  --isolation db.sqlite3 `
  --media private-media `
  --key-file .backups/cle-locale.key `
  --output .backups/crm-2026-10-20.enc `
  --quiesced

.venv/Scripts/python.exe scripts/crm_backup.py verify `
  --archive .backups/crm-2026-10-20.enc `
  --key-file .backups/cle-locale.key

.venv/Scripts/python.exe scripts/crm_backup.py restore `
  --archive .backups/crm-2026-10-20.enc `
  --key-file .backups/cle-locale.key `
  --target .backups/restauration-2026-10-20
```

L’exemple place temporairement clé et archive dans le même dossier local pour la commande ; ce n’est **pas** une séparation de conservation suffisante. Conserver ensuite la clé en coffre indépendant et la sauvegarde sur un autre support privé. Ne jamais ajouter clé, archive ou données restaurées à Git. Aucun secret applicatif existant n’est généré, remplacé ou affiché par ces commandes.

## Vérifications et reprise

`verify` déchiffre, vérifie les empreintes SHA-256 et tailles, l’inventaire, les trois bases, l’intégrité SQLite, les clés étrangères et les nombres de lignes par table. Un code de retour 0 indique la réussite ; toute erreur renvoie 1. Les résumés JSON indiquent uniquement version, date UTC, nombres de bases/fichiers et taille ; pas de contenu métier ou valeur de clé.

`restore` fait ces vérifications **avant de créer** un dossier neuf contenant :

```text
databases/portal.sqlite3
databases/assurance.sqlite3
databases/isolation.sqlite3
media/...
manifest.json
```

Il refuse tout dossier cible déjà présent, même vide, toute archive altérée ou clé incorrecte, une base manquante, une empreinte/comptage incorrect ou un chemin dangereux. Il ne décompresse pas avec `extractall` et ne remplace jamais les bases actuelles. Si l’écriture échoue, seul le nouveau dossier de restauration créé par cette opération est nettoyé. L’archive d’origine reste conservée. Une interruption brutale peut laisser une archive incomplète ou un dossier de restauration partiel ; les conserver pour diagnostic, utiliser une nouvelle destination pour la tentative suivante et exécuter `verify` avant toute utilisation.

Avant toute remise en service : contrôler les comptes, documents et accès dans une instance isolée, avec la même version de code et les clés applicatives d’origine conservées dans le coffre (`SECRET_KEY`, clés d’accès CRM, chiffrement MFA, calendrier et courrier selon configuration). Aucun secret n’est reconstitué par les snapshots. Les sessions restaurées et tâches en attente peuvent exister ; ne pas démarrer les ordonnanceurs, relais SMTP, synchronisations ou fournisseurs pendant la recette. Décider explicitement de leur traitement avant promotion. Le programme ne révoque pas de sessions et ne réécrit pas les tâches.

Le transfert final vers les emplacements actifs est une opération d’exploitation distincte, non automatisée par cet outil. La vérification de structure et de compteurs ne prouve pas à elle seule que tous les parcours métier ou toutes les clés de chiffrement fonctionnent.

## Recette exécutée

```powershell
.venv/Scripts/python.exe -m unittest core.test_crm_backup -v
```

Dix tests utilisent des bases et fichiers temporaires : aller-retour chiffré des trois bases/documents binaires/médias, WAL non checkpointé, refus d’écrasement et sources préservées, mauvaise clé et altération, empreintes/comptages/chemins malveillants, limites/maintenance/clé hors média, liens, erreur disque avec nettoyage et commandes CLI complètes. Création de lien non disponible sur le Windows de recette : ce test est ignoré localement et exécuté sous Linux en CI.

Une recette CLI a également créé et migré **trois bases Django jetables**, ajouté une adhésion portail, un contrat/document lié Assurance et un import Isolation avec fichier privé. `keygen`, `create`, `verify` et `restore` ont réussi. Après restauration, adhésion, lien contractuel, octets du document et fichier d’import ont été contrôlés. Aucune base existante du projet ni fournisseur n’a été sollicité.
