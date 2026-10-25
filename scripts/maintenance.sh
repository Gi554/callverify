#!/usr/bin/env bash
# Housekeeping, run after every verified deployment and safe to run by hand or weekly (cron):
# keeps only the latest pre-deployment backups and removes unused Docker images and build cache.
# Usage from the project folder:  ./scripts/maintenance.sh        (KEEP_BACKUPS=5 by default)
set -euo pipefail
cd "$(dirname "$0")/.."
keep=${KEEP_BACKUPS:-5}
[[ "$keep" =~ ^[1-9][0-9]*$ ]] || { echo "KEEP_BACKUPS invalide : $keep" >&2; exit 1; }

removed=0
if [ -d .backups ]; then
  # Folder names start with a UTC timestamp, so a plain sort is chronological.
  while IFS= read -r folder; do
    rm -rf -- "$folder"
    removed=$((removed + 1))
  done < <(find .backups -mindepth 1 -maxdepth 1 -type d | sort | head -n "-$keep")
fi
echo "Sauvegardes supprimées : $removed (les $keep plus récentes sont conservées)."

if command -v docker > /dev/null; then
  docker image prune -f --filter "until=168h" > /dev/null
  docker builder prune -f --filter "until=168h" > /dev/null
  echo "Images et cache de construction inutilisés depuis plus de 7 jours supprimés."
fi
