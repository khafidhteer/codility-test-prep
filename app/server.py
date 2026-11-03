# -*- coding: utf-8 -*-
"""Password-gated static server for the Codility lab.

Standard library only, so the container needs nothing beyond python:slim and the
image stays small enough for a 2 vCPU / 2 GB VPS.

Endpoints
    GET  /            the app (cookie required, otherwise redirect to /login)
    GET  /login       login form
    POST /login       password check, sets an HMAC-signed cookie
    POST /logout      clears the cookie
    GET  /healthz     liveness probe, no auth
    GET  /favicon.ico 204

Environment
    APP_PASSWORD     required, the shared password
    APP_SECRET       optional, defaults to a value derived from APP_PASSWORD
    PORT             default 8080
    BIND             default 0.0.0.0
    SECURE_COOKIE    set to 1 when served over HTTPS
    SESSION_HOURS    default 168 (7 days)
    ALLOWED_IPS      optional comma separated allowlist, checked before auth

Design notes
    - Only two files are ever served, both by explicit path. No directory
      traversal surface.
    - Login attempts are rate limited per IP in memory. Restarting the process
      clears the counters, which is fine for a single-user tool.
    - The cookie is signed, not encrypted, and carries only a timestamp.
"""
import gzip
import hashlib
import hmac
import html
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
INDEX_GZ = INDEX + ".gz"

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
APP_SECRET = os.environ.get("APP_SECRET", "") or ("lab:" + APP_PASSWORD)
PORT = int(os.environ.get("PORT", "8080"))
BIND = os.environ.get("BIND", "0.0.0.0")
SECURE_COOKIE = os.environ.get("SECURE_COOKIE", "0") == "1"
SESSION_SECONDS = int(float(os.environ.get("SESSION_HOURS", "168")) * 3600)
ALLOWED_IPS = [ip.strip() for ip in os.environ.get("ALLOWED_IPS", "").split(",") if ip.strip()]

COOKIE = "lab_session"


def login_page(error=""):
    """Render the login page. str.replace, not %, because the CSS contains percent signs."""
    return LOGIN_PAGE.replace("{{ERROR}}", error)
MAX_FAILS = 6
FAIL_WINDOW = 600

_fails = {}
_fails_lock = threading.Lock()


def sign(ts):
    mac = hmac.new(APP_SECRET.encode(), str(ts).encode(), hashlib.sha256).hexdigest()[:32]
    return "%d.%s" % (ts, mac)


def valid_cookie(value):
    if not value or "." not in value:
        return False
    ts_s, mac = value.split(".", 1)
    try:
        ts = int(ts_s)
    except ValueError:
        return False
    expect = hmac.new(APP_SECRET.encode(), ts_s.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(mac, expect):
        return False
    return (time.time() - ts) < SESSION_SECONDS


def too_many_fails(ip):
    now = time.time()
    with _fails_lock:
        hits = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW]
        _fails[ip] = hits
        return len(hits) >= MAX_FAILS


def note_fail(ip):
    with _fails_lock:
        _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip):
    with _fails_lock:
        _fails.pop(ip, None)


LOGIN_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in | Codility lab</title>
<style>
:root{--bar:#0e2740;--coral:#e2543f;--line:#dbe4ec}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f4f7fa;
     font:15px/1.5 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#16222e;padding:20px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:26px 24px;width:100%;max-width:380px;
      box-shadow:0 6px 24px rgba(14,39,64,.08)}
h1{font-size:19px;margin:0 0 4px;color:var(--bar)}
p.sub{margin:0 0 18px;color:#5f7080;font-size:13px}
label{display:block;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#5f7080;margin-bottom:6px}
input{width:100%;padding:12px;border:1px solid var(--line);border-radius:8px;font-size:16px;margin-bottom:14px}
button{width:100%;padding:13px;border:0;border-radius:8px;background:var(--coral);color:#fff;font-size:15px;font-weight:700}
button:active{opacity:.9}
.err{background:#fdefec;border:1px solid #f5c2b7;color:#8b2c1a;border-radius:8px;padding:10px 12px;font-size:13px;margin-bottom:12px}
.foot{margin-top:16px;font-size:12px;color:#8794a1;text-align:center}
</style></head><body>
<form class="card" method="post" action="/login">
  <h1>Codility lab</h1>
  <p class="sub">Senior Data Scientist (Analytics) practice environment</p>
  {{ERROR}}
  <label for="p">Password</label>
  <input id="p" name="password" type="password" autocomplete="current-password" autofocus required>
  <button type="submit">Enter</button>
  <div class="foot">Private instance. Sessions last 7 days.</div>
</form></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "CodilityLab/1.0"
    sys_version = ""

    # ---------------------------------------------------------------- helpers
    def client_ip(self):
        fwd = self.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
        return self.client_address[0]

    def allowed(self):
        if not ALLOWED_IPS:
            return True
        return self.client_ip() in ALLOWED_IPS

    def cookies(self):
        raw = self.headers.get("Cookie", "")
        out = {}
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k.strip()] = v.strip()
        return out

    def authed(self):
        return valid_cookie(self.cookies().get(COOKIE))

    def send_bytes(self, body, status=200, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def redirect(self, where, extra=None):
        self.send_bytes(b"", 303, extra=[("Location", where)] + list(extra or []))

    def log_message(self, fmt, *args):  # keep logs small and free of secrets
        sys.stderr.write("%s %s\n" % (self.client_ip(), fmt % args))

    # ---------------------------------------------------------------- routes
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.allowed():
            self.send_bytes(b"Not available from this network.", 403, "text/plain; charset=utf-8")
            return
        path = self.path.split("?")[0]

        if path == "/healthz":
            self.send_bytes(b'{"ok":true}', 200, "application/json")
            return
        if path == "/favicon.ico":
            self.send_bytes(b"", 204)
            return
        if path == "/login":
            if self.authed():
                self.redirect("/")
                return
            self.send_bytes(login_page().encode("utf-8"))
            return
        if path not in ("/", "/index.html"):
            self.send_bytes(b"Not found.", 404, "text/plain; charset=utf-8")
            return
        if not self.authed():
            self.redirect("/login")
            return

        wants_gz = "gzip" in self.headers.get("Accept-Encoding", "")
        if wants_gz and os.path.exists(INDEX_GZ):
            with open(INDEX_GZ, "rb") as f:
                body = f.read()
            extra = [("Content-Encoding", "gzip"), ("Vary", "Accept-Encoding"),
                     ("Cache-Control", "private, max-age=0, must-revalidate")]
        else:
            with open(INDEX, "rb") as f:
                body = f.read()
            extra = [("Cache-Control", "private, max-age=0, must-revalidate")]
        self.send_bytes(body, 200, "text/html; charset=utf-8", extra)

    def do_POST(self):
        if not self.allowed():
            self.send_bytes(b"Not available from this network.", 403, "text/plain; charset=utf-8")
            return
        path = self.path.split("?")[0]
        if path == "/logout":
            self.send_bytes(b"", 303, extra=[
                ("Location", "/login"),
                ("Set-Cookie", "%s=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax" % COOKIE),
            ])
            return
        if path != "/login":
            self.send_bytes(b"Not found.", 404, "text/plain; charset=utf-8")
            return

        ip = self.client_ip()
        if too_many_fails(ip):
            self.send_bytes(login_page('<div class="err">Too many attempts. Wait ten minutes.</div>').encode("utf-8"), 429)
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > 4096:
            self.send_bytes(b"Too large.", 413, "text/plain; charset=utf-8")
            return
        body = self.rfile.read(length).decode("utf-8", "replace")
        given = (parse_qs(body).get("password") or [""])[0]

        if APP_PASSWORD and hmac.compare_digest(given, APP_PASSWORD):
            clear_fails(ip)
            cookie = "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax%s" % (
                COOKIE, sign(int(time.time())), SESSION_SECONDS,
                "; Secure" if SECURE_COOKIE else "")
            self.send_bytes(b"", 303, extra=[("Location", "/"), ("Set-Cookie", cookie)])
            return

        note_fail(ip)
        time.sleep(0.4)  # slow down scripted guessing
        self.send_bytes(login_page('<div class="err">Wrong password.</div>').encode("utf-8"), 401)


def main():
    if not APP_PASSWORD:
        print("APP_PASSWORD is not set. Refusing to start without a password.\n"
              "Set it in .env (see .env.example) or export it in the shell.", file=sys.stderr)
        return 2
    if not os.path.exists(INDEX):
        print("app/index.html is missing. Run: python3 build/build_app.py", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    srv.daemon_threads = True
    print("Codility lab on http://%s:%d  (secure cookie: %s, ip allowlist: %s)"
          % (BIND, PORT, SECURE_COOKIE, ALLOWED_IPS or "off"), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
