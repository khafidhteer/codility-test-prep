#!/usr/bin/env bash
# Deploy the Codility lab on a fresh VPS.
#
#   bash scripts/deploy.sh              # localhost only, reachable via SSH tunnel
#   bash scripts/deploy.sh --public     # bind 0.0.0.0:8080, plain HTTP, not recommended
#   DOMAIN=lab.example.com bash scripts/deploy.sh   # HTTPS through Caddy
#
# Idempotent: safe to re-run after a failure. It generates a password on first
# run, builds, starts, waits for health, then verifies the real auth flow.
# Any failed step prints the container logs and exits non-zero.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PUBLIC=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --public) PUBLIC=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '   ok: %s\n' "$*"; }
die()  { printf '\n   FAILED: %s\n' "$*" >&2; exit 1; }

on_error() {
  printf '\n   ---- last 40 log lines ----\n' >&2
  docker compose logs --tail=40 2>&1 || true
  printf '\n   Fix the error above, then re-run: bash scripts/deploy.sh\n' >&2
}
trap on_error ERR

# ---------------------------------------------------------------- 1. preflight
say "preflight"
command -v docker >/dev/null || die "docker is not installed. Run: curl -fsSL https://get.docker.com | sh"
docker info >/dev/null 2>&1 || die "the docker daemon is not running or not reachable. Try: sudo systemctl enable --now docker"
docker compose version >/dev/null 2>&1 || die "docker compose v2 is missing. Run: sudo apt-get install -y docker-compose-plugin"
ok "docker and compose available"

# Linux-only host checks, skipped elsewhere so the script can be rehearsed on a laptop
if [ "$(uname -s)" = "Linux" ]; then
  for p in 80 443; do
    if [ -n "${DOMAIN:-}" ] && command -v ss >/dev/null && ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${p}\$"; then
      die "port ${p} is already in use. Run: sudo ss -ltnp | grep :${p}  and stop that service first."
    fi
  done
  FREE_KB=$(df -Pk . | awk 'NR==2 {print $4}')
  [ "${FREE_KB:-0}" -gt 1048576 ] || printf '   warn: less than 1 GB free disk, the image build needs about 400 MB\n'
  ok "host checks passed"
fi

# ---------------------------------------------------------------- 2. secrets
say "configuration"
if [ ! -f .env ]; then
  cp .env.example .env
  ok "created .env from .env.example"
fi

current_password() { awk -F= '/^APP_PASSWORD=/{print substr($0, index($0,"=")+1)}' .env | tr -d '\r'; }
current_domain()   { awk -F= '/^DOMAIN=/{print substr($0, index($0,"=")+1)}' .env | tr -d '\r'; }

PW="$(current_password)"
case "$PW" in
  ""|change-me-to-something-long)
    if command -v openssl >/dev/null; then
      PW="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | cut -c1-24)"
    else
      PW="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | cut -c1-24)"
    fi
    if grep -q '^APP_PASSWORD=' .env; then
      awk -v pw="$PW" 'BEGIN{FS=OFS="="} /^APP_PASSWORD=/{print "APP_PASSWORD="pw; next} {print}' .env > .env.tmp && mv .env.tmp .env
    else
      printf 'APP_PASSWORD=%s\n' "$PW" >> .env
    fi
    ok "generated a password and wrote it to .env"
    ;;
  *) ok "using the password already in .env" ;;
esac

DOMAIN_RESOLVED="${DOMAIN:-$(current_domain)}"
if [ -n "$DOMAIN_RESOLVED" ] && [ "$DOMAIN_RESOLVED" != "lab.example.com" ]; then
  printf 'DOMAIN=%s\n' "$DOMAIN_RESOLVED" | grep -q . && \
    awk -v d="$DOMAIN_RESOLVED" 'BEGIN{FS=OFS="="} /^DOMAIN=/{print "DOMAIN="d; next} {print}' .env > .env.tmp && mv .env.tmp .env
  # HTTPS terminates at Caddy, so the cookie must be Secure
  awk 'BEGIN{FS=OFS="="} /^SECURE_COOKIE=/{print "SECURE_COOKIE=1"; next} {print}' .env > .env.tmp && mv .env.tmp .env
  MODE="tls"
  ok "domain ${DOMAIN_RESOLVED}, TLS mode"
else
  # Plain HTTP on localhost: a Secure cookie would be written and never sent back
  awk 'BEGIN{FS=OFS="="} /^SECURE_COOKIE=/{print "SECURE_COOKIE=0"; next} {print}' .env > .env.tmp && mv .env.tmp .env
  MODE="local"
  ok "no domain set, localhost mode on 127.0.0.1:8080"
fi

docker compose config >/dev/null || die "docker compose config rejected the files. Check .env for stray quotes or spaces."
ok "compose file validates"

# ---------------------------------------------------------------- 3. DNS check
if [ "$MODE" = "tls" ] && [ "$FORCE" -eq 0 ] && [ "$(uname -s)" = "Linux" ]; then
  say "dns check for ${DOMAIN_RESOLVED}"
  SERVER_IP="$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null || true)"
  if command -v getent >/dev/null; then
    DOMAIN_IP="$(getent hosts "$DOMAIN_RESOLVED" | awk '{print $1}' | head -1)"
  else
    DOMAIN_IP="$(curl -fsS --max-time 8 "https://dns.google/resolve?name=${DOMAIN_RESOLVED}&type=A" 2>/dev/null | grep -o '"data":"[0-9.]*"' | head -1 | cut -d'"' -f4)"
  fi
  if [ -z "$DOMAIN_IP" ]; then
    die "${DOMAIN_RESOLVED} does not resolve. Create an A record pointing at ${SERVER_IP:-this server}, wait for propagation, or re-run with --force to skip certificate issuance checks."
  fi
  if [ -n "$SERVER_IP" ] && [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    die "${DOMAIN_RESOLVED} resolves to ${DOMAIN_IP} but this server is ${SERVER_IP}. Fix the A record, or re-run with --force if you use a proxy such as Cloudflare."
  fi
  ok "dns points at this server (${DOMAIN_IP})"
fi

# ---------------------------------------------------------------- 4. build and start
say "build (runs the content gate inside the image)"
docker compose build

say "start"
if [ "$MODE" = "tls" ]; then
  docker compose --profile tls up -d
else
  if [ "$PUBLIC" -eq 1 ]; then
    printf '   warn: --public exposes plain HTTP on 0.0.0.0:8080. The password crosses the network in clear text.\n'
    docker compose up -d
  else
    docker compose up -d lab
  fi
fi

# ---------------------------------------------------------------- 5. wait for health
say "waiting for health"
HEALTHY=0
for i in $(seq 1 60); do
  if curl -fsS --max-time 2 http://127.0.0.1:8080/healthz 2>/dev/null | grep -q '"ok":true'; then
    HEALTHY=1
    ok "healthy after ${i}s"
    break
  fi
  sleep 2
done
[ "$HEALTHY" -eq 1 ] || die "the app did not become healthy within 120s. Check: docker compose logs --tail=50 lab"

# ---------------------------------------------------------------- 6. verify the real gate
say "verifying the auth flow"
if [ "$MODE" = "tls" ]; then
  BASE="https://${DOMAIN_RESOLVED}"
else
  BASE="http://127.0.0.1:8080"
fi
bash scripts/verify_deploy.sh "$BASE" "$PW"

# ---------------------------------------------------------------- 7. summary
say "done"
printf '   mode      : %s\n' "$MODE"
printf '   url       : %s\n' "$BASE"
printf '   password  : %s\n' "$PW"
printf '   stored in : %s/.env\n\n' "$ROOT"
if [ "$MODE" = "local" ] && [ "$PUBLIC" -eq 0 ]; then
  cat <<'EOF'
   Reach it from your laptop with an SSH tunnel:

       ssh -L 8080:127.0.0.1:8080 <user>@<this-server-ip>

   then open http://localhost:8080 and paste the password above.

   For phone access, either add a DOMAIN to .env and re-run this script, or
   use a Cloudflare tunnel:  cloudflared tunnel --url http://127.0.0.1:8080
EOF
fi
printf '   logs      : docker compose logs -f lab\n'
printf '   restart   : docker compose restart lab\n'
printf '   update    : git pull && bash scripts/deploy.sh\n'
