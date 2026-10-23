#!/usr/bin/env bash
# Updates an already initialized production checkout. Invoked by CD through stdin.
set -euo pipefail
umask 077
sha=${1:-}
deploy_path=${2:-}
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid deployment commit.' >&2; exit 1; }
[[ "$deploy_path" =~ ^/[a-zA-Z0-9_/-]+$ && "$deploy_path" != / && "$deploy_path" != *..* ]] || exit 1
cd -- "$deploy_path"
[[ -d .git && -f .env ]] || { echo 'Initialize the production checkout and .env first.' >&2; exit 1; }
exec 9>.git/crm-deploy.lock
flock -n 9 || { echo 'Another deployment is already running.' >&2; exit 1; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo 'Tracked server changes must be resolved before deployment.' >&2; exit 1; }
git fetch --no-tags origin main
[[ "$(git rev-parse origin/main)" == "$sha" ]] || { echo 'Commit superseded on main; deployment skipped.'; exit 0; }
previous=$(git rev-parse HEAD)
if [[ "$previous" == "$sha" && -f .git/crm-last-successful-deploy && "$(cat .git/crm-last-successful-deploy)" == "$sha" ]]; then
  echo 'Commit already verified; nothing to deploy.'
  exit 0
fi
domain=$(sed -n 's/^CALLVERIFY_DOMAIN=//p' .env | tr -d '\r')
[[ "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ && "$domain" == *.* ]] || { echo 'A configured HTTPS domain is required.' >&2; exit 1; }

compose=(docker compose -f compose.yaml -f infra/compose.crm.yaml -f compose.production.yaml)
"${compose[@]}" config -q
# This pipeline updates a running installation; first provisioning remains explicit.
for service in db portal-db assurance-db api; do
  [[ -n "$("${compose[@]}" ps --status running -q "$service")" ]] || { echo "First deploy or repair required: $service is not running." >&2; exit 1; }
done
backup=".backups/$(date -u +%Y%m%dT%H%M%SZ)-${sha:0:12}-$$"
mkdir -p -- "$backup"
printf '%s\n' "$previous" > "$backup/previous-commit"
printf '%s\n' "$sha" > "$backup/target-commit"
cp -- .env "$backup/config.env"
for service in db portal-db assurance-db; do
  "${compose[@]}" exec -T "$service" sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup/$service.dump"
  [[ -s "$backup/$service.dump" ]]
  "${compose[@]}" exec -T "$service" pg_restore --list < "$backup/$service.dump" > /dev/null
done
"${compose[@]}" exec -T api tar -czf - -C /app/private-media . > "$backup/media.tar.gz"
tar -tzf "$backup/media.tar.gz" > /dev/null
echo "Pre-deployment backups saved in $backup (private, local to server)."

git checkout --detach "$sha"
if ! bash scripts/deploy.sh; then
  echo "Deployment failed. Previous commit: $previous. Backup: $backup. No automatic database rollback." >&2
  exit 1
fi
# Both the frontend and each routed API must answer through public HTTPS.
curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors --max-time 15 "https://$domain/crm" -o /dev/null
for path in /api/portal/session/ /api/assurance/contacts/ /api/isolation/work-queue/; do
  healthy=false
  for attempt in {1..12}; do
    code=$(curl --silent --show-error --max-time 15 -o /dev/null -w '%{http_code}' "https://$domain$path") || code=000
    if [[ "$code" == 401 || "$code" == 403 ]]; then healthy=true; break; fi
    sleep 5
  done
  [[ "$healthy" == true ]] || { echo "Post-deployment route check failed: $path ($code). Backup: $backup" >&2; exit 1; }
done
printf '%s\n' "$sha" > .git/crm-last-successful-deploy
echo "Deployment verified: $sha"
