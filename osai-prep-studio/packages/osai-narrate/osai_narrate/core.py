"""Narrated-lesson renderer — portable, offline-first, provider-agnostic.

A course is **pre-rendered**: an author writes a lesson script; it is rendered to audio
**once**, and the audio + a timing/caption manifest are cached and shipped. The core here —
parse a script, emit a deterministic render **plan / manifest / WebVTT** — needs **no
provider, no key, no network**. A provider only fills in the audio files the manifest lists.

Stdlib-only; **no course-app import** (that is what makes it shareable across projects).

Providers (choose with ``NARRATE_PROVIDER``; render is gated behind ``NARRATE=1``):

  * ``browser`` — Web Speech API in the player; no server render, no key, free.
  * ``cmd``     — **any** local/OSS TTS CLI (Piper, Kokoro, XTTS, …) via ``NARRATE_CMD``
                  (``{out}`` = audio path, ``{voice}`` optional; text on stdin). The default.
  * ``openai`` / ``elevenlabs`` / ``azure`` — cloud neural voices; each needs its own key
                  from the env or a ``*_FILE`` secret (never logged). SDK call is an
                  extension point (no dep is pulled in here).

Env vars accept a course-neutral name **or** the legacy ``OSAI_TTS*`` alias, so existing
OSAI deployments keep working unchanged: ``NARRATE``/``OSAI_TTS`` (toggle),
``NARRATE_PROVIDER``/``OSAI_TTS_PROVIDER``, ``NARRATE_CMD``/``OSAI_TTS_CMD``,
``NARRATE_RATE_<P>``/``OSAI_TTS_RATE_<P>``.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
from pathlib import Path

from . import redaction

__all__ = [
    "DEFAULT_PROVIDER", "DEFAULT_VOICE", "PROVIDERS",
    "provider_name", "provider_kind", "key_present", "key_source", "provider_available",
    "render_enabled", "rate_per_million", "status",
    "parse_script", "cache_key", "render_plan", "to_vtt", "render_segment", "write_manifest",
]

_TRUTHY = {"1", "true", "on", "yes"}

# Approximate one-time render cost, US$ per 1M characters. Planning only — rates change;
# override any via NARRATE_RATE_<PROVIDER>. Local/browser are free.
_DEFAULT_RATES = {"browser": 0.0, "cmd": 0.0, "openai": 15.0, "elevenlabs": 150.0, "azure": 16.0}

# provider -> (kind, key_env). kind: 'client' (in-browser), 'local' (subprocess), 'cloud'.
PROVIDERS = {
    "browser":    ("client", None),
    "cmd":        ("local",  None),
    "openai":     ("cloud",  "OPENAI_API_KEY"),
    "elevenlabs": ("cloud",  "ELEVENLABS_API_KEY"),
    "azure":      ("cloud",  "AZURE_SPEECH_KEY"),
}
DEFAULT_PROVIDER = "cmd"      # free, offline, no lock-in (OSS voices)
DEFAULT_VOICE = "en-GB"       # a British English narrator by default (overridable per script)
_CHARS_PER_SEC = 14.5         # ~ chars/sec of natural narration, for duration estimates


def _env(*names: str, default: str = "") -> str:
    """First non-empty env var among ``names`` (course-neutral name, then OSAI alias)."""
    for n in names:
        v = os.environ.get(n)
        if v is not None and v.strip():
            return v.strip()
    return default


def _truthy_env(*names: str) -> bool:
    return _env(*names).lower() in _TRUTHY


def provider_name() -> str:
    p = _env("NARRATE_PROVIDER", "OSAI_TTS_PROVIDER", default=DEFAULT_PROVIDER).lower()
    return p if p in PROVIDERS else DEFAULT_PROVIDER


def provider_kind(provider: str | None = None) -> str:
    return PROVIDERS[provider or provider_name()][0]


def _key_env(provider: str) -> str | None:
    return PROVIDERS.get(provider, (None, None))[1]


def key_present(provider: str | None = None) -> bool:
    """Presence-only check for a cloud provider's key (env OR ``*_FILE`` secret).
    Never returns, logs, or hashes the value."""
    env = _key_env(provider or provider_name())
    if not env:
        return False
    if os.environ.get(env, "").strip():
        return True
    kf = os.environ.get(env + "_FILE")
    if kf:
        try:
            return bool(Path(kf).read_text(encoding="utf-8-sig").strip())
        except OSError:
            return False
    return False


def key_source(provider: str | None = None) -> str:
    """'env', 'file', 'n/a' (client/local need no key), or 'none'. Never the value."""
    env = _key_env(provider or provider_name())
    if not env:
        return "n/a"
    if os.environ.get(env, "").strip():
        return "env"
    kf = os.environ.get(env + "_FILE")
    if kf and Path(kf).is_file():
        return "file"
    return "none"


def _cmd_template() -> str:
    return _env("NARRATE_CMD", "OSAI_TTS_CMD")


def provider_available(provider: str | None = None) -> bool:
    """client — always; local — iff a render command is configured; cloud — iff key present."""
    provider = provider or provider_name()
    kind = provider_kind(provider)
    if kind == "client":
        return True
    if kind == "local":
        return bool(_cmd_template())
    return key_present(provider)


def render_enabled(provider: str | None = None) -> bool:
    """Server-side rendering is OFF unless opted in (``NARRATE=1``/``OSAI_TTS=1``) AND the
    provider is usable. Keeps the default experience offline and CI green."""
    return _truthy_env("NARRATE", "OSAI_TTS") and provider_available(provider)


def rate_per_million(provider: str | None = None) -> float:
    provider = provider or provider_name()
    override = _env(f"NARRATE_RATE_{provider.upper()}", f"OSAI_TTS_RATE_{provider.upper()}")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    return _DEFAULT_RATES.get(provider, 0.0)


def status(provider: str | None = None) -> dict:
    """A safe, presence-only snapshot — never the key value."""
    provider = provider or provider_name()
    return {
        "provider": provider,
        "kind": provider_kind(provider),
        "key_env": _key_env(provider),
        "key_present": key_present(provider),
        "key_source": key_source(provider),
        "available": provider_available(provider),
        "render_enabled": render_enabled(provider),
        "rate_per_million_usd": rate_per_million(provider),
        "providers": sorted(PROVIDERS),
    }


# --- narration script model ------------------------------------------------- #

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(s: str) -> str:
    return _SLUG.sub("-", (s or "").lower()).strip("-") or "seg"


def parse_script(source, *, lesson_id: str | None = None) -> dict:
    """Normalise a lesson script into ``{lesson_id, title, voice, segments}``.

    Accepts a structured dict (``{"lesson_id","title","voice","segments":[…]}``, where a
    segment is a string or ``{"id","text","slide"?}``) or a plain-text string whose
    blank-line-separated paragraphs each become a segment. Deterministic; every segment
    gets a stable id."""
    if isinstance(source, str):
        data = {"segments": [p.strip() for p in re.split(r"\n\s*\n", source) if p.strip()]}
    else:
        data = dict(source or {})
    lid = data.get("lesson_id") or lesson_id or "lesson"
    voice = data.get("voice") or DEFAULT_VOICE
    segs, seen = [], set()
    for i, raw in enumerate(data.get("segments", []), 1):
        seg = {"text": raw.strip()} if isinstance(raw, str) else dict(raw)
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        sid = seg.get("id") or f"{i:03d}-{_slug(text[:40])}"
        base, n = sid, 2
        while sid in seen:
            sid = f"{base}-{n}"; n += 1
        seen.add(sid)
        out = {"id": sid, "text": text}
        if seg.get("slide"):
            out["slide"] = seg["slide"]
        segs.append(out)
    return {"lesson_id": lid, "title": data.get("title") or lid, "voice": voice, "segments": segs}


def cache_key(text: str, *, provider: str, voice: str) -> str:
    """Deterministic content hash → the audio filename. Re-render only fires when text,
    voice, or provider changes (idempotent)."""
    h = hashlib.sha256(f"{provider}\x1f{voice}\x1f{text}".encode("utf-8")).hexdigest()
    return h[:16]


def _fmt(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def render_plan(script, *, provider: str | None = None, ext: str = "mp3") -> dict:
    """Everything needed to render a lesson, computed with NO provider/key/network: per
    segment its caption text, ``start``/``end`` timings, estimated duration, and cache-keyed
    output path; plus totals and a one-time cost estimate. The player and a batch renderer
    both consume this."""
    sc = parse_script(script)
    provider = provider or provider_name()
    voice = sc["voice"]
    segs, total_chars, cursor = [], 0, 0.0
    for seg in sc["segments"]:
        chars = len(seg["text"])
        secs = chars / _CHARS_PER_SEC
        key = cache_key(seg["text"], provider=provider, voice=voice)
        segs.append({
            "id": seg["id"], "text": seg["text"], "chars": chars,
            "start": round(cursor, 2), "end": round(cursor + secs, 2),
            "est_seconds": round(secs, 1),
            "audio": f"{sc['lesson_id']}/{seg['id']}.{key}.{ext}",
            **({"slide": seg["slide"]} if "slide" in seg else {}),
        })
        total_chars += chars
        cursor += secs
    rate = rate_per_million(provider)
    return {
        "lesson_id": sc["lesson_id"], "title": sc["title"], "voice": voice,
        "provider": provider, "kind": provider_kind(provider),
        "segments": segs, "segment_count": len(segs),
        "total_chars": total_chars,
        "est_duration": _fmt(cursor), "est_seconds": round(cursor, 1),
        "est_cost_usd": round(total_chars / 1_000_000 * rate, 4),
        "rate_per_million_usd": rate,
    }


def to_vtt(plan: dict) -> str:
    """WebVTT captions from a render plan — synced subtitles + accessible transcript."""
    def ts(s: float) -> str:
        h, rem = divmod(float(s), 3600)
        m, sec = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}"
    lines = ["WEBVTT", ""]
    for s in plan["segments"]:
        lines += [s["id"], f"{ts(s['start'])} --> {ts(s['end'])}", s["text"], ""]
    return "\n".join(lines)


def render_segment(text: str, out_path, *, provider: str | None = None, voice: str | None = None):
    """Render one segment to ``out_path`` — **gated and fail-closed**. Writes nothing (no
    network/subprocess) when the seam is off or any flag/secret/PII survives redaction. Only
    the local ``cmd`` path is wired; a cloud provider is a documented extension point."""
    provider = provider or provider_name()
    voice = voice or DEFAULT_VOICE
    if not render_enabled(provider):
        return {"rendered": False,
                "reason": f"render disabled — set NARRATE=1 and configure provider '{provider}'"}
    leaks = redaction.residual_secrets(text)
    if leaks:
        return {"rendered": False, "reason": f"blocked: content still carries {leaks} after redaction"}
    if provider_kind(provider) == "cloud":
        return {"rendered": False,
                "reason": f"cloud provider '{provider}' render is an extension point — wire its SDK, "
                          "or use NARRATE_PROVIDER=cmd with a local TTS CLI"}
    if provider == "browser":
        return {"rendered": False, "reason": "browser provider renders client-side in the lesson player"}
    tmpl = _cmd_template()
    if not tmpl:
        return {"rendered": False, "reason": "no NARRATE_CMD configured for the local 'cmd' provider"}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [a.replace("{out}", str(out_path)).replace("{voice}", voice) for a in shlex.split(tmpl)]
    import subprocess  # local import: never reached on the default offline path
    try:
        subprocess.run(cmd, input=redaction.redact_text(text).encode("utf-8"),
                       check=True, capture_output=True, timeout=120)
    except Exception as exc:  # pragma: no cover - depends on the local binary
        return {"rendered": False, "reason": f"local render failed: {exc}"}
    return {"rendered": True, "path": str(out_path), "provider": provider, "voice": voice}


def write_manifest(script, out_dir, *, provider: str | None = None) -> dict:
    """Write ``<out_dir>/<lesson_id>.manifest.json`` + ``<lesson_id>.vtt`` and return the
    plan. Both ship even with no provider — the player uses them for timing + captions, and
    a batch renderer fills in the audio the manifest lists."""
    import json
    plan = render_plan(script, provider=provider)
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{plan['lesson_id']}.manifest.json"
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    vtt = base / f"{plan['lesson_id']}.vtt"
    vtt.write_text(to_vtt(plan), encoding="utf-8")
    return {"manifest": str(out), "captions": str(vtt), "plan": plan}
