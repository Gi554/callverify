# Déploiement à finaliser avec vos informations

L'API, le frontend Nginx, les workers et Celery Beat sont définis dans `compose.yaml`. Beat redispatche l'outbox toutes les 30 secondes et purge les fichiers expirés chaque heure. Un seul Beat doit fonctionner.

1. Copier `.env.example` vers `.env` et définir les secrets côté serveur.
2. Générer une clé Fernet : `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Placer la valeur dans `MFA_ENCRYPTION_KEY` et conserver cette clé dans un coffre indépendant des sauvegardes de base. Ne pas la régénérer à chaque démarrage.
3. Configurer PostgreSQL, SMTP, Twilio, région S3 si utilisée, coût unitaire Lookup et devise. Les packages avancés sont facultatifs : `LOOKUP_PACKAGES=line_type_intelligence,line_status` après confirmation des droits et de la tarification.
4. Pour la recette locale : `docker compose build`, puis `docker compose up -d db redis`, `docker compose run --rm api python manage.py migrate`, `docker compose run --rm api python manage.py bootstrap_admin votre.identifiant`, `docker compose up -d`. Frontend : `http://127.0.0.1:8080`.
5. Pour la production : `DEBUG=false`, `CALLVERIFY_DOMAIN`, `ALLOWED_HOSTS`, `FRONTEND_URL=https://votre-domaine`, origines HTTPS exactes et SMTP configuré. Lancer avec `docker compose -f compose.yaml -f compose.production.yaml up -d --build`. Caddy termine HTTPS ; les ports directs du frontend et de l'API sont retirés par l'override.
6. Exécuter `encrypt_mfa`, `preflight` et `check --deploy`. Une migration de secrets d'un environnement DEBUG vers la production exige de conserver la clé utilisée pour les données existantes ou de réenrôler les comptes.
7. Sauvegarder PostgreSQL et le stockage privé, tester une restauration isolée, puis effectuer la recette fournisseur réelle.

Pour les sauvegardes PostgreSQL, utiliser `pg_dump -Fc` puis chiffrer l'archive dans votre outil de sauvegarde. Restaurer avec `pg_restore` dans une base isolée. Les clés Fernet et SECRET_KEY nécessaires à la restauration restent dans le coffre. Aucun secret réel n'est fourni dans le dépôt.

Les appels réels ne sont pas activables dans cette version : leur scénario, horaires, émetteur et conditions d'autorisation restent à fournir et à valider. Les écrans de préparation et le contrôle des exclusions sont disponibles.
