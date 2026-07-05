"""Package acceptance — the renderer works standalone, with NO course-app dependency.

Run from the package (``pytest``); the package must import and render a generic, non-OSAI
lesson, emit a manifest + WebVTT, and keep the redaction tripwire, all off by default.
"""

import json
import sys

import osai_narrate as nar
from osai_narrate import redaction

CC = {  # a lesson with nothing to do with OSAI — proves the package is course-neutral
    "lesson_id": "CC01", "title": "Certified in Cybersecurity — Security Principles",
    "voice": "en-GB",
    "segments": [
        {"text": "Welcome to the CC course. This lesson covers the CIA triad.", "slide": "intro"},
        {"text": "Confidentiality, integrity, and availability are the three core goals.", "slide": "cia"},
        "Least privilege means giving each identity only the access its job requires.",
    ],
}


def test_no_course_app_import():
    assert "osai_spine" not in sys.modules  # the package pulls in no course app


def test_off_by_default():
    assert nar.render_enabled() is False
    assert nar.status()["provider"] == "cmd"


def test_renders_a_generic_lesson_plan():
    plan = nar.render_plan(CC)
    assert plan["lesson_id"] == "CC01" and plan["segment_count"] == 3
    for s in plan["segments"]:
        assert s["id"] and s["text"] and s["end"] > s["start"] >= 0
        assert s["audio"].startswith("CC01/") and s["audio"].endswith(".mp3")


def test_deterministic():
    assert nar.render_plan(CC) == nar.render_plan(CC)


def test_webvtt_and_manifest(tmp_path):
    res = nar.write_manifest(CC, tmp_path)
    manifest = json.loads((tmp_path / "CC01.manifest.json").read_text())
    assert manifest["segment_count"] == 3
    vtt = (tmp_path / "CC01.vtt").read_text()
    assert vtt.startswith("WEBVTT") and vtt.count("-->") == 3 and "CIA triad" in vtt


def test_redaction_tripwire_present():
    assert redaction.residual_secrets("token OSAI{deadbeef}") == ["REDACTED_FLAG"]
    assert redaction.residual_secrets("email a@b.com") == ["REDACTED_EMAIL"]
    assert redaction.residual_secrets("plain narration text") == []


def test_render_fails_closed_on_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("NARRATE", "1")
    monkeypatch.setenv("NARRATE_CMD", "cat")
    r = nar.render_segment("the flag is OSAI{x}", tmp_path / "a.mp3")
    assert r["rendered"] is False and "REDACTED_FLAG" in r["reason"]
    assert not (tmp_path / "a.mp3").exists()


def test_neutral_and_legacy_env_both_work(monkeypatch):
    monkeypatch.setenv("OSAI_TTS_PROVIDER", "openai")     # legacy OSAI alias …
    assert nar.provider_name() == "openai"
    monkeypatch.setenv("NARRATE_PROVIDER", "azure")       # … neutral name wins
    assert nar.provider_name() == "azure"
