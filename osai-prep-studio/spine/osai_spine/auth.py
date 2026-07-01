"""Optional authentication (opt-in via ``OSAI_AUTH=1``) — stdlib only.

Off by default, so the offline/demo/CI flows (learner id supplied in the request) are
unchanged. When enabled, learner-scoped endpoints derive the learner from a verified
**session token** rather than a client-supplied id, so a user can only act as
themselves.

Primitives (no third-party deps):
  * passwords hashed with PBKDF2-HMAC-SHA256 + a per-user random salt;
  * stateless session tokens = ``base64(payload).base64(HMAC-SHA256(payload))`` with an
    expiry, verified with a constant-time compare (same HMAC discipline as the flags).

The signing secret and password hashes are read/stored server-side only; tokens carry
just the username + expiry, never the password.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time

_TRUTHY = {"1", "true", "on", "yes"}
PBKDF2_ITERS = 200_000
TOKEN_TTL = 12 * 3600  # seconds
MIN_PASSWORD_LEN = 8


def auth_enabled() -> bool:
    return os.environ.get("OSAI_AUTH", "").strip().lower() in _TRUTHY


class AuthError(Exception):
    """Registration/validation failure (bad input, duplicate user)."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(txt: str) -> bytes:
    return base64.urlsafe_b64decode(txt + "=" * (-len(txt) % 4))


class AuthStore:
    """SQLite-backed user store + stateless token issuer/verifier."""

    def __init__(self, db_path: str = ":memory:", secret: str | None = None):
        self.secret = (
            secret or os.environ.get("OSAI_AUTH_SECRET") or "dev-auth-secret-change-me"
        ).encode()
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS user ("
                "  username   TEXT PRIMARY KEY,"
                "  salt       BLOB NOT NULL,"
                "  pw_hash    BLOB NOT NULL,"
                "  created_ts REAL NOT NULL)"
            )
            self.conn.commit()

    @staticmethod
    def _hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)

    # --- accounts ----------------------------------------------------------
    def register(self, username: str, password: str, now: float | None = None) -> str:
        username = (username or "").strip()
        if not username or len(username) > 64:
            raise AuthError("username required (<= 64 chars)")
        if not password or len(password) < MIN_PASSWORD_LEN:
            raise AuthError(f"password must be at least {MIN_PASSWORD_LEN} characters")
        now = float(now) if now is not None else time.time()
        salt = os.urandom(16)
        pw_hash = self._hash(password, salt)
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT INTO user(username,salt,pw_hash,created_ts) VALUES(?,?,?,?)",
                    (username, salt, pw_hash, now),
                )
                self.conn.commit()
            except sqlite3.IntegrityError:
                raise AuthError("username already taken")
        return username

    def verify_password(self, username: str, password: str) -> bool:
        row = self.conn.execute(
            "SELECT salt,pw_hash FROM user WHERE username=?", (username,)
        ).fetchone()
        if not row:
            return False
        candidate = self._hash(password or "", row["salt"])
        return hmac.compare_digest(candidate, row["pw_hash"])

    # --- tokens ------------------------------------------------------------
    def issue_token(self, username: str, ttl: int = TOKEN_TTL, now: float | None = None) -> str:
        now = float(now) if now is not None else time.time()
        payload = json.dumps({"sub": username, "exp": now + ttl}, separators=(",", ":"))
        body = _b64e(payload.encode())
        sig = _b64e(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def verify_token(self, token: str, now: float | None = None):
        """Return the username for a valid, unexpired token, else ``None``."""
        now = float(now) if now is not None else time.time()
        try:
            body, sig = (token or "").split(".", 1)
        except ValueError:
            return None
        expected = _b64e(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            payload = json.loads(_b64d(body))
        except Exception:
            return None
        if float(payload.get("exp", 0)) < now:
            return None
        return payload.get("sub")
