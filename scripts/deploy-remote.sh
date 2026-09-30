#!/usr/bin/env bash
# Runs ON THE SERVER (called by .github/workflows/deploy.yml).
# Installs Docker if needed, creates/updates .env, and starts Logirad with docker compose.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/logirad}"
cd "$APP_DIR"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | $SUDO sh
fi
if ! $SUDO docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin is missing; install docker-compose-plugin" >&2
  exit 1
fi

# Values sent by the workflow (never printed). The file is removed right after reading.
if [ -f .deploy.env ]; then
  set -a; . ./.deploy.env; set +a
  rm -f .deploy.env
fi

touch .env
chmod 600 .env
set_var() {  # set_var KEY VALUE  — add or replace a line in .env
  local key="$1" value="$2"
  # Single-quoted values are taken literally by docker compose (no $ interpolation)
  case "$value" in *"'"*) echo "$key must not contain a single quote (')" >&2; exit 1;; esac
  grep -v "^${key}=" .env > .env.tmp || true
  printf "%s='%s'\n" "$key" "$value" >> .env.tmp
  mv .env.tmp .env
  chmod 600 .env
}
has_var() { grep -q "^$1=." .env; }

# Secrets generated once on the server and never leave it
has_var POSTGRES_PASSWORD || set_var POSTGRES_PASSWORD "$(openssl rand -hex 16)"
has_var LOGIRAD_JWT_SECRET || set_var LOGIRAD_JWT_SECRET "$(openssl rand -hex 32)"

# Values managed from GitHub secrets: only overwritten when provided
for key in DOMAIN LOGIRAD_ADMIN_EMAIL LOGIRAD_ADMIN_PASSWORD LOGIRAD_AI_ENABLED ANTHROPIC_API_KEY \
           LOGIRAD_SMTP_HOST LOGIRAD_SMTP_PORT LOGIRAD_SMTP_USER LOGIRAD_SMTP_PASSWORD LOGIRAD_SMTP_FROM \
           LOGIRAD_WHATSAPP_TOKEN LOGIRAD_WHATSAPP_PHONE_NUMBER_ID LOGIRAD_WHATSAPP_VERIFY_TOKEN \
           LOGIRAD_WHATSAPP_APP_SECRET LOGIRAD_WHATSAPP_DISPLAY_NUMBER; do
  if [ -n "${!key:-}" ]; then set_var "$key" "${!key}"; fi
done

for required in DOMAIN LOGIRAD_ADMIN_PASSWORD; do
  has_var "$required" || { echo "Missing $required (add it as a GitHub secret)" >&2; exit 1; }
done

echo "==> Building and starting containers"
$SUDO docker compose up -d --build --remove-orphans

echo "==> Waiting for the backend"
for i in $(seq 1 60); do
  if $SUDO docker compose exec -T backend python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" >/dev/null 2>&1; then
    echo "Backend is healthy"
    $SUDO docker compose ps
    $SUDO docker image prune -f >/dev/null || true
    exit 0
  fi
  sleep 5
done
echo "Backend did not become healthy; recent logs:" >&2
$SUDO docker compose logs --tail=80 backend >&2
exit 1
