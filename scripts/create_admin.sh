#!/usr/bin/env bash
# Create the first CRM administrator, with access to Assurance and Isolation.
# Usage:  ./scripts/create_admin.sh IDENTIFIANT   (the password is typed privately)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ $# -ne 1 ]; then
  echo "Usage : ./scripts/create_admin.sh IDENTIFIANT" >&2
  exit 1
fi
compose=(docker compose -f compose.yaml -f infra/compose.crm.yaml -f compose.production.yaml)
"${compose[@]}" run --rm portal python manage.py createsuperuser --username "$1" \
  --settings=portal.backend.settings
for space in assurance isolation; do
  "${compose[@]}" run --rm portal python manage.py grant_workspace "$1" "$space" administrator \
    --settings=portal.backend.settings
done
echo "Administrateur $1 créé : il invite ensuite les autres utilisateurs depuis le CRM."
