"""Normalize messy raw LLM logs into a single canonical event schema.

Real-world logs are *messy*: timestamps in five formats, fields that are
sometimes missing or misnamed, nested metadata, role labels in mixed case,
booleans as strings. A Technical Intelligence Analyst spends a surprising
fraction of their time here — you cannot hunt a signal you cannot parse.

The canonical event (the contract every other module relies on):

    {
        "event_id":      str,           # stable id; synthesized if absent
        "ts_raw":        str | None,    # original timestamp, verbatim
        "ts_utc":        str | None,    # ISO-8601 UTC, or None if unparseable
        "session_id":    str | None,
        "user_id":       str | None,
        "model":         str | None,
        "source":        str | None,    # api | chat_ui | rag | tool | plugin | ...
        "role":          str | None,    # user | assistant | system | tool
        "content":       str,           # always a string ("" if missing)
        "input_tokens":  int | None,
        "output_tokens": int | None,
        "latency_ms":    int | None,
        "client_ip":     str | None,
        "country":       str | None,
        "app":           str | None,
        "raw_json":      str,           # original record, for forensics
    }
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

# Field aliases seen across producers. First present wins.
_ALIASES = {
    "event_id": ("event_id", "id", "eventId", "uuid", "request_id", "requestId"),
    "timestamp": ("timestamp", "ts", "time", "@timestamp", "created", "created_at", "datetime"),
    "session_id": ("session_id", "sessionId", "session", "conversation_id", "conversationId", "thread_id"),
    "user_id": ("user_id", "userId", "user", "uid", "account_id", "actor"),
    "model": ("model", "model_name", "engine", "deployment"),
    "source": ("source", "channel", "origin", "surface", "interface"),
    "role": ("role", "speaker", "author", "from"),
    "content": ("content", "text", "message", "msg", "body", "prompt", "completion", "input", "output"),
    "input_tokens": ("input_tokens", "prompt_tokens", "inputTokens", "tokens_in"),
    "output_tokens": ("output_tokens", "completion_tokens", "outputTokens", "tokens_out"),
    "latency_ms": ("latency_ms", "latency", "duration_ms", "elapsed_ms", "response_time_ms"),
}

# Role normalization.
_ROLE_MAP = {
    "user": "user", "human": "user", "end_user": "user", "customer": "user",
    "assistant": "assistant", "ai": "assistant", "bot": "assistant",
    "model": "assistant", "completion": "assistant", "gpt": "assistant",
    "system": "system", "developer": "system",
    "tool": "tool", "function": "tool", "tool_result": "tool", "retrieval": "tool",
}

# Source normalization.
_SOURCE_MAP = {
    "api": "api", "rest": "api", "v1": "api",
    "chat": "chat_ui", "chat_ui": "chat_ui", "ui": "chat_ui", "web": "chat_ui", "webapp": "chat_ui",
    "rag": "rag", "retrieval": "rag", "vector": "rag", "kb": "rag", "knowledge_base": "rag",
    "tool": "tool", "function": "tool", "tool_output": "tool",
    "plugin": "plugin", "extension": "plugin",
    "document": "document", "file": "document", "upload": "document",
    "email": "email", "mail": "email",
}

_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",   # apache-style
    "%m/%d/%Y %H:%M",         # US slash, minute precision
)


def _first(record: dict, keys: tuple) -> Optional[Any]:
    for k in keys:
        if k in record and record[k] not in (None, ""):
            return record[k]
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _epoch_to_iso(num: float) -> Optional[str]:
    """Convert a numeric epoch to ISO-8601 UTC, picking the unit by magnitude.

    Bands are anchored to plausible modern dates so a non-epoch number (a
    compact date like 20260301, or a numeric id) falls OUTSIDE every band and
    returns ``None`` instead of being fabricated into a 1970-era timestamp.
        seconds       ~1e8  (1973) .. 1e11 (5138)
        milliseconds  ~1e11 .. 1e14
        microseconds  ~1e14 .. 1e17
    """
    if 1e8 <= num < 1e11:
        secs = num
    elif 1e11 <= num < 1e14:
        secs = num / 1e3
    elif 1e14 <= num < 1e17:
        secs = num / 1e6
    else:
        return None
    try:
        return datetime.fromtimestamp(secs, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def parse_timestamp(value: Any) -> Optional[str]:
    """Best-effort parse of a messy timestamp into ISO-8601 UTC.

    Handles epoch seconds/millis/micros (int or numeric string) and a battery of
    string formats. Returns ``None`` if nothing parses, so downstream code can
    decide how to treat unparseable events instead of crashing. Critically, a
    numeric value is only treated as an epoch when it is in a plausible epoch
    range — so "20260301" or a numeric request id is NOT silently converted to a
    1970 date.
    """
    if value is None or value == "":
        return None

    # Numeric epoch from a real number (guard against bool, an int subclass).
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _epoch_to_iso(float(value))

    if not isinstance(value, str):
        return None

    # Numeric string: only an epoch if it is an epoch-plausible length.
    digits = value.strip().lstrip("-")
    if digits.isdigit() and len(digits) in (10, 13, 16):
        iso = _epoch_to_iso(float(value.strip()))
        if iso:
            return iso
        # otherwise fall through to the string-format parsers

    text = value.strip()
    # Python's fromisoformat handles most ISO variants (incl. "Z" in 3.11).
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass

    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _structural_content(record: dict) -> Optional[Any]:
    """Pull content from OpenAI-style nesting: message.content / choices[].message."""
    msg = record.get("message") or {}
    if isinstance(msg, dict) and msg.get("content") is not None:
        return msg.get("content")
    choices = record.get("choices")
    if isinstance(choices, list) and choices:
        inner = choices[0]
        if isinstance(inner, dict):
            return (inner.get("message") or {}).get("content") or inner.get("text")
    return None


def _extract_content(record: dict, raw_value: Any) -> str:
    """Content can be a string, a list of message parts, or a nested dict.

    Structural OpenAI-style content (message.content / choices) is preferred when
    the resolved alias is absent or merely a bare scalar (e.g. ``input: 0``), so
    a generic scalar alias never shadows the richer nested payload.
    """
    val = raw_value
    if val is None or isinstance(val, (int, float, bool)):
        structural = _structural_content(record)
        if structural is not None:
            val = structural
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        # OpenAI-style content parts: [{"type":"text","text":"..."}].
        parts = []
        for p in val:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                parts.append(str(p.get("text") or p.get("content") or ""))
        return " ".join(x for x in parts if x)
    if isinstance(val, dict):
        return str(val.get("text") or val.get("content") or json.dumps(val, ensure_ascii=False))
    return str(val)


def _flatten_metadata(record: dict) -> dict:
    """Pull client_ip / country / app out of a possibly-nested metadata blob."""
    meta = record.get("metadata") or record.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    merged = {**meta, **record}  # top-level wins over nested

    def grab(*keys):
        for k in keys:
            if merged.get(k) not in (None, ""):
                return str(merged[k])
        return None

    return {
        "client_ip": grab("client_ip", "ip", "ip_address", "remote_addr", "source_ip"),
        # Only true country fields — a region/geo string ("us-east-1") is not a country.
        "country": grab("country", "country_code"),
        "app": grab("app", "application", "client", "app_name", "service"),
    }


def _synth_event_id(record: dict) -> str:
    """Deterministic id for records that arrive without one."""
    blob = json.dumps(record, sort_keys=True, default=str, ensure_ascii=False)
    return "synth-" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def normalize_event(record: dict) -> dict:
    """Map one raw record onto the canonical schema. Never raises on bad input."""
    if not isinstance(record, dict):
        record = {"content": str(record)}

    raw_role = _first(record, _ALIASES["role"])
    role = _ROLE_MAP.get(str(raw_role).strip().lower(), None) if raw_role else None

    raw_source = _first(record, _ALIASES["source"])
    source = _SOURCE_MAP.get(str(raw_source).strip().lower(), None) if raw_source else None
    if source is None and raw_source:
        source = str(raw_source).strip().lower()

    ts_raw = _first(record, _ALIASES["timestamp"])
    event_id = _first(record, _ALIASES["event_id"]) or _synth_event_id(record)

    # Compute each alias lookup once.
    sid = _first(record, _ALIASES["session_id"])
    uid = _first(record, _ALIASES["user_id"])
    model = _first(record, _ALIASES["model"])
    content_raw = _first(record, _ALIASES["content"])

    meta = _flatten_metadata(record)

    return {
        "event_id": str(event_id),
        "ts_raw": str(ts_raw) if ts_raw is not None else None,
        "ts_utc": parse_timestamp(ts_raw),
        "session_id": str(sid) if sid else None,
        "user_id": str(uid) if uid else None,
        "model": str(model) if model else None,
        "source": source,
        "role": role,
        "content": _extract_content(record, content_raw),
        "input_tokens": _coerce_int(_first(record, _ALIASES["input_tokens"])),
        "output_tokens": _coerce_int(_first(record, _ALIASES["output_tokens"])),
        "latency_ms": _coerce_int(_first(record, _ALIASES["latency_ms"])),
        "client_ip": meta["client_ip"],
        "country": meta["country"],
        "app": meta["app"],
        "raw_json": json.dumps(record, ensure_ascii=False, default=str),
    }


def normalize_many(records: Iterable[dict]) -> list[dict]:
    return [normalize_event(r) for r in records]


def normalization_stats(raw: list[dict], normalized: list[dict]) -> dict:
    """Quick data-quality summary — the kind of thing you cite in a writeup."""
    n = len(normalized)
    return {
        "total": n,
        "unparseable_timestamps": sum(1 for e in normalized if e["ts_utc"] is None),
        "missing_role": sum(1 for e in normalized if e["role"] is None),
        "missing_source": sum(1 for e in normalized if e["source"] is None),
        "missing_user": sum(1 for e in normalized if e["user_id"] is None),
        "synthesized_ids": sum(1 for e in normalized if e["event_id"].startswith("synth-")),
        "empty_content": sum(1 for e in normalized if not e["content"]),
    }
