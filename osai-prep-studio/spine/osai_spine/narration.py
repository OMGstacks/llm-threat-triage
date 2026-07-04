"""Narration (text-to-speech) seam — the plumbing for the fully-narrated lesson
experience (27-narrated-lessons.md).

**Optional, offline-first, provider-agnostic — exactly like the LLM seam (``llm.py``).**
The platform runs fully without it: with no provider configured the seam only *plans*
a render (segments, timing, cost, cache keys) and the web lesson-player falls back to
the browser's built-in voice. CI is green with no key, no binary, and no network.

Narration for a *course* is **pre-rendered**: an author writes a lesson script, the
script is rendered to audio **once**, and the audio + a timing manifest are cached and
shipped. So this seam's core — parsing a script and producing a deterministic render
**plan/manifest** — needs no provider at all; a provider only fills in the audio files.

Providers (swap with ``OSAI_TTS_PROVIDER``; render is gated behind ``OSAI_TTS=1``):

  * ``browser`` — Web Speech API in the player; no server render, no key, free.
  * ``cmd``     — **any** local/OSS TTS CLI (Piper, Kokoro, XTTS, …) via a command
                  template ``OSAI_TTS_CMD`` (``{text}`` on stdin, ``{out}`` = audio path).
                  Free, offline, no vendor lock-in — the recommended default.
  * ``openai`` / ``elevenlabs`` / ``azure`` — cloud neural voices. Each needs its own
                  key, read from the env **or** a ``*_FILE`` secret (Docker/K8s), and its
                  value is never logged. The SDK call is a documented extension point.

Keys are read from the environment ONLY — never hardcoded, never logged. Because a
cloud render is egress, script text is scrubbed (``llm.residual_secrets``) and the seam
**fails closed** if any flag/secret/PII survives.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
from pathlib import Path

from . import llm  # reuse the vetted redaction / residual-secret tripwire

_TRUTHY = {"1", "true", "on", "yes"}

# Approximate one-time render cost, US$ per 1M characters. For *planning only* — rates
# change; override any via OSAI_TTS_RATE_<PROVIDER>. Local/browser are free.
_DEFAULT_RATES = {"browser": 0.0, "cmd": 0.0, "openai": 15.0, "elevenlabs": 150.0, "azure": 16.0}

# provider -> (kind, key_env). kind: 'client' (in-browser), 'local' (subprocess), 'cloud'.
_PROVIDERS = {
    "browser":    ("client", None),
    "cmd":        ("local",  None),
    "openai":     ("cloud",  "OPENAI_API_KEY"),
    "elevenlabs": ("cloud",  "ELEVENLABS_API_KEY"),
    "azure":      ("cloud",  "AZURE_SPEECH_KEY"),
}
DEFAULT_PROVIDER = "cmd"      # the free, offline, no-lock-in OSS path (per the plan)
DEFAULT_VOICE = "en-GB"       # a British English narrator by default (overridable per script)

# ~ characters per second of speech at a natural narration pace — for duration estimates.
_CHARS_PER_SEC = 14.5


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def provider_name() -> str:
    p = os.environ.get("OSAI_TTS_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    return p if p in _PROVIDERS else DEFAULT_PROVIDER


def provider_kind(provider: str | None = None) -> str:
    return _PROVIDERS[provider or provider_name()][0]


def _key_env(provider: str) -> str | None:
    return _PROVIDERS.get(provider, (None, None))[1]


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


def provider_available(provider: str | None = None) -> bool:
    """Can this provider actually render right now?
      * client  — always (the browser does it);
      * local   — iff a render command template is configured (``OSAI_TTS_CMD``);
      * cloud   — iff its key is present.
    """
    provider = provider or provider_name()
    kind = provider_kind(provider)
    if kind == "client":
        return True
    if kind == "local":
        return bool(os.environ.get("OSAI_TTS_CMD", "").strip())
    return key_present(provider)


def render_enabled(provider: str | None = None) -> bool:
    """Server-side rendering is OFF unless explicitly opted in (``OSAI_TTS=1``) AND the
    provider is actually usable. Keeps the default experience offline and CI green."""
    return _truthy("OSAI_TTS") and provider_available(provider)


def rate_per_million(provider: str | None = None) -> float:
    provider = provider or provider_name()
    override = os.environ.get("OSAI_TTS_RATE_" + provider.upper())
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    return _DEFAULT_RATES.get(provider, 0.0)


def status(provider: str | None = None) -> dict:
    """A safe, presence-only snapshot of the seam — never the key value."""
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
        "providers": sorted(_PROVIDERS),
    }


# --- narration script model ------------------------------------------------- #

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(s: str) -> str:
    return _SLUG.sub("-", (s or "").lower()).strip("-") or "seg"


def parse_script(source, *, lesson_id: str | None = None) -> dict:
    """Normalise a lesson narration script into ``{lesson_id, title, voice, segments}``.

    Accepts either a structured dict (``{"lesson_id","title","voice","segments":[…]}``,
    where a segment is a string or ``{"id","text","slide"?}``) or a plain-text string
    whose blank-line-separated paragraphs each become a segment. Deterministic; the
    author writes prose, the seam gives every segment a stable id."""
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
        while sid in seen:          # ids are globally-unique within a lesson
            sid = f"{base}-{n}"; n += 1
        seen.add(sid)
        out = {"id": sid, "text": text}
        if seg.get("slide"):
            out["slide"] = seg["slide"]
        segs.append(out)
    return {"lesson_id": lid, "title": data.get("title") or lid, "voice": voice, "segments": segs}


def cache_key(text: str, *, provider: str, voice: str) -> str:
    """Deterministic content hash → the audio filename. Re-render only fires when the
    text, voice, or provider changes (idempotent, like the fact-store fingerprints)."""
    h = hashlib.sha256(f"{provider}\x1f{voice}\x1f{text}".encode("utf-8")).hexdigest()
    return h[:16]


def _fmt(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def render_plan(script, *, provider: str | None = None, ext: str = "mp3") -> dict:
    """Everything needed to render a lesson — computed with NO provider, NO key, NO
    network. Per segment: char count, estimated duration, cache-keyed output file. Plus
    totals and a one-time cost estimate for the chosen provider. This is the plumbing
    the web player and a batch renderer both consume."""
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
    total_secs = cursor
    rate = rate_per_million(provider)
    return {
        "lesson_id": sc["lesson_id"], "title": sc["title"], "voice": voice,
        "provider": provider, "kind": provider_kind(provider),
        "segments": segs, "segment_count": len(segs),
        "total_chars": total_chars,
        "est_duration": _fmt(total_secs), "est_seconds": round(total_secs, 1),
        "est_cost_usd": round(total_chars / 1_000_000 * rate, 4),
        "rate_per_million_usd": rate,
    }


def to_vtt(plan: dict) -> str:
    """WebVTT captions from a render plan — the player renders these as synced subtitles,
    and they double as the accessible transcript. Timings are the estimated segment
    boundaries; a renderer can refine them to the real audio durations."""
    def ts(s: float) -> str:
        h, rem = divmod(float(s), 3600)
        m, sec = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}"
    lines = ["WEBVTT", ""]
    for s in plan["segments"]:
        lines += [s["id"], f"{ts(s['start'])} --> {ts(s['end'])}", s["text"], ""]
    return "\n".join(lines)


def render_segment(text: str, out_path, *, provider: str | None = None, voice: str | None = None):
    """Render one segment to ``out_path`` — **gated and fail-closed**.

    Returns ``{"rendered": bool, "path"|"reason": …}``. If the seam is not enabled, or a
    flag/secret/PII survives redaction (a cloud render is egress), NOTHING is written and
    no network/subprocess is touched. Only the ``cmd`` (local OSS) path is wired here; a
    cloud provider is a documented extension point so no SDK/dep is pulled in."""
    provider = provider or provider_name()
    voice = voice or DEFAULT_VOICE
    if not render_enabled(provider):
        return {"rendered": False,
                "reason": f"render disabled — set OSAI_TTS=1 and configure provider '{provider}'"}
    leaks = llm.residual_secrets(text)               # defense-in-depth tripwire
    if leaks:
        return {"rendered": False, "reason": f"blocked: content still carries {leaks} after redaction"}
    if provider_kind(provider) == "cloud":
        return {"rendered": False,
                "reason": f"cloud provider '{provider}' render is an extension point — wire its SDK, "
                          "or use OSAI_TTS_PROVIDER=cmd with a local TTS CLI"}
    if provider == "browser":
        return {"rendered": False, "reason": "browser provider renders client-side in the lesson player"}
    # provider == 'cmd': run the configured local TTS CLI, text on stdin, {out} = file.
    tmpl = os.environ.get("OSAI_TTS_CMD", "").strip()
    if not tmpl:
        return {"rendered": False, "reason": "no OSAI_TTS_CMD configured for the local 'cmd' provider"}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [a.replace("{out}", str(out_path)).replace("{voice}", voice) for a in shlex.split(tmpl)]
    import subprocess  # local import: never reached in the default offline path
    try:
        subprocess.run(cmd, input=llm.redact_text(text).encode("utf-8"),
                       check=True, capture_output=True, timeout=120)
    except Exception as exc:  # pragma: no cover - depends on the local binary
        return {"rendered": False, "reason": f"local render failed: {exc}"}
    return {"rendered": True, "path": str(out_path), "provider": provider, "voice": voice}


def write_manifest(script, out_dir, *, provider: str | None = None) -> dict:
    """Write the lesson's render plan to ``<out_dir>/<lesson_id>.manifest.json`` and
    return it. The manifest ships even with no provider — the player uses it for segment
    timing and captions, and a batch renderer fills in the audio files listed in it."""
    import json
    plan = render_plan(script, provider=provider)
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{plan['lesson_id']}.manifest.json"
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    vtt = base / f"{plan['lesson_id']}.vtt"                 # captions ship next to the manifest
    vtt.write_text(to_vtt(plan), encoding="utf-8")
    return {"manifest": str(out), "captions": str(vtt), "plan": plan}
