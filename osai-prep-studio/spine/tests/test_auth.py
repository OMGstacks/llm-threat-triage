"""Optional auth core: PBKDF2 password hashing + HMAC-signed session tokens."""

import pytest

from osai_spine.auth import AuthError, AuthStore, auth_enabled


def _store():
    return AuthStore(secret="test-secret")


def test_register_and_verify_password():
    s = _store()
    s.register("alice", "correct-horse")
    assert s.verify_password("alice", "correct-horse") is True
    assert s.verify_password("alice", "wrong-password") is False
    assert s.verify_password("nobody", "whatever") is False  # unknown user


def test_password_never_stored_plaintext():
    s = _store()
    s.register("alice", "correct-horse")
    row = s.conn.execute("SELECT salt,pw_hash FROM user WHERE username='alice'").fetchone()
    assert b"correct-horse" not in row["pw_hash"] and row["salt"] != row["pw_hash"]


def test_register_rejects_bad_input():
    s = _store()
    with pytest.raises(AuthError):
        s.register("alice", "short")          # < 8 chars
    with pytest.raises(AuthError):
        s.register("", "long-enough-pw")      # empty username
    s.register("bob", "long-enough-pw")
    with pytest.raises(AuthError):
        s.register("bob", "another-good-pw")  # duplicate


def test_token_roundtrip_and_expiry():
    s = _store()
    s.register("alice", "correct-horse")
    tok = s.issue_token("alice", ttl=100, now=1000.0)
    assert s.verify_token(tok, now=1050.0) == "alice"   # within ttl
    assert s.verify_token(tok, now=2000.0) is None       # expired


def test_token_tamper_and_wrong_secret_rejected():
    s = _store()
    tok = s.issue_token("alice", now=1000.0)
    assert s.verify_token("not.a.token") is None
    assert s.verify_token(tok[:-3] + "xyz", now=1000.0) is None  # bad signature
    # a different secret cannot verify the token
    other = AuthStore(secret="different-secret")
    assert other.verify_token(tok, now=1000.0) is None


def test_salts_are_unique_per_user():
    s = _store()
    s.register("alice", "same-password")
    s.register("bob", "same-password")
    a = s.conn.execute("SELECT salt,pw_hash FROM user WHERE username='alice'").fetchone()
    b = s.conn.execute("SELECT salt,pw_hash FROM user WHERE username='bob'").fetchone()
    assert a["salt"] != b["salt"] and a["pw_hash"] != b["pw_hash"]  # same pw, different hash


def test_auth_enabled_env(monkeypatch):
    monkeypatch.delenv("OSAI_AUTH", raising=False)
    assert auth_enabled() is False
    monkeypatch.setenv("OSAI_AUTH", "1")
    assert auth_enabled() is True
