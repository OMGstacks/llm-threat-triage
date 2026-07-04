"""PR29 — prove the narration seam with one REAL lesson end-to-end (27-narrated-lessons.md).

Renders the shipped ``lessons/L03.json`` through the offline/local seam: the script parses,
the plan is deterministic, the manifest carries ids / durations / captions / cache keys /
output paths, a mocked local ``cmd`` provider writes audio for every segment, captions
export as valid WebVTT, and a secret in a script is blocked. No network, no keys, no cloud.
"""

import json
import sys
from pathlib import Path

import pytest

from osai_spine import narration as nar

LESSON = Path(__file__).resolve().parents[1] / "lessons" / "L03.json"

# A hermetic stand-in for a local TTS binary: copy the narration text (stdin) to {out}.
MOCK_TTS = f'{sys.executable} -c "import sys;open(\'{{out}}\',\'wb\').write(sys.stdin.buffer.read())"'


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("OSAI_TTS", "OSAI_TTS_PROVIDER", "OSAI_TTS_CMD"):
        monkeypatch.delenv(k, raising=False)


def _script():
    return json.loads(LESSON.read_text(encoding="utf-8"))


def test_real_lesson_parses():
    sc = nar.parse_script(_script())
    assert sc["lesson_id"] == "L03" and sc["segments"]
    assert all(s["id"] and s["text"] for s in sc["segments"])
    assert all("slide" in s for s in sc["segments"])          # this lesson cues a slide per segment


def test_plan_is_deterministic():
    assert nar.render_plan(_script()) == nar.render_plan(_script())


def test_manifest_has_every_required_field():
    plan = nar.render_plan(_script())
    assert plan["segment_count"] >= 8
    prev_end = 0.0
    for s in plan["segments"]:
        assert s["id"] and s["text"]                          # id + caption
        assert s["audio"].startswith("L03/") and s["audio"].endswith(".mp3")   # output path
        assert len(s["audio"].split(".")[-2]) == 16           # 16-hex cache key
        assert s["end"] > s["start"] >= 0 and s["est_seconds"] > 0   # duration
        assert s["start"] == pytest.approx(prev_end)          # segments are contiguous
        prev_end = s["end"]
    assert ":" in plan["est_duration"] and plan["est_cost_usd"] == 0.0


def test_captions_export_as_webvtt():
    vtt = nar.to_vtt(nar.render_plan(_script()))
    assert vtt.startswith("WEBVTT")
    assert vtt.count("-->") == nar.render_plan(_script())["segment_count"]   # one cue per segment
    assert "OWASP LLM01" in vtt                               # the real caption text is present


def test_write_manifest_emits_manifest_and_captions(tmp_path):
    res = nar.write_manifest(_script(), tmp_path)
    assert Path(res["manifest"]).exists() and Path(res["captions"]).exists()
    assert Path(res["captions"]).suffix == ".vtt"


def test_full_local_render_writes_all_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("OSAI_TTS", "1")
    monkeypatch.setenv("OSAI_TTS_CMD", MOCK_TTS)
    assert nar.render_enabled() is True
    res = nar.write_manifest(_script(), tmp_path)
    sc = nar.parse_script(_script())
    rendered = 0
    for planseg, seg in zip(res["plan"]["segments"], sc["segments"]):
        r = nar.render_segment(seg["text"], tmp_path / planseg["audio"], voice=res["plan"]["voice"])
        assert r["rendered"] is True
        out = tmp_path / planseg["audio"]
        assert out.exists() and out.read_text(encoding="utf-8") == seg["text"]
        rendered += 1
    assert rendered == res["plan"]["segment_count"]           # every segment produced audio


def test_lesson_render_fails_closed_on_a_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("OSAI_TTS", "1")
    monkeypatch.setenv("OSAI_TTS_CMD", MOCK_TTS)
    r = nar.render_segment("the lab flag is OSAI{deadbeef}", tmp_path / "x.mp3")
    assert r["rendered"] is False and "REDACTED_FLAG" in r["reason"]
    assert not (tmp_path / "x.mp3").exists()


def test_shipped_lesson_has_no_secret_material():
    # authored content must never carry a flag/secret/PII (defense-in-depth on our own file)
    from osai_spine import llm
    assert llm.residual_secrets(_script()) == []
