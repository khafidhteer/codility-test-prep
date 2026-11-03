#!/usr/bin/env bash
# Verifies a running deployment over its real URL.
#
#   bash scripts/verify_deploy.sh https://lab.example.com 'the-password'
#   bash scripts/verify_deploy.sh http://127.0.0.1:8080 'the-password'
#
# Deliberately does NOT test the login rate limit: six failures would lock the
# caller's IP out of the live deployment for ten minutes. That case is covered by
# tests/smoke.sh against a throwaway local server.
set -euo pipefail

BASE="${1:?usage: verify_deploy.sh BASE_URL PASSWORD}"
PASS="${2:?usage: verify_deploy.sh BASE_URL PASSWORD}"
TMP=".verify-tmp"
rm -rf "$TMP" && mkdir -p "$TMP"

pass_n=0
fail() { printf '   FAIL %s\n' "$1" >&2; printf '        %s\n' "${2:-}" >&2; exit 1; }
ok()   { printf '   ok   %s\n' "$1"; pass_n=$((pass_n+1)); }
code() { curl -s -o "$TMP/body" -w '%{http_code}' --max-time 15 "$@"; }

# ---------------------------------------------------------------- health
HEALTH="$(curl -fsS --max-time 10 "$BASE/healthz" 2>/dev/null || true)"
[ "$HEALTH" = '{"ok":true}' ] || fail "/healthz did not return {\"ok\":true}" "got: ${HEALTH:-<no response>}"
ok "healthz responds"

# ---------------------------------------------------------------- gate is closed
c="$(code "$BASE/")"
[ "$c" = "303" ] || fail "unauthenticated / should redirect to login" "got $c"
ok "unauthenticated requests are redirected"

c="$(code "$BASE/nope")"
case "$c" in
  404) ok "unknown paths return 404, no directory listing" ;;
  303) ok "unknown paths redirect to login" ;;
  *)   fail "unknown path returned $c, expected 404 or a redirect" ;;
esac

# ---------------------------------------------------------------- wrong password
c="$(code -d 'password=definitely-wrong' "$BASE/login")"
[ "$c" = "401" ] || fail "wrong password should return 401" "got $c"
grep -qi "wrong password" "$TMP/body" || fail "login page does not explain the failure"
ok "wrong password rejected"

# ---------------------------------------------------------------- correct password
c="$(curl -s -c "$TMP/jar" -o "$TMP/login" -w '%{http_code}' --max-time 15 -d "password=$PASS" "$BASE/login")"
[ "$c" = "303" ] || fail "correct password should redirect" "got $c (check the password in .env)"
grep -q "lab_session" "$TMP/jar" || fail "no session cookie was set" "the cookie may be marked Secure while serving plain HTTP: set SECURE_COOKIE=0 for HTTP"
ok "password accepted, session cookie set"

c="$(code -b "$TMP/jar" "$BASE/")"
[ "$c" = "200" ] || fail "authenticated request failed" "got $c"
ok "app served to an authenticated session"

# ---------------------------------------------------------------- payload
SIZE="$(curl -s -b "$TMP/jar" -H 'Accept-Encoding: gzip' -o "$TMP/page.gz" -w '%{size_download}' --max-time 30 "$BASE/")"
[ "${SIZE:-0}" -gt 100000 ] || fail "app payload suspiciously small" "got ${SIZE:-0} bytes"
gzip -t "$TMP/page.gz" 2>/dev/null || fail "gzip payload did not decompress" "server compression may be broken"
gzip -dc "$TMP/page.gz" > "$TMP/page.html"
grep -q "Senior Data Scientist" "$TMP/page.html" || fail "served page is not the app" "expected the exam title in the body"
ok "payload ${SIZE} bytes gzipped, contains the app"

# ---------------------------------------------------------------- tamper and logout
c="$(code -H 'Cookie: lab_session=1.deadbeef' "$BASE/")"
[ "$c" = "303" ] || fail "a forged cookie was accepted" "got $c; the signing secret may be empty"
ok "forged cookies rejected"

c="$(curl -s -b "$TMP/jar" -c "$TMP/jar" -o "$TMP/lo" -w '%{http_code}' --max-time 15 -X POST "$BASE/logout")"
[ "$c" = "303" ] || fail "logout should redirect" "got $c"
c="$(code -b "$TMP/jar" "$BASE/")"
[ "$c" = "303" ] || fail "session survived logout" "got $c"
ok "logout clears the session"

# ---------------------------------------------------------------- tls
case "$BASE" in
  https://*)
    if echo | openssl s_client -connect "${BASE#https://}:443" -servername "${BASE#https://}" 2>/dev/null | grep -q "Verify return code: 0"; then
      ok "tls certificate verifies"
    else
      printf '   warn: could not confirm the TLS chain with openssl (the page still loaded)\n'
    fi
    ;;
esac

rm -rf "$TMP"
printf '\n   VERIFIED: %d checks passed against %s\n' "$pass_n" "$BASE"
