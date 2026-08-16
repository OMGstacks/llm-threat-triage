"""An intentionally web-vulnerable AI application — the target for the web/API assessment.

Modern LLM apps ARE web/API apps: their attack surface is REST endpoints, auth/session handling,
SSRF-able tool calls, IDOR on conversation objects, and XSS from model-rendered output. This target
models that intersection: a small "AcmeChat" API around the LLM assistant, carrying the classic
web/API flaws an app pentester looks for — each mapped to OWASP **API/Web** Top 10 (not the LLM Top
10) so the range demonstrates conventional application-security testing, not just prompt injection.

Deterministic and std-lib only, like the rest of the range, so exploit success is ground truth. Each
handler runs in ``vulnerable`` or ``hardened`` mode; the hardened path is the fix under test.

Vulnerabilities modeled (vulnerable mode):
  * SSRF        — an agent "url fetch" tool follows an attacker-supplied URL to internal metadata.
  * IDOR        — GET /conversations/{id} returns any user's transcript with no ownership check.
  * Broken auth — GET /admin/config serves secrets with no/weak token.
  * Reflected XSS — /search reflects the query into HTML unescaped.
  * SQLi        — /history builds a query by string concatenation; ' OR '1'='1 dumps all rows.

The hardened mode applies the textbook fix for each (allowlist+block-internal, ownership check,
constant-time token check, HTML-escaping, parameterized query).
"""

from __future__ import annotations

import html
import hmac
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

# --- fake internal data (never real secrets) ---
ADMIN_TOKEN = "acme-admin-7f3d"                       # the "correct" admin token
ADMIN_CONFIG = {"db_dsn": "postgres://acme:not-real@db.internal/acme", "aws_key": "AKIAIOSFODNN7EXAMPLE"}
INTERNAL_METADATA = "iam-role: acme-app; secret: AKIAIOSFODNN7EXAMPLE"   # what SSRF reaches

# conversations owned by users (IDOR target)
CONVERSATIONS = {
    "conv-1001": {"owner": "user-alice", "text": "alice: how do refunds work?"},
    "conv-1002": {"owner": "user-bob",   "text": "bob: my card ending 4242 was double charged"},
}
# chat history rows (SQLi target)
HISTORY_ROWS = [
    {"id": 1, "user": "user-alice", "q": "refund policy?"},
    {"id": 2, "user": "user-bob",   "q": "billing address change"},
    {"id": 3, "user": "user-admin", "q": "rotate the prod aws key"},   # sensitive row SQLi can leak
]

# hosts a server-side "fetch" tool is legitimately allowed to reach
EGRESS_ALLOWLIST = {"api.acme.example", "docs.acme.example"}
# internal ranges SSRF tries to reach
_INTERNAL_HOSTS = {"169.254.169.254", "localhost", "127.0.0.1", "metadata.internal"}


@dataclass
class Resp:
    """Result of one request against the app, with ground-truth exploit flags."""
    status: int
    body: str
    ssrf_reached_internal: bool = False
    idor_leaked_other_user: bool = False
    auth_bypassed: bool = False
    xss_reflected_unescaped: bool = False
    sqli_dumped_extra_rows: bool = False
    blocked: bool = False
    notes: list = field(default_factory=list)


class AcmeWebApp:
    def __init__(self, mode: str = "vulnerable"):
        if mode not in ("vulnerable", "hardened"):
            raise ValueError("mode must be 'vulnerable' or 'hardened'")
        self.mode = mode

    # --- SSRF: server-side URL fetch (an agent tool) ---
    def fetch_url(self, url: str) -> Resp:
        host = (urlparse(url).hostname or "").lower()
        if self.mode == "hardened":
            # allowlist + block internal/link-local; never fetch by raw IP outside the allowlist
            if host not in EGRESS_ALLOWLIST or host in _INTERNAL_HOSTS:
                return Resp(403, "egress blocked: host not on allowlist", blocked=True,
                            notes=["SSRF fix: egress allowlist + internal-range denylist"])
            return Resp(200, f"fetched {host}: ok")
        # vulnerable: follows whatever it is handed
        if host in _INTERNAL_HOSTS:
            return Resp(200, INTERNAL_METADATA, ssrf_reached_internal=True,
                        notes=["SSRF: fetched internal metadata endpoint"])
        return Resp(200, f"fetched {host}: ok")

    # --- IDOR: read a conversation by id ---
    def get_conversation(self, conv_id: str, as_user: str) -> Resp:
        conv = CONVERSATIONS.get(conv_id)
        if not conv:
            return Resp(404, "not found")
        if self.mode == "hardened" and conv["owner"] != as_user:
            return Resp(403, "forbidden: not your conversation", blocked=True,
                        notes=["IDOR fix: ownership check on the object"])
        leaked = conv["owner"] != as_user
        return Resp(200, conv["text"], idor_leaked_other_user=leaked,
                    notes=["IDOR: returned another user's transcript"] if leaked else [])

    # --- Broken auth: admin config endpoint ---
    def admin_config(self, token: Optional[str]) -> Resp:
        if self.mode == "hardened":
            if not token or not hmac.compare_digest(token, ADMIN_TOKEN):
                return Resp(401, "unauthorized", blocked=True,
                            notes=["auth fix: constant-time token check, deny by default"])
            return Resp(200, str(ADMIN_CONFIG))
        # vulnerable: no real check — any/empty token is accepted
        bypass = (token != ADMIN_TOKEN)
        return Resp(200, str(ADMIN_CONFIG), auth_bypassed=bypass,
                    notes=["broken auth: secrets served without a valid token"] if bypass else [])

    # --- Reflected XSS: search echoes the query ---
    def search(self, query: str) -> Resp:
        if self.mode == "hardened":
            safe = html.escape(query)
            return Resp(200, f"<p>No results for: {safe}</p>",
                        notes=["XSS fix: HTML-escape reflected input"])
        page = f"<p>No results for: {query}</p>"   # reflected raw
        reflected = bool(re.search(r"<script|onerror=|javascript:", query, re.I)) and query in page
        return Resp(200, page, xss_reflected_unescaped=reflected,
                    notes=["reflected XSS: active content echoed unescaped"] if reflected else [])

    # --- SQLi: history search by naive string concat ---
    def history(self, user: str, term: str) -> Resp:
        # A mock "SQL" evaluator: the vulnerable query is  WHERE user='{user}' AND q LIKE '%{term}%'
        if self.mode == "hardened":
            # parameterized: term is bound, never breaks out; scope stays pinned to `user`
            rows = [r for r in HISTORY_ROWS if r["user"] == user and term in r["q"]]
            return Resp(200, str(rows), notes=["SQLi fix: parameterized query + user scoping"])
        # vulnerable: classic  ' OR '1'='1  tautology dumps every row across users
        injected = "' or '1'='1" in term.lower() or "' or 1=1" in term.lower()
        if injected:
            rows = list(HISTORY_ROWS)   # tautology returns everything
            extra = any(r["user"] != user for r in rows)
            return Resp(200, str(rows), sqli_dumped_extra_rows=extra,
                        notes=["SQLi: tautology bypassed the user filter, dumped all rows"])
        rows = [r for r in HISTORY_ROWS if r["user"] == user and term in r["q"]]
        return Resp(200, str(rows))
