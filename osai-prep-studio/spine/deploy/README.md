# Deploy — OSAI Prep Studio

Container artifacts + a runbook for standing up the studio, from a laptop demo to a
controlled beta. Everything here honours the platform threat model
([13-platform-threat-model.md](../../13-platform-threat-model.md)) and the data-handling
policy ([docs/security/api-key-and-data-handling.md](../../docs/security/api-key-and-data-handling.md)):
secrets live in files/managers (never image layers or git), lab targets get deny-all
egress, and a public deploy **fails closed** unless auth is configured.

## What's here

| File | Purpose |
|------|---------|
| `Dockerfile.grader` | FastAPI grader API image (vendors the reused detection engine + reference corpus). |
| `Dockerfile.labtarget` | A deliberately-vulnerable lab-target container (HTTP wrapper around a mock/Ollama target); one image serves any lab via `OSAI_LAB`. |
| `Dockerfile.web` | Next.js front-end, standalone production build, non-root. |
| `docker-compose.yml` | **Dev**: grader (no auth) + three isolated lab targets — chat (L01), RAG (L02), MCP (L11) — on an internal network. |
| `docker-compose.beta.yml` | **Beta**: grader (auth + cookie/CSRF + fail-closed guard, secret from a file) + web. Grader is not published; only web is. |
| `docker-compose.llm.yml` | Overlay: enable the tutor's generative path with the Anthropic key from a Docker **secret**. |
| `docker-compose.ollama.yml` | Overlay: swap the mock lab targets for real, locally-hosted Ollama models (weights pre-pulled into a volume; runtime has no egress). |
| `docker-compose.tls.yml` + `Caddyfile` | Overlay: a Caddy reverse proxy terminating HTTPS in front of `web` (auto Let's Encrypt or local cert) + baseline security headers. |

The three compose overlays compose with each other and with the dev/beta base.

---

## 1 — Dev (offline, no auth)

The fastest loop; deterministic mock targets, no secrets, no model.

```bash
cd osai-prep-studio/spine/deploy
docker compose up --build
# grader  -> http://localhost:8077/health
# L01 live target -> http://localhost:9001  (on an internal, egress-denied network)
```

## 2 — Controlled beta (auth on, fail-closed)

```bash
cd osai-prep-studio/spine/deploy

# a) token-signing secret -> a git-ignored FILE (never an env var or image layer):
mkdir -p secrets
openssl rand -hex 32 > secrets/osai_auth_secret

# b) per-deploy config via your shell env (compose fails to start if these are unset):
export OSAI_SERVER_SEED="$(openssl rand -hex 32)"   # flag-derivation seed (keep secret)
export OSAI_ADMIN_USERS="you@example.com"           # instructor account(s), comma-separated

# c) bring it up (grader is internal-only; web is the only published port):
docker compose -f docker-compose.beta.yml up --build -d

# d) register the instructor account, then log in from the web UI at http://localhost:8080
#    (the first registration for a username in OSAI_ADMIN_USERS gets the instructor role).
```

**TLS.** Secure cookies (`OSAI_COOKIE_SECURE=1`, the default) are only sent over HTTPS,
so real exposure needs TLS in front of `web`. The shipped **Caddy overlay** does this
(automatic Let's Encrypt for a real domain, or a locally-trusted cert for `localhost`),
and adds transport/baseline headers (HSTS, `nosniff`, frame-deny, referrer). The
front-end app additionally emits a **per-request nonce-based Content-Security-Policy**
from its Next.js middleware (`web/middleware.ts`), which Caddy passes through unchanged:

```bash
export OSAI_SITE_ADDRESS=studio.example.com   # or leave unset for https://localhost
docker compose -f docker-compose.beta.yml -f docker-compose.tls.yml up --build -d
# public entrypoint is now https://$OSAI_SITE_ADDRESS (Caddy terminates TLS -> web -> grader)
```

With Caddy fronting it, firewall off the web container's redundant `:8080` publish so
Caddy is the only entrypoint. For a closed LAN trial over plain HTTP only (no proxy), set
`OSAI_COOKIE_SECURE=0` — never do this on a routable network.

**Why it's safe by construction.** The grader runs with `OSAI_PUBLIC=1`, so
`osai_spine.auth.enforce_deploy_policy` **refuses to start** unless auth is on with a
strong (≥32-char), non-default signing secret. A missing secret file, the default secret,
or a short one aborts boot — you cannot accidentally publish an open instance.

### Enable the tutor (optional, adds the Anthropic key as a secret)

```bash
mkdir -p secrets && printf '%s' "$ANTHROPIC_API_KEY" > secrets/anthropic_api_key
docker compose -f docker-compose.beta.yml -f docker-compose.llm.yml up --build -d
docker compose exec grader python -m osai_spine.cli llm    # presence-only check, never prints the key
```

`OSAI_LLM_TRANSCRIPTS` stays **unset** — learner-transcript judging remains held off
until the operational data-handling controls (retention, redaction sign-off) are met.

### Real model lab targets (optional Ollama overlay)

```bash
# 1) pre-pull weights into a volume (the ONLY step granted egress):
docker compose -f docker-compose.yml -f docker-compose.ollama.yml \
    --profile pull run --rm ollama-pull
# 2) run with the real, weakly-guardrailed models behind the same target contracts:
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

This backs **all three target kinds** — chat (L01, `:9001`), RAG (L02, `:9002`), and
MCP (L11, `:9011`) — with one shared `ollama` server; every target and the server run on
the internal `labnet` (no egress, no published model port). The backend-agnostic
factories (`labtarget.make_{chat,rag,mcp}_target`) keep the grader loop identical whether
the mock or the real model answers. Pick a model with `OSAI_OLLAMA_MODEL` (default
`llama3.2:3b`); one pull serves every target.

---

## 3 — Smoke test

```bash
# health + advertised feature flags (auth_enabled / cookie_auth):
curl -fsS http://localhost:8077/health          # dev
# beta: hit the web proxy instead (grader isn't published):
curl -fsS http://localhost:8080/api/health

# fail-closed guard actually fires (should error, NOT start):
docker run --rm -e OSAI_PUBLIC=1 osai-grader:beta \
  python -c "from osai_spine import auth; auth.enforce_deploy_policy()" \
  && echo "UNEXPECTED: guard did not fire" || echo "OK: guard fails closed"
```

---

## Pre-beta checklist

Operational gate before inviting external learners. Code-level controls are already
enforced; this list is the deploy-time confirmation.

- [ ] **Secrets are files, not env/layers** — `secrets/osai_auth_secret` exists, is
      ≥32 chars, git-ignored (`git check-ignore` passes), and readable only by you.
- [ ] **Fail-closed verified** — the smoke-test guard command above errors as expected.
- [ ] **Auth + cookie/CSRF on** — `/api/health` reports `auth_enabled: true` and
      `cookie_auth: true`.
- [ ] **TLS in front of `web`** — the Caddy overlay (`docker-compose.tls.yml`) with
      `OSAI_SITE_ADDRESS` set, or a closed LAN with `OSAI_COOKIE_SECURE=0` (documented).
- [ ] **Instructor bootstrapped** — `OSAI_ADMIN_USERS` set; the account has the
      `instructor` role; the admin console (roster/audit/eval) loads.
- [ ] **Lab targets isolated** — lab containers are on internal networks, no published
      ports, deny-all egress; Ollama weights were pre-pulled, not fetched at runtime.
- [ ] **Server seed is strong & secret** — `OSAI_SERVER_SEED` is random and not shared
      (it derives per-learner flags).
- [ ] **LLM data-handling** — if the tutor is on, the key is a secret. Transcript
      judging (`OSAI_LLM_TRANSCRIPTS`) stays off until sign-off; the controls are in
      place (consent, bounded retention + `osai transcripts purge`, redaction-verified
      fail-closed choke point), and the posture is visible at `/health` → `data_handling`
      and `osai transcripts status`.
- [ ] **Gold-set ship gate green** — `python -m osai_spine.cli goldset` passes
      (zero hallucinated taxonomy IDs; abstention/refusal thresholds met).
- [ ] **Backups/reset** — `OSAI_SERVER_SEED` and the auth secret are backed up (losing
      the auth secret invalidates every session; losing the seed re-keys every flag).
- [ ] **Scope & ethics** — authorized-lab-only banner present; tutor refuses real-target
      requests; no proprietary OffSec content shipped.
