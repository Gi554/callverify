# Préparation de la base commune

## État livré

Le CRM utilise encore trois bases distinctes. Ce lot livre uniquement un audit
SQLite en lecture seule et ce plan de migration. Il ne crée aucune cible, ne copie
aucune donnée vers PostgreSQL et ne change aucune connexion applicative.

Les fichiers locaux sont à la racine : `portal.sqlite3`, `assurance.sqlite3` et
`db.sqlite3` (Isolation). Les déploiements PostgreSQL actuels gardent leurs bases
séparées ; leur audit et leur migration devront avoir une procédure dédiée.

## Exécuter l'audit local

Depuis la racine, choisir un nouveau fichier de rapport dans le dossier ignoré :

```powershell
.venv/Scripts/python.exe scripts/crm_db_audit.py --portal portal.sqlite3 --assurance assurance.sqlite3 --isolation db.sqlite3 --output private-media/db-audit-nouveau.json
```

Le script utilise des instantanés SQLite incluant les écritures WAL validées,
vérifie l'intégrité et les clés étrangères, inventorie tables/colonnes/index par
empreinte et compte les références connues vers les identités du portail. Il
contrôle aussi la destination des tentatives d'appel et des synchronisations
calendrier selon leur espace. Toute colonne suffixée `_id` non couverte par une
clé étrangère, le registre explicite ou l'exception UUID `request_id` est signalée.
Les exclusions polymorphes sont décrites dans le rapport ; elles ne sont pas
présentées comme vérifiées. Les migrations minimales attendues sont contrôlées.

Le rapport contient des noms de structure et des comptes agrégés, sans lignes
métier, identités, notes, numéros, mots de passe ni clés. Il reste hors Git. Les
sources doivent être distinctes, existantes et sans lien symbolique/jonction.
Une destination existante ou identique à une source est refusée sans écrasement.
La limite de chaque instantané est de 256 Mio ; les trois copies sont en mémoire.

Codes de sortie :

- `0` : aucun problème détecté dans le périmètre contrôlé ; rapport écrit.
- `2` : blocages détectés ; rapport écrit avec leurs comptes et leur structure.
- `1` : audit impossible (source, intégrité, schéma ou destination) ; erreur
  générique sans données brutes et aucun nouveau rapport.

`--quiesced` déclare un arrêt coordonné déjà réalisé par l'opérateur. Il n'arrête
aucun service et ne prouve pas l'arrêt. Sans arrêt coordonné, les trois instantanés
sont cohérents séparément, sans photographie transactionnelle commune. Même avec
cette option, `migration_ready` reste toujours `false`.

## Constat local du 22 octobre 2026

L'audit exécuté sans arrêter les services compte 22 tables portail, 29 Assurance
et 33 Isolation. Il ne détecte aucun blocage parmi 36 contrôles d'identités et deux
contrôles de sources métier. Neuf noms de tables sont présents dans plusieurs
bases. Ces chiffres décrivent un instant local, pas une certification des données.

Les identifiants numériques ne suffisent pas à rapprocher les personnes :
Isolation conserve notamment son ancien modèle administratif, tandis que le
portail porte les identités et leurs appartenances aux espaces. Ne jamais fusionner
deux comptes sur leur nom, leur courriel ou leur identifiant numérique seul.

## Cible à éprouver

La cible proposée est une base PostgreSQL physique commune avec trois schémas
`portal`, `assurance`, `isolation`. Les trois services gardent leurs tables
techniques et leur historique de migrations dans leur propre schéma. Le portail
reste l'autorité des identités CRM ; les références historiques Isolation sont
préservées. Les tables de même nom ne doivent pas être fusionnées.

Cette organisation doit d'abord être démontrée sur une cible jetable, avec des
rôles distincts et un chemin de résolution de schéma explicite par service. Les
droits doivent empêcher toute lecture/écriture implicite entre espaces et toute
création indésirable dans un schéma partagé. Le réglage des connexions, les
migrations Django et les permissions ne sont pas encore implémentés ni validés.
Une base physique commune ne remplace pas les contrôles d'accès métier existants.

## Étapes restantes avant une bascule

1. Préparer une cible isolée reproductible et tester les rôles, schémas et
   connexions des trois services, sans modifier le déploiement courant.
2. Implémenter puis répéter le transfert SQLite vers cette cible sur des copies.
   Conserver les identifiants, relations, valeurs nulles, JSON, dates, empreintes
   de mots de passe et données chiffrées ; ajuster les séquences PostgreSQL après
   import. Ne jamais simuler une migration Django appliquée pour masquer une
   différence de schéma. Contrôler également les références polymorphes, valeurs
   JSON et événements actuellement exclus de cet audit.
3. Comparer les comptes, relations et données entre copies sources et cible,
   puis vérifier les parcours et permissions de chaque rôle dans chaque espace.
   Ne déclencher aucun appel, message ni écriture calendrier externe de recette.
4. Vérifier médias, pièces jointes et clés de chiffrement hors Git ; produire une
   sauvegarde chiffrée et répéter une restauration complète de la base commune,
   ainsi que le retour au déploiement précédent. Les outils actuels de sauvegarde
   multi-bases ne constituent pas une recette de restauration mono-base/schémas.
5. Seulement après ces preuves, planifier l'arrêt coordonné des écritures, refaire
   l'audit et les sauvegardes, transférer puis contrôler avant réouverture. Si un
   contrôle échoue, conserver l'ancien déploiement et les sources intactes.

Voir aussi [sauvegardes locales](BACKUP_LOCAL.md) et
[sauvegardes PostgreSQL actuelles](BACKUP_POSTGRES.md). L'audit ne remplace aucune
de ces sauvegardes et ne constitue jamais un feu vert automatique de migration.

## Validation de ce lot

Huit tests dédiés couvrent les références manquantes sans exposition d'identifiants,
les sources selon l'espace, les nouvelles références non classées, les migrations
absentes, les écritures WAL, les refus d'écrasement, les sources identiques ou
absentes et les corruptions de clés étrangères. La suite core complète passe :
231 tests, dont 17 ignorés selon SQLite/Windows. Aucun service arrêté, aucune
connexion ni donnée métier modifiée, aucun fournisseur externe sollicité.
