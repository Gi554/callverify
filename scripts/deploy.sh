#!/usr/bin/env bash
# Deploy or update CRM AMX on the server: build, migrate the three databases, check, start.
# Usage from the project folder:  ./scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Fichier .env absent. Lancez d'abord : python3 scripts/generate_production_env.py VOTRE-DOMAINE" >&2
  exit 1
fi
if grep -q '^DEBUG=true' .env; then
  echo "DEBUG=true dans .env : interdit en production." >&2
  exit 1
fi

compose=(docker compose -f compose.yaml -f infra/compose.crm.yaml -f compose.production.yaml)
# The NEWT journal worker only runs when call durations are enabled.
if grep -q '^NEWT_CDR_HISTORY_ENABLED=true' .env; then
  compose+=(--profile newt-journal)
fi

echo "1/5 Vérification de la configuration"
"${compose[@]}" config -q

echo "2/5 Construction des images"
"${compose[@]}" build

echo "3/5 Démarrage des bases de données"
"${compose[@]}" up -d --wait db portal-db assurance-db redis

echo "4/5 Migrations et contrôles de sécurité"
"${compose[@]}" run --rm api python manage.py migrate --noinput
"${compose[@]}" run --rm portal python manage.py migrate --noinput --settings=portal.backend.settings
"${compose[@]}" run --rm assurance python manage.py migrate --noinput --settings=apps.assurance.backend.settings
"${compose[@]}" run --rm api python manage.py check --deploy
"${compose[@]}" run --rm portal python manage.py check --deploy --settings=portal.backend.settings
"${compose[@]}" run --rm assurance python manage.py check --deploy --settings=apps.assurance.backend.settings

echo "5/5 Démarrage de l'application"
"${compose[@]}" up -d --remove-orphans
"${compose[@]}" ps
echo "Terminé. Ouvrez https://$(grep '^CALLVERIFY_DOMAIN=' .env | cut -d= -f2)/crm"
