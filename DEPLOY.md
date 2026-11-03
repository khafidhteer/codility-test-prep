# Deploy runbook

Written for a coding agent on a fresh VPS, and detailed enough that a human can follow it
with no prior context. Every command is copy-paste, every step states what success looks
like, and every failure I have actually hit has an entry in the playbook at the end.

Target: Ubuntu 22.04 or 24.04, 2 vCPU, 2 GB RAM. Nothing else is required except Docker.

---

## 0. What "deployed" means here

The app is a single HTML file served by a 250-line Python process behind a password, with
optional Caddy in front for HTTPS. There is no database server, no build toolchain on the
host, and nothing to install with pip. The container is capped at 256 MB and half a CPU;
it actually uses about 15 MB.

Done means all of these are true:

1. `docker compose ps` shows `lab` as `running (healthy)`.
2. `curl -s localhost:8080/healthz` prints exactly `{"ok":true}`.
3. `bash scripts/verify_deploy.sh <url> <password>` prints `VERIFIED: <n> checks passed`.
4. You have told the user the URL and the password.

---

## 1. Prerequisites

Run these five checks first. Each prints a line; anything other than the expected output
means fix it before going further.

```bash
# 1. the OS (expect Ubuntu 22.04 or 24.04, anything Debian-based is fine)
. /etc/os-release && echo "$PRETTY_NAME"

# 2. docker present (expect "Docker version 24" or newer)
docker --version

# 3. daemon running (expect a Server block, not "Cannot connect")
docker info | head -5

# 4. compose v2 (expect "Docker Compose version v2.x")
docker compose version

# 5. free space, expect more than 2 GB
df -h / | tail -1
```

If Docker is missing:

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # log out and back in, or prefix commands with sudo
```

---

## 2. Get the repository onto the VPS

The repo is private. The agent needs one of two things: an SSH deploy key, or a token.

**Option A, deploy key (recommended).**

```bash
ssh-keygen -t ed25519 -C "vps-deploy" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
```

Add that public key at `https://github.com/khafidhteer/codility-test-prep/settings/keys`
with **read** access (write only if the agent will push). Then:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-codility
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config

git clone git@github-codility:khafidhteer/codility-test-prep.git codility-lab
```

**Option B, token over HTTPS.**

```bash
git clone https://<TOKEN>@github.com/khafidhteer/codility-test-prep.git codility-lab
```

Do not leave the token in shell history or in the remote URL. If you use it, set the remote
back to a clean URL afterwards:

```bash
cd codility-lab && git remote set-url origin https://github.com/khafidhteer/codility-test-prep.git
```

Expected after cloning: `ls` shows `README.md`, `DEPLOY.md`, `Dockerfile`,
`docker-compose.yml`, `Caddyfile`, `content/`, `build/`, `app/`, `scripts/`, `tests/`,
`Makefile`, `.env.example`.

---

## 3. Configure

```bash
cd codility-lab
cp .env.example .env
```

Edit `.env`. Two decisions:

| Setting | Choose it when | Effect |
|---|---|---|
| `DOMAIN=lab.example.com` | you own a domain and can point an A record at this VPS | HTTPS through Caddy, certificate issued automatically |
| `DOMAIN=` (empty) | no domain | app on `127.0.0.1:8080`, reach it through an SSH tunnel |

Leave `APP_PASSWORD` as the placeholder and the deploy script generates a strong one and
writes it back. If you set it yourself, use 20 characters or more.

Do not set `SECURE_COOKIE` by hand. The deploy script sets it to `1` for a domain and `0`
for plain-HTTP localhost, and getting it wrong produces a login that appears to succeed and
then bounces straight back.

For the domain path, create the DNS record **before** deploying:

```bash
dig +short lab.example.com          # must print this server's public IPv4
curl -s https://api.ipify.org       # this server's public IPv4, for comparison
```

If those two disagree, Caddy cannot get a certificate and the deploy will look broken.

---

## 4. Deploy

One command. It is idempotent, so re-running after any failure is safe.

```bash
bash scripts/deploy.sh
```

What it does, in order, and what you should see:

```
== preflight
   ok: docker and compose available
   ok: host checks passed
== configuration
   ok: created .env from .env.example
   ok: generated a password and wrote it to .env
   ok: no domain set, localhost mode on 127.0.0.1:8080
   ok: compose file validates
== build (runs the content gate inside the image)
   ... buildkit output, ends with "naming to docker.io/library/..."
== start
   ... "Container <name>-lab-1  Started"
== waiting for health
   ok: healthy after 6s
== verifying the auth flow
   ok   healthz responds
   ok   unauthenticated requests are redirected
   ok   unknown paths return 404, no directory listing
   ok   wrong password rejected
   ok   password accepted, session cookie set
   ok   app served to an authenticated session
   ok   payload 814927 bytes gzipped, contains the app
   ok   forged cookies rejected
   ok   logout clears the session

   VERIFIED: 9 checks passed against http://127.0.0.1:8080
== done
   mode      : local
   url       : http://127.0.0.1:8080
   password  : <generated>
   stored in : /home/<user>/codility-lab/.env
```

With a domain, the mode line reads `tls`, the URL is `https://lab.example.com`, and one
extra check appears for the certificate chain.

The first build takes two to four minutes because it pulls the Python base image, generates
the database and verifies every reference answer inside the build. Later builds are seconds.

### Variants

```bash
bash scripts/deploy.sh --force    # skip the DNS precheck (Cloudflare proxy in front)
bash scripts/deploy.sh --public   # publish on 0.0.0.0:8080, plain HTTP
```

`--public` is for a throwaway test only. The password crosses the network in clear text.
For phone access without a domain, prefer a tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

---

## 5. Reach it

**With a domain:** open `https://lab.example.com`, enter the password.

**Without a domain, from a laptop:**

```bash
ssh -L 8080:127.0.0.1:8080 <user>@<server-ip>
# leave that open, then browse http://localhost:8080
```

From a phone, the tunnel above is the practical route: `cloudflared` prints a temporary
`https://<random>.trycloudflare.com` URL that works in mobile Safari or Chrome.

---

## 6. Verify independently

Never trust the deploy script alone. Run this and read the output:

```bash
docker compose ps
#   NAME              SERVICE   STATUS                   PORTS
#   ...-lab-1         lab       running (healthy)        127.0.0.1:8080->8080/tcp

curl -s localhost:8080/healthz
#   {"ok":true}

bash scripts/verify_deploy.sh http://127.0.0.1:8080 "$(grep ^APP_PASSWORD .env | cut -d= -f2)"
#   ... VERIFIED: 9 checks passed

docker stats --no-stream --format 'mem={{.MemUsage}}' $(docker compose ps -q lab)
#   mem=14.8MiB / 256MiB

docker images --format '{{.Repository}} {{.Size}}' | grep codility
#   codility-lab  187MB
```

All four numbers should match the ranges above. If memory is far higher, the build stage is
wrong and the runtime image contains the whole build context.

---

## 7. Failure playbook

| Symptom | Cause | Fix |
|---|---|---|
| `the docker daemon is not running` | Docker not started, or the agent shell lacks group membership | `sudo systemctl enable --now docker`, or run with `sudo`, or `newgrp docker` |
| `docker compose version` prints "docker-compose" v1 | Compose v2 plugin missing | `sudo apt-get install -y docker-compose-plugin` |
| `docker compose config rejected the files` | `.env` has quotes or trailing spaces | Print `.env`, remove quotes, keep `KEY=value` with no spaces |
| Build fails at `python build/verify.py` | a content edit broke a reference answer | The message names the task id. Fix `content/`, or `git checkout` the change |
| Build fails with `toomanyrequests` | Docker Hub rate limit | `docker login` with any account, then rebuild |
| `the app did not become healthy within 120s` | container crashed on start | `docker compose logs --tail=50 lab`. Usually a missing `APP_PASSWORD` |
| Login accepts the password but bounces to `/login` | `SECURE_COOKIE=1` while serving plain HTTP | Set `SECURE_COOKIE=0` in `.env`, re-run the deploy script |
| Password rejected with 401 for a password you copied | shell quoting or trailing whitespace in `.env` | `grep ^APP_PASSWORD .env \| cat -A` and remove invisible characters |
| 429 on login | six failed attempts locked the IP for ten minutes | `docker compose restart lab` clears the in-memory counters |
| Caddy keeps restarting | DNS not pointing here, or port 80 blocked | `docker compose logs caddy`; fix DNS; open 80 and 443 |
| `port 80 is already in use` | nginx or apache on the host | `sudo ss -ltnp \| grep :80`, stop it, or run localhost mode instead |
| Let's Encrypt rate limit after repeated retries | too many failed issuances | Wait an hour, or use `--force` with a Cloudflare-proxied domain |
| Blank page after login | HTML was never built inside the image | `docker compose build --no-cache` |
| "Loading the Python runtime" never finishes | the browser cannot reach jsDelivr | Expected on a locked-down network. Knowledge and SQL still work |

Logs, in order of usefulness:

```bash
docker compose logs --tail=100 lab     # app
docker compose logs --tail=100 caddy   # certificates, in tls mode
docker compose exec lab ls -la /app/app   # is index.html actually in the image
```

---

## 8. Operations

```bash
# restart, after a config change
docker compose restart lab

# update to the latest commit
git pull && bash scripts/deploy.sh

# rotate the password
sed -i "s/^APP_PASSWORD=.*/APP_PASSWORD=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | cut -c1-24)/" .env
docker compose up -d lab          # recreates with the new value
grep ^APP_PASSWORD .env

# stop, keep volumes (certificates survive)
docker compose stop

# remove everything except the images
docker compose down

# remove everything including certificates (re-issues on next start)
docker compose down -v
```

Anything under `data/` is generated, so there is nothing to back up. The only state worth
keeping is `.env`.

---

## 9. Rules for the deploying agent

These are not stylistic. Breaking one produces a deployment that looks fine and is not.

1. Never commit `.env`, and never echo its contents into a public log or a commit message.
2. Never publish port 8080 on `0.0.0.0` unless the user explicitly asked for plain HTTP.
   The default binding is `127.0.0.1` and it should stay that way.
3. Do not change the container port. If you must, change it in `docker-compose.yml` and in
   the Caddyfile `reverse_proxy` target together, or TLS will proxy to nothing.
4. Do not run `docker compose down -v` to "clean up". It deletes the certificate volume and
   triggers re-issuance, which can burn a Let's Encrypt rate limit.
5. Run `bash scripts/verify_deploy.sh` after every deploy and paste its last line into the
   report. A deploy without that line is unverified.
6. Report exactly four facts to the user: the URL, the password, the `docker compose ps`
   status, and the verify line. Nothing else is useful to them.
7. If any step fails, stop and report the failure with the last 40 log lines. Do not retry
   with invented workarounds such as disabling the password gate or exposing the port.

---

## 10. Copy-paste prompt for the agent

```
Deploy the repository https://github.com/khafidhteer/codility-test-prep on this VPS.
Read DEPLOY.md first and follow it exactly; do not improvise.

Context: Ubuntu VPS, 2 vCPU, 2 GB RAM, Docker should be present.
The repository is private; if the clone fails, set up a deploy key as described in
DEPLOY.md section 2 and tell me what public key to add.

Do this:
1. Run the five prerequisite checks in DEPLOY.md section 1 and report their output.
2. Clone the repo into ~/codility-lab.
3. Ask me for a domain if I have not given one. If I have none, deploy in localhost
   mode and tell me the SSH tunnel command.
4. Copy .env.example to .env, set DOMAIN, and leave APP_PASSWORD as the placeholder so
   the script generates one.
5. Run: bash scripts/deploy.sh
6. Independently verify with the four commands in DEPLOY.md section 6.
7. Report back: the URL, the generated password, the docker compose ps status line, and
   the VERIFIED line from scripts/verify_deploy.sh.

Constraints: do not commit .env, do not expose port 8080 publicly, do not use
docker compose down -v. If something fails, paste the last 40 log lines and stop.
```
