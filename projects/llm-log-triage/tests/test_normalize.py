"""Normalization: messy input -> canonical schema, without crashing."""

from src import normalize as n


# --- timestamps ------------------------------------------------------------- #

def test_iso_with_z():
    assert n.parse_timestamp("2026-03-01T12:30:00Z").startswith("2026-03-01T12:30:00")


def test_iso_with_offset():
    out = n.parse_timestamp("2026-03-01T12:30:00+00:00")
    assert out.startswith("2026-03-01T12:30:00")


def test_space_format():
    assert n.parse_timestamp("2026-03-01 12:30:00").startswith("2026-03-01T12:30:00")


def test_slash_format():
    assert n.parse_timestamp("2026/03/01 12:30:00").startswith("2026-03-01T12:30:00")


def test_apache_format():
    assert n.parse_timestamp("01/Mar/2026:12:30:00 +0000").startswith("2026-03-01T12:30:00")


def test_epoch_seconds():
    out = n.parse_timestamp(1772541000)
    assert out is not None and out.startswith("2026-")


def test_epoch_millis():
    out = n.parse_timestamp(1772541000000)
    assert out is not None and out.startswith("2026-")


def test_epoch_as_string():
    assert n.parse_timestamp("1772541000") is not None


def test_unparseable_returns_none():
    assert n.parse_timestamp("not-a-timestamp") is None
    assert n.parse_timestamp(None) is None
    assert n.parse_timestamp("") is None


# --- field aliasing & coercion --------------------------------------------- #

def test_alias_resolution():
    ev = n.normalize_event({"userId": "u1", "sessionId": "s1", "text": "hi", "ts": "2026-03-01T00:00:00Z"})
    assert ev["user_id"] == "u1"
    assert ev["session_id"] == "s1"
    assert ev["content"] == "hi"
    assert ev["ts_utc"] is not None


def test_role_normalization():
    assert n.normalize_event({"role": "Human", "content": "x"})["role"] == "user"
    assert n.normalize_event({"speaker": "AI", "content": "x"})["role"] == "assistant"
    assert n.normalize_event({"author": "FUNCTION", "content": "x"})["role"] == "tool"


def test_source_normalization():
    assert n.normalize_event({"channel": "UI", "content": "x"})["source"] == "chat_ui"
    assert n.normalize_event({"source": "retrieval", "content": "x"})["source"] == "rag"


def test_token_coercion_from_strings():
    ev = n.normalize_event({"prompt_tokens": "120", "completion_tokens": "45.0", "content": "x"})
    assert ev["input_tokens"] == 120
    assert ev["output_tokens"] == 45


def test_event_id_synthesized_when_missing():
    ev = n.normalize_event({"content": "hello", "role": "user"})
    assert ev["event_id"].startswith("synth-")


def test_event_id_is_deterministic():
    rec = {"content": "hello", "role": "user", "user_id": "u9"}
    assert n.normalize_event(dict(rec))["event_id"] == n.normalize_event(dict(rec))["event_id"]


# --- nested content & metadata --------------------------------------------- #

def test_openai_style_content_parts():
    rec = {"role": "user", "content": [{"type": "text", "text": "part one"}, {"type": "text", "text": "part two"}]}
    assert "part one" in n.normalize_event(rec)["content"]
    assert "part two" in n.normalize_event(rec)["content"]


def test_choices_nested_content():
    rec = {"choices": [{"message": {"role": "assistant", "content": "nested answer"}}]}
    assert n.normalize_event(rec)["content"] == "nested answer"


def test_metadata_flattening():
    rec = {"content": "x", "metadata": {"ip": "1.2.3.4", "country": "US", "app": "support-bot"}}
    ev = n.normalize_event(rec)
    assert ev["client_ip"] == "1.2.3.4"
    assert ev["country"] == "US"
    assert ev["app"] == "support-bot"


def test_never_raises_on_garbage():
    for junk in [None, 42, "just a string", [], {"weird": object()}]:
        ev = n.normalize_event(junk)
        assert isinstance(ev["content"], str)
        assert "event_id" in ev


# --- stats ------------------------------------------------------------------ #

def test_normalization_stats():
    raw = [{"content": "x"}, {"ts": "bad", "content": "y", "role": "user"}]
    norm = n.normalize_many(raw)
    stats = n.normalization_stats(raw, norm)
    assert stats["total"] == 2
    assert stats["unparseable_timestamps"] >= 1
    assert stats["synthesized_ids"] == 2
