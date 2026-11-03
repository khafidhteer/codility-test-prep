#!/usr/bin/env bash
# End to end check of the gated server. Starts it on a spare port, exercises the
# auth flow, then kills it. Fails loudly on the first wrong status code.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${PORT:-8098}"
PASS="smoketest-$(date +%s)"
BASE="http://127.0.0.1:${PORT}"
TMP=".smoke-tmp"
rm -rf "$TMP" && mkdir -p "$TMP"
trap 'kill "${PID:-0}" 2>/dev/null || true; rm -rf "$TMP"' EXIT

[ -f app/index.html ] || { echo "app/index.html missing, run: python3 build/build_app.py"; exit 1; }

APP_PASSWORD="$PASS" PORT="$PORT" SESSION_HOURS=1 python3 app/server.py >"$TMP/server.log" 2>&1 &
PID=$!

for i in $(seq 1 40); do
  if curl -fsS --max-time 2 "$BASE/healthz" >/dev/null 2>&1; then break; fi
  sleep 0.25
done

fail() { echo "FAIL: $1"; echo "--- server log"; cat "$TMP/server.log"; exit 1; }
expect() { [ "$1" = "$2" ] || fail "$3 (got $1, want $2)"; }

# write bodies to a real file: native Windows curl cannot write to /dev/null and
# returns exit 23 on any response that has a body
code() { curl -s -o "$TMP/last.body" -w '%{http_code}' --max-time 10 "$@"; }

expect "$(curl -s --max-time 5 "$BASE/healthz")" '{"ok":true}' "healthz"
expect "$(code "$BASE/")" "303" "unauthenticated root should redirect"
expect "$(code "$BASE/index.html")" "303" "unauthenticated asset should redirect"
expect "$(code "$BASE/nope")" "404" "unknown path"
expect "$(code -d 'password=wrong' "$BASE/login")" "401" "wrong password"
expect "$(curl -s -o "$TMP/w.html" -w '%{http_code}' --max-time 10 -d 'password=wrong' "$BASE/login")" "401" "wrong password body"
grep -q "Wrong password" "$TMP/w.html" || fail "login page should explain the failure"

expect "$(curl -s -c "$TMP/cj" -o /dev/null -w '%{http_code}' --max-time 10 -d "password=$PASS" "$BASE/login")" "303" "correct password"
expect "$(curl -s -b "$TMP/cj" -o /dev/null -w '%{http_code}' --max-time 10 "$BASE/")" "200" "authenticated root"

SIZE=$(curl -s -b "$TMP/cj" -H 'Accept-Encoding: gzip' -o "$TMP/page.gz" -w '%{size_download}' --max-time 20 "$BASE/")
gunzip -c "$TMP/page.gz" > "$TMP/page.html" 2>/dev/null || fail "gzip payload did not decompress"
grep -q "Codility" "$TMP/page.html" || fail "page looks empty"
echo "payload: ${SIZE} bytes gzipped, $(wc -c < "$TMP/page.html") bytes raw"

expect "$(code -H 'Cookie: lab_session=1.bad' "$BASE/")" "303" "tampered cookie must be rejected"
# -c updates the jar from Set-Cookie, which is what removes the dead cookie
expect "$(code -b "$TMP/cj" -c "$TMP/cj" -X POST "$BASE/logout")" "303" "logout"
expect "$(code -b "$TMP/cj" "$BASE/")" "303" "cookie must be dead after logout"

for i in 1 2 3 4 5 6; do code -d 'password=wrong' "$BASE/login" >/dev/null; done
expect "$(code -d 'password=wrong' "$BASE/login")" "429" "rate limit after 6 failures"

echo "PASS: auth, assets, gzip, tamper rejection, logout, rate limit"
