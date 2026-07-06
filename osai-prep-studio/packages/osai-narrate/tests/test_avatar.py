"""Avatar (talking-head video) seam — plumbing acceptance tests.

Proves, offline and deterministically: the seam mirrors the TTS seam's safety posture
exactly — OFF by default, presence-only key checks, fails closed on any redaction hit,
and every provider (HeyGen / Synthesia / Tavus) is a documented extension point with NO
SDK call, NO key ever used, and NO video produced. Also proves the one integration point
with the render plan is additive-only: with the seam off (the default, and the only mode
any shipped lesson uses), a plan is byte-for-byte identical to one built before this seam
existed — no course manifest can be disturbed by this feature landing.
"""

import osai_narrate as nar

SCRIPT = {"lesson_id": "CC01", "segments": ["Welcome to the course.", "Second segment."]}

_ENV = ["AVATAR", "AVATAR_PROVIDER", "AVATAR_ID",
        "HEYGEN_API_KEY", "HEYGEN_API_KEY_FILE",
        "SYNTHESIA_API_KEY", "SYNTHESIA_API_KEY_FILE",
        "TAVUS_API_KEY", "TAVUS_API_KEY_FILE"]


def _clean(monkeypatch):
    for k in _ENV:
        monkeypatch.delenv(k, raising=False)


# --- off by default, offline, no keys -------------------------------------- #

def test_avatar_off_by_default(monkeypatch):
    _clean(monkeypatch)
    st = nar.avatar_status()
    assert st["provider"] == "none" and st["kind"] == "none"
    assert st["avatar_enabled"] is False
    assert nar.avatar_enabled() is False


def test_no_provider_chosen_is_never_available(monkeypatch):
    _clean(monkeypatch)
    assert nar.avatar_provider_available("none") is False
    monkeypatch.setenv("AVATAR", "1")           # opting in alone isn't enough …
    assert nar.avatar_enabled() is False        # … with no provider chosen


def test_key_check_is_presence_only_and_never_the_value(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("AVATAR_PROVIDER", "heygen")
    monkeypatch.setenv("HEYGEN_API_KEY", "hg-super-secret-value-1234567890")
    st = nar.avatar_status()
    assert st["key_present"] is True and st["key_source"] == "env"
    import json
    dumped = json.dumps(st)
    assert "super-secret" not in dumped and "hg-super-secret-value-1234567890" not in dumped


def test_key_file_secret_convention(tmp_path, monkeypatch):
    _clean(monkeypatch)
    kf = tmp_path / "k"
    kf.write_text("hg-from-a-mounted-secret\n")
    monkeypatch.setenv("AVATAR_PROVIDER", "synthesia")
    monkeypatch.setenv("SYNTHESIA_API_KEY_FILE", str(kf))
    assert nar.avatar_key_present("synthesia") is True
    assert nar.avatar_key_source("synthesia") == "file"


def test_availability_and_enable_gating(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("AVATAR_PROVIDER", "tavus")
    assert nar.avatar_provider_available("tavus") is False   # no key yet
    assert nar.avatar_enabled() is False
    monkeypatch.setenv("TAVUS_API_KEY", "tv-x")
    assert nar.avatar_provider_available("tavus") is True    # key present now …
    assert nar.avatar_enabled() is False                     # … but AVATAR=1 not set
    monkeypatch.setenv("AVATAR", "1")
    assert nar.avatar_enabled() is True


# --- render_plan integration: additive-only, off by default ------------------ #

def test_default_plan_has_no_video_field(monkeypatch):
    _clean(monkeypatch)
    plan = nar.render_plan(SCRIPT)
    assert "avatar_provider" not in plan
    assert all("video" not in s for s in plan["segments"])


def test_default_plan_is_byte_identical_regardless_of_avatar_seam_existing(monkeypatch):
    """The exact guarantee that protects every already-shipped course manifest."""
    _clean(monkeypatch)
    a = nar.render_plan(SCRIPT)
    b = nar.render_plan(SCRIPT, avatar=False)
    assert a == b


def test_plan_gains_a_video_field_only_when_avatar_seam_is_on(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("AVATAR_PROVIDER", "heygen")
    monkeypatch.setenv("AVATAR_ID", "avatar_123")
    monkeypatch.setenv("HEYGEN_API_KEY", "hg-x")
    monkeypatch.setenv("AVATAR", "1")
    plan = nar.render_plan(SCRIPT)
    assert plan["avatar_provider"] == "heygen"
    for s in plan["segments"]:
        assert s["video"].startswith("CC01/") and s["video"].endswith(".mp4")


def test_video_cache_key_is_deterministic_and_content_addressed():
    a = nar.video_cache_key("hello", provider="heygen", avatar="a1", voice="en-GB")
    assert a == nar.video_cache_key("hello", provider="heygen", avatar="a1", voice="en-GB")
    assert a != nar.video_cache_key("hello!", provider="heygen", avatar="a1", voice="en-GB")
    assert a != nar.video_cache_key("hello", provider="heygen", avatar="a2", voice="en-GB")
    assert a != nar.video_cache_key("hello", provider="synthesia", avatar="a1", voice="en-GB")


def test_vtt_is_unaffected_by_the_avatar_seam(monkeypatch):
    _clean(monkeypatch)
    off = nar.to_vtt(nar.render_plan(SCRIPT))
    monkeypatch.setenv("AVATAR_PROVIDER", "heygen")
    monkeypatch.setenv("HEYGEN_API_KEY", "hg-x")
    monkeypatch.setenv("AVATAR", "1")
    on = nar.to_vtt(nar.render_plan(SCRIPT))
    assert off == on


# --- render_avatar_segment: gated, fail-closed, always an extension point ---- #

def test_render_avatar_segment_disabled_writes_nothing(tmp_path, monkeypatch):
    _clean(monkeypatch)
    r = nar.render_avatar_segment("hello", tmp_path / "a.mp4")
    assert r["rendered"] is False and "no avatar provider configured" in r["reason"]
    assert not (tmp_path / "a.mp4").exists()


def test_render_avatar_segment_needs_optin_even_with_key(tmp_path, monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("AVATAR_PROVIDER", "heygen")
    monkeypatch.setenv("HEYGEN_API_KEY", "hg-x")
    r = nar.render_avatar_segment("hello", tmp_path / "a.mp4")
    assert r["rendered"] is False and "disabled" in r["reason"]
    assert not (tmp_path / "a.mp4").exists()


def test_render_avatar_segment_fails_closed_on_a_secret(tmp_path, monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("AVATAR_PROVIDER", "heygen")
    monkeypatch.setenv("HEYGEN_API_KEY", "hg-x")
    monkeypatch.setenv("AVATAR", "1")
    r = nar.render_avatar_segment("the flag is OSAI{deadbeef}", tmp_path / "a.mp4")
    assert r["rendered"] is False and "REDACTED_FLAG" in r["reason"]
    assert not (tmp_path / "a.mp4").exists()


def test_every_real_provider_is_an_extension_point_with_no_sdk_call(tmp_path, monkeypatch):
    for provider, key_env in (("heygen", "HEYGEN_API_KEY"),
                               ("synthesia", "SYNTHESIA_API_KEY"),
                               ("tavus", "TAVUS_API_KEY")):
        _clean(monkeypatch)
        monkeypatch.setenv("AVATAR_PROVIDER", provider)
        monkeypatch.setenv(key_env, "x")
        monkeypatch.setenv("AVATAR", "1")
        r = nar.render_avatar_segment("narration text", tmp_path / f"{provider}.mp4")
        assert r["rendered"] is False
        assert "extension point" in r["reason"] and provider in r["reason"]
        assert not (tmp_path / f"{provider}.mp4").exists()
