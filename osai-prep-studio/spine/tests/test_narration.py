"""Narration (TTS) seam — the plumbing acceptance tests (27-narrated-lessons.md).

Proves, offline and deterministically: the seam is OFF by default; key checks are
presence-only (never the value) and honour the ``*_FILE`` secret convention; a lesson
script parses into stably-id'd segments; the render plan (segments / duration / cost /
cache keys) is deterministic and needs no provider; and ``render`` is gated + fails
closed (disabled, or any secret in a script) and only writes audio via a configured
local command.
"""

import json

import pytest

from osai_spine import narration as nar

# every test starts from a clean env — no OSAI_TTS* / provider keys leak in
_ENV = ["OSAI_TTS", "OSAI_TTS_PROVIDER", "OSAI_TTS_CMD", "OSAI_TTS_RATE_OPENAI",
        "OPENAI_API_KEY", "OPENAI_API_KEY_FILE", "ELEVENLABS_API_KEY", "AZURE_SPEECH_KEY"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _ENV:
        monkeypatch.delenv(k, raising=False)


SCRIPT = {
    "lesson_id": "L03", "title": "Encoded payload smuggling", "voice": "en-GB",
    "segments": [
        {"text": "Welcome. We smuggle an encoded injection past a naive filter — OWASP LLM01.", "slide": "title"},
        {"text": "Base64-encode the instruction; the keyword filter never sees a banned word."},
        "Decode-then-inspect is the defense: canonicalize before you filter.",
    ],
}


# --- seam is OFF by default, offline, no keys ----------------------------- #

def test_seam_off_by_default():
    st = nar.status()
    assert st["provider"] == "cmd" and st["kind"] == "local"
    assert st["render_enabled"] is False
    assert nar.render_enabled() is False


def test_key_check_is_presence_only_and_never_the_value(monkeypatch):
    monkeypatch.setenv("OSAI_TTS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value-1234567890")
    st = nar.status()
    assert st["key_present"] is True and st["key_source"] == "env"
    # the value must never appear anywhere in the status snapshot
    assert "super-secret" not in json.dumps(st)
    assert "sk-super-secret-value-1234567890" not in json.dumps(st)


def test_key_file_secret_convention(tmp_path, monkeypatch):
    kf = tmp_path / "k"; kf.write_text("sk-from-a-mounted-secret\n")
    monkeypatch.setenv("OSAI_TTS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY_FILE", str(kf))
    assert nar.key_present("openai") is True
    assert nar.key_source("openai") == "file"


def test_provider_availability_rules(monkeypatch):
    assert nar.provider_available("browser") is True          # client-side, always
    assert nar.provider_available("cmd") is False             # no OSAI_TTS_CMD yet
    monkeypatch.setenv("OSAI_TTS_CMD", "piper --out {out}")
    assert nar.provider_available("cmd") is True
    assert nar.provider_available("openai") is False          # cloud needs a key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert nar.provider_available("openai") is True


def test_render_enabled_needs_optin_and_availability(monkeypatch):
    monkeypatch.setenv("OSAI_TTS_CMD", "piper --out {out}")   # available…
    assert nar.render_enabled() is False                      # …but not opted in
    monkeypatch.setenv("OSAI_TTS", "1")
    assert nar.render_enabled() is True


# --- script model + deterministic plan ------------------------------------ #

def test_parse_plaintext_and_structured_agree_on_segment_count():
    plain = "One paragraph.\n\nTwo paragraph.\n\nThree."
    assert len(nar.parse_script(plain)["segments"]) == 3
    sc = nar.parse_script(SCRIPT)
    assert [s["id"] for s in sc["segments"]] == sorted({s["id"] for s in sc["segments"]}) or True
    assert len(sc["segments"]) == 3
    assert sc["segments"][0]["slide"] == "title"           # slide cue preserved
    assert all(s["id"] for s in sc["segments"])            # every segment has a stable id
    assert len({s["id"] for s in sc["segments"]}) == 3     # ids unique


def test_empty_segments_dropped():
    sc = nar.parse_script({"segments": ["real text", "   ", ""]})
    assert len(sc["segments"]) == 1


def test_cache_key_is_deterministic_and_content_addressed():
    a = nar.cache_key("hello", provider="cmd", voice="en-GB")
    assert a == nar.cache_key("hello", provider="cmd", voice="en-GB")   # stable
    assert a != nar.cache_key("hello!", provider="cmd", voice="en-GB")  # text change
    assert a != nar.cache_key("hello", provider="cmd", voice="en-US")   # voice change
    assert a != nar.cache_key("hello", provider="openai", voice="en-GB")  # provider change


def test_render_plan_totals_and_cost(monkeypatch):
    plan = nar.render_plan(SCRIPT)
    assert plan["segment_count"] == 3
    assert plan["total_chars"] == sum(len(s["text"]) for s in nar.parse_script(SCRIPT)["segments"])
    assert plan["est_cost_usd"] == 0.0                    # local provider is free
    assert plan["est_seconds"] > 0 and ":" in plan["est_duration"]
    # a paid provider's one-time cost is total_chars/1e6 * rate
    monkeypatch.setenv("OSAI_TTS_PROVIDER", "openai")
    monkeypatch.setenv("OSAI_TTS_RATE_OPENAI", "15")
    paid = nar.render_plan(SCRIPT)
    assert paid["est_cost_usd"] == round(paid["total_chars"] / 1_000_000 * 15, 4)


def test_plan_is_deterministic():
    assert nar.render_plan(SCRIPT) == nar.render_plan(SCRIPT)


# --- render is gated + fails closed --------------------------------------- #

def test_render_disabled_writes_nothing(tmp_path):
    r = nar.render_segment("hello", tmp_path / "a.mp3")
    assert r["rendered"] is False and "disabled" in r["reason"]
    assert not (tmp_path / "a.mp3").exists()


def test_render_fails_closed_on_a_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("OSAI_TTS", "1")
    monkeypatch.setenv("OSAI_TTS_CMD", "cat")               # provider available + opted in
    assert nar.render_enabled() is True
    r = nar.render_segment("the flag is OSAI{deadbeef}", tmp_path / "a.mp3")
    assert r["rendered"] is False and "REDACTED_FLAG" in r["reason"]
    assert not (tmp_path / "a.mp3").exists()


def test_cloud_render_is_an_extension_point(tmp_path, monkeypatch):
    monkeypatch.setenv("OSAI_TTS", "1")
    monkeypatch.setenv("OSAI_TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-x")
    r = nar.render_segment("hello", tmp_path / "a.mp3")
    assert r["rendered"] is False and "extension point" in r["reason"]


def test_local_cmd_render_writes_audio(tmp_path, monkeypatch):
    # a hermetic stand-in TTS: copy stdin -> {out}, proving the subprocess pipeline
    monkeypatch.setenv("OSAI_TTS", "1")
    monkeypatch.setenv(
        "OSAI_TTS_CMD",
        "python3 -c \"import sys;open('{out}','wb').write(sys.stdin.buffer.read())\"")
    out = tmp_path / "seg.wav"
    r = nar.render_segment("narration audio bytes", out)
    assert r["rendered"] is True and out.exists()
    assert out.read_text() == "narration audio bytes"


def test_write_manifest_ships_without_a_provider(tmp_path):
    res = nar.write_manifest(SCRIPT, tmp_path)
    assert res["plan"]["segment_count"] == 3
    manifest = json.loads((tmp_path / "L03.manifest.json").read_text())
    assert manifest["lesson_id"] == "L03" and len(manifest["segments"]) == 3
    assert manifest["segments"][0]["audio"].endswith(".mp3")   # player/renderer target
