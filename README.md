# Codility lab: Grab Senior Data Scientist (Analytics)

A password-gated, mobile-friendly practice exam that looks and behaves like a Codility
screen, with the learning material sitting next to the question instead of in another tab.

Two modes:

- **Exam.** Draws a fresh paper of 16 tasks: 11 knowledge questions, 3 SQL, 2 Python. One
  timer, 110 minutes, no pause, task order free. Same mechanics as the real screen.
- **Study.** All 97 bank items, no timer, searchable, with the full learning pane. This is
  where you actually learn the material before spending a paper.

The bank is six times the size of a paper on purpose: 72 knowledge questions (6.5x the 11
drawn), 15 SQL tasks (5x the 3), 10 Python tasks (5x the 2). Every paper is sampled at
random, so a second attempt is a real test of recall rather than the same questions again.

Everything runs from one HTML file. SQL executes in the browser against a real SQLite
database. Python executes in the browser too, through Pyodide, so there is no code
execution on the server at all.

---

## What is inside

```
app/server.py          password gate + static server, standard library only
app/index.html         the whole app, built (2.3 MB, 0.78 MB gzipped)
content/               the question bank, topic cards, reference library
build/gen_db.py        generates data/mock.db (deterministic seed)
build/verify.py        content gate: 5x ratio, valid MCQs, every query returns rows
build/build_app.py     inlines content, database and SQL engine into one HTML file
tests/smoke.sh         auth, gzip, tamper, logout, rate limit
tests/ui_test.py       Chrome walkthrough: login, MCQ, SQL, Python, study, mobile
```

The database is small on purpose: 1,100 users, 12,000 bookings, 479 CRM sends. It fits
inside the HTML, so the app works offline once loaded and there is no API to keep alive.

---

## Run it locally

```bash
cp .env.example .env          # then edit APP_PASSWORD
make setup                    # database, verify, build
APP_PASSWORD=localdev python3 app/server.py
# open http://localhost:8080
```

Requires Python 3.9+ and nothing else. No pip install, no virtualenv.

To test the gate end to end: `make test`. To drive the UI with a real browser:
`python3 tests/ui_test.py` with the server running (needs Playwright and Chrome).

---

## Deploy on a VPS

Sizing, measured rather than guessed: the image is 187 MB (python slim base dominates), a
running container uses about 15 MB of RAM against a 256 MB cap and 0.5 CPU, and the app
writes nothing to disk. On a 2 vCPU / 2 GB VPS this is idle weight; 40 GB of disk is far
more than needed.

`.env` is optional at the compose level so `docker compose config` works before you create
it, but the server refuses to start without `APP_PASSWORD` and says so on stderr.

### 1. Point a hostname at the box

Create an A record, for example `lab.example.com` to the VPS IPv4 address. Wait for DNS to
resolve before starting Caddy, otherwise certificate issuance fails.

### 2. Get the code and configure

```bash
git clone <your-repo-url> codility-lab && cd codility-lab
cp .env.example .env
```

Edit `.env`:

```
APP_PASSWORD=<a long random password, 20+ characters>
DOMAIN=lab.example.com
SECURE_COOKIE=1
```

Generate a password with `openssl rand -base64 24`.

### 3. Start it

```bash
docker compose --profile tls up -d --build
```

That builds the app image (the content gate runs inside the build, so a broken reference
query fails the deploy), starts the app on `127.0.0.1:8080`, and starts Caddy on 80/443
with an automatic Let's Encrypt certificate.

Open `https://lab.example.com`, enter the password, and use it.

Without a domain, two options:

```bash
# localhost only, reachable through an SSH tunnel from your laptop
docker compose up -d lab
ssh -L 8080:127.0.0.1:8080 user@your-vps
# then http://localhost:8080

# or a temporary public HTTPS URL with no open ports and no DNS, good for a phone
cloudflared tunnel --url http://127.0.0.1:8080
```

If you use the tunnel, keep `SECURE_COOKIE=0` only while testing on plain HTTP.

### 4. Check it is healthy

```bash
curl -s localhost:8080/healthz        # {"ok":true}
docker compose ps                     # both services Up, healthcheck passing
docker compose logs -f lab
```

---

## How the gate works

- One shared password, checked with a constant-time compare.
- Sessions are HMAC-signed cookies carrying a timestamp only. `HttpOnly`, `SameSite=Lax`,
  and `Secure` when `SECURE_COOKIE=1`. Default lifetime 7 days.
- Six wrong passwords from one IP in ten minutes returns 429 for the rest of the window.
  Counters are in memory, so a restart clears them.
- Optional `ALLOWED_IPS` allowlist, checked before auth.
- The server serves exactly two files by explicit path, so there is no traversal surface.
- No user input is executed server side. SQL and Python run in your browser.

Limits worth knowing: this is single-user gating, not multi-tenant auth. Anyone with the
password is in, and the cookie is signed but not encrypted. For a personal prep tool that
is the right trade-off; do not put exam content you care about behind it.

To revoke access: change `APP_PASSWORD` (and `APP_SECRET` if you set it), then restart.

---

## Updating the content

Edit the bank, then rebuild. The gate runs first and refuses to ship a broken question.

```bash
python3 build/verify.py       # 5x ratio, 4 options, valid answer index, queries return rows
python3 build/build_app.py    # rebuild app/index.html
docker compose up -d --build  # redeploy
```

- Knowledge questions: `content/bank_mcq.py` (72 items) and `content/topics.py` (the
  theory cards shown beside them).
- SQL tasks: `content/sql_tasks.py` (the verified queries) and `content/bank_sql.py`
  (learning cards).
- Python tasks: `content/bank_py.py`. The reference function's return value becomes the
  expected output, so you never hand-compute an answer.
- Reference tables: `content/library.py`.

If you add a SQL task, its reference query must return at least one row against
`data/mock.db`, otherwise the build stops. That is deliberate: an empty expected result
would make every answer look correct.

---

## Handing this to a coding agent

Paste the repo URL and this block:

```
Deploy this repository on my VPS (Ubuntu, 2 vCPU, 2 GB RAM, Docker installed).
Follow README.md exactly.

Steps:
1. Clone the repo, copy .env.example to .env.
2. Set APP_PASSWORD to a 24-character random string and print it to me at the end.
3. Set DOMAIN if I gave you one; otherwise leave the lab service bound to 127.0.0.1
   and tell me how to reach it through an SSH tunnel.
4. Run: docker compose --profile tls up -d --build
5. Verify: curl -s localhost:8080/healthz returns {"ok":true}, and
   bash tests/smoke.sh passes.
6. Do not commit .env, and do not expose port 8080 publicly without the proxy.
7. Report the URL, the password, and the output of docker compose ps.
```

---

## Troubleshooting

**Login page loads but the password is rejected.** Check `.env` has no quotes or trailing
spaces around the value. `docker compose config` prints the resolved environment.

**429 after a few attempts.** Six failures lock the IP for ten minutes. Restart the
container to clear it, or wait.

**Blank page after login.** Open the browser console. The app is a single file, so a blank
page means the file did not build: run `python3 build/build_app.py` and check
`app/index.html` exists.

**"Loading the Python runtime" never finishes.** Pyodide is fetched from jsDelivr on first
use. If the network blocks it, SQL and knowledge questions still work; write the Python
answer locally instead. The runtime is cached by the browser after the first load.

**SQL says a table does not exist.** The browser database is the one in `data/mock.db`.
Check the schema cards above the editor; the practice folder in the playbook uses the same
table names.

**Certificate errors.** DNS is not resolving yet, or port 80 is blocked. Caddy needs both
80 and 443 open to issue and renew.

---

## Why the questions look like this

The paper shape comes from published candidate accounts of Grab's Codility screen: a
knowledge block, one or more SQL tasks and a coding task, all under one timer, with sample
data you can run against. The topics follow the job description: CRM analytics,
experimentation, lifecycle segmenting, predictive modelling and applied LLM tooling.
Nothing here is leaked exam content, and the reference queries are checked mechanically
rather than trusted.
