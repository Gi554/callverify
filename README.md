# CallVerify

Plateforme locale de qualification téléphonique canadienne : API Django REST Framework, interface Vue 3/TypeScript, PostgreSQL, Celery et Redis. Le thème crème/olive est commun à la connexion et aux écrans métier.

## Lancer sur ce poste

Les dépendances Python et Node sont déjà installées.

```powershell
# Terminal 1 : API et tâches immédiates pour le développement
./scripts/dev.ps1
# Terminal 2 : interface Vue
./scripts/frontend.ps1
```

Interface : http://127.0.0.1:5173. Aperçu sans compte : `/demo`, avec données fictives et aucune écriture serveur. Les variables `.env` sont chargées par Compose ; en dehors de Docker, les définir dans le terminal.

Pour le premier compte réel, dans un terminal privé :

```powershell
$env:DEBUG='true'
.venv/Scripts/python.exe manage.py bootstrap_admin votre.identifiant --email vous@example.com
```

La commande demande le mot de passe sans l'afficher et fournit le secret TOTP et des codes de secours à conserver en coffre. Aucun compte de production partagé n'est fourni. Le script `scripts/recette_seed.py` est réservé à une base jetable, exige un opt-in explicite et ne doit jamais être utilisé en production.

## Parcours disponibles

- Connexion, récupération de mot de passe, MFA avec QR code, secrets chiffrés et codes de secours à usage unique.
- Campagnes : création, édition, archivage, budgets estimés et progression Lookup.
- Imports CSV/XLSX : aperçu, choix de feuille, mappage téléphone/nom/référence, dédoublonnage E.164, conservation des lignes et rapport d'anomalies CSV.
- Résultats : recherche, filtres, pagination, fiche, historique Lookup, preuves et sources.
- Exports CSV/XLSX : colonnes choisies, filtre de validité, téléchargement privé, protection des formules, expiration et purge automatique.
- Administrateurs : invitation privée, suspension/réactivation, rôles avec MFA obligatoire avant promotion superadmin.
- Paramètres, exclusions, preuves d'autorisation, décisions justifiées, journal d'audit et alertes de traitement.
- Préparation des campagnes d'appels et contrôle d'admissibilité ; émission réelle désactivée.

Les permissions sont vérifiées côté serveur. Un administrateur accède à ses campagnes ; le superadministrateur voit toutes les campagnes. Aucune route employé.

## Traitements et intégrations

Une outbox en base conserve les demandes avant leur envoi. Beat les redispatche toutes les 30 secondes ; après 25 échecs de publication, un examen est requis. Le débit Lookup est limité globalement via Redis. Les opérations idempotentes protègent les doublons de livraison. Une réponse fournisseur ambiguë n'est pas relancée automatiquement.

Twilio Basic et les packages optionnels `line_type_intelligence` / `line_status` sont implémentés mais restent désactivés sans configuration. Les erreurs de package sont conservées. Un résultat Active ne devient pas Reachable. Le cache conserve la date réelle du contrôle et sa provenance.

`spent` et `LookupCheck.cost` sont des réserves estimées. Un endpoint superadmin permet de consigner un coût facturé avec une référence de facture ; le rapprochement automatique des factures reste à définir avec les données fournisseur.

Beat purge les exports expirés chaque heure et les fichiers d'import selon la durée configurée, en conservant les rapports. Développement : mode eager sans Redis ; production : workers et Beat séparés. Un seul Beat doit être actif.

## Docker et HTTPS

Copier `.env.example` vers `.env`, compléter les informations puis suivre [deploy/README.md](deploy/README.md). Compose comprend API, Vue/Nginx, PostgreSQL, Redis, worker et Beat. L'override de production ajoute Caddy pour HTTPS et retire les ports directs de l'API et du frontend.

En production, `SECRET_KEY` et `MFA_ENCRYPTION_KEY` sont obligatoires. Conserver la clé MFA en coffre, indépendamment des sauvegardes. Le repli de développement dépend de SECRET_KEY ; conserver la clé d'origine ou réenrôler les comptes lors d'un changement d'environnement.

## Vérifier

```powershell
$env:DEBUG='true'
.venv/Scripts/python.exe manage.py test
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

Les tests automatisés ont été exécutés sur SQLite et PostgreSQL. Redis a été testé en réel pour la limitation globale. Une sauvegarde PostgreSQL de données fictives a été restaurée dans une deuxième base jetable. Ces vérifications ne remplacent pas la recette sur votre hébergement et votre compte Twilio.

## À fournir et valider ensuite

Identifiants Twilio/SMTP, accès aux packages canadiens, tarification et devise, domaine/hébergement, stockage/région et politique de conservation. Le module d'émission Voice attend votre scénario autorisé, les horaires, l'émetteur et ses règles d'autorisation avant son implémentation et sa recette. Les tests de charge au volume cible, S3 et les appels fournisseur réels restent à effectuer.

[Guide administrateur](docs/GUIDE_ADMIN.md) · [API](docs/API.md) · [Exploitation](docs/OPERATIONS.md) · [État et travaux restants](docs/ROADMAP.md)
