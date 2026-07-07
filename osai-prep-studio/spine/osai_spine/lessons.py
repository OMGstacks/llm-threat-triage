"""Course-side lesson catalog + build-all (PR32).

Turns the authored lesson scripts in ``lessons/*.json`` into the web player's committed
static artifacts — a per-lesson render manifest + WebVTT — plus a single ``index.json``
catalog that the ``/lessons`` index page lists.

This lives in the COURSE (``osai_spine``), **not** in the shared ``osai-narrate`` package,
because it knows OSAI-specific frontmatter (track / module / frameworks) and where the web
app keeps its static lessons. The package stays the neutral render seam — here we only call
its ``render_plan`` / ``to_vtt`` / ``write_manifest`` (via the thin ``narration`` adapter).

Everything is deterministic and offline: no provider, no key, no network, no audio. Audio is
the gated seam; captions + timing always ship so the player works with no provider at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import narration as nar  # thin adapter over the shared osai-narrate package

_HERE = Path(__file__).resolve().parent
LESSONS_DIR = _HERE.parent / "lessons"
WEB_LESSONS_DIR = _HERE.parents[1] / "web" / "public" / "lessons"

# Module -> track fallback, used only for a lesson whose id lacks a ``T<n>-`` prefix
# (the L03 pilot predates the T<track>-L<nn> naming standard in 12-content-authoring.md).
_MODULE_TRACK = {"M1": 2, "M2": 3, "M3": 3, "M5": 3, "M4": 4, "M6": 4, "M7": 4,
                 "M8": 5, "M9": 5, "M10": 6, "M11": 6}


def load_scripts(lessons_dir: Path | str = LESSONS_DIR) -> list:
    """Every lesson script (``lessons/*.json``), parsed, in filename order."""
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(Path(lessons_dir).glob("*.json"))]


def _track_of(script: dict) -> int:
    """The lesson's track for ordering: declared ``track``, else the ``T<n>-`` id prefix,
    else the module->track fallback, else 99 (unknown sorts last)."""
    if script.get("track") is not None:
        return int(script["track"])
    lid = script.get("lesson_id", "")
    if lid[:1] == "T" and "-" in lid:
        try:
            return int(lid.split("-", 1)[0][1:])
        except ValueError:
            pass
    return _MODULE_TRACK.get(script.get("module"), 99)


def _frameworks_of(script: dict) -> list:
    """All framework ids the lesson declares — the ``frameworks`` list plus a legacy single
    ``owasp`` field (the L03 pilot), de-duplicated, order preserved."""
    fw = list(script.get("frameworks", []))
    owasp = script.get("owasp")
    if owasp and owasp not in fw:
        fw.append(owasp)
    return fw


def card(script: dict) -> dict:
    """A compact, deterministic catalog entry for the ``/lessons`` index: the generic render
    summary (from the shared package) plus the course's own taxonomy frontmatter."""
    plan = nar.render_plan(script)
    return {
        "lesson_id": plan["lesson_id"],
        "title": plan["title"],
        "track": _track_of(script),
        "module": script.get("module"),
        "frameworks": _frameworks_of(script),
        "detector": script.get("detector"),
        "segment_count": plan["segment_count"],
        "est_duration": plan["est_duration"],
        "est_seconds": plan["est_seconds"],
    }


def catalog(lessons_dir: Path | str = LESSONS_DIR) -> dict:
    """The full lessons index — one card per script, ordered by ``(track, lesson_id)``.
    Deterministic, so it can be committed and drift-tested against the scripts."""
    cards = [card(s) for s in load_scripts(lessons_dir)]
    cards.sort(key=lambda c: (c["track"], c["lesson_id"]))
    return {"lessons": cards, "count": len(cards)}


def _write(path: Path, text: str) -> None:
    """Write text with a trailing newline, matching the artifacts the pilot committed so a
    rebuild is byte-stable for git (POSIX-friendly final newline)."""
    path.write_text(text + "\n", encoding="utf-8")


def build_all(lessons_dir: Path | str = LESSONS_DIR, web_dir: Path | str = WEB_LESSONS_DIR) -> dict:
    """Render every lesson's manifest + VTT into the web app's static lessons dir and write
    the ``index.json`` catalog. Never renders audio (that is the gated seam) — captions +
    timing always ship so the player works with no provider. Deterministic and idempotent:
    re-running on unchanged scripts rewrites byte-identical files. Returns a summary.

    Files are written here (not via the package's ``write_manifest``) so the course controls
    formatting — every artifact is newline-terminated — while the shared package stays the
    neutral render seam (``render_plan`` / ``to_vtt``)."""
    web = Path(web_dir)
    web.mkdir(parents=True, exist_ok=True)
    built = []
    for script in load_scripts(lessons_dir):
        plan = nar.render_plan(script)
        lid = plan["lesson_id"]
        _write(web / f"{lid}.manifest.json", json.dumps(plan, indent=2))
        _write(web / f"{lid}.vtt", nar.to_vtt(plan))
        built.append(lid)
    _write(web / "index.json", json.dumps(catalog(lessons_dir), indent=2))
    return {"lessons": built, "count": len(built), "index": str(web / "index.json"),
            "web_dir": str(web)}
