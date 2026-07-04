"""Portability proof, run from the OSAI spine suite: the shared ``osai-narrate`` package
has **no OSAI-specific coupling**.

The check that matters can't run in-process — ``conftest.py`` already put the spine dir on
``sys.path`` for every other test, so ``osai_spine`` is importable here. To prove the
package stands alone we spawn a **fresh, site-less interpreter** (``python -S``) whose path
contains *only* the package (``PYTHONPATH`` = the package dir, ``cwd`` = a neutral tmp dir).
``-S`` is what makes the isolation honest: this repo pip-installs the spine **editable**, so
its ``.pth`` finder is registered in site-packages and ``osai_spine`` would otherwise resolve
from *any* interpreter no matter the path. Skipping site init drops that finder, leaving a
truly course-free interpreter (the package is stdlib-only, so ``-S`` costs it nothing).

Inside the child: import ``osai_narrate`` with no course app present, render a **generic,
non-OSAI** lesson, emit a manifest + WebVTT, and confirm the redaction tripwire still fires.
If the package had smuggled in a course import, the subprocess would fail to import and this
test would go red.

This complements the package's own ``tests/test_portability.py`` (which runs from the
package): here we assert portability *from the consuming course's* test run, which is where
drift would actually bite.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PKG = (Path(__file__).resolve().parents[2] / "packages" / "osai-narrate").resolve()

pytestmark = pytest.mark.skipif(
    not (_PKG / "osai_narrate" / "core.py").exists(),
    reason="osai-narrate package not colocated (pip-installed elsewhere)",
)

# A lesson with nothing to do with OSAI — proves the renderer is course-neutral.
_CC_LESSON = {
    "lesson_id": "CC01",
    "title": "Certified in Cybersecurity — Security Principles",
    "voice": "en-GB",
    "segments": [
        {"text": "Welcome to the CC course. This lesson covers the CIA triad.", "slide": "intro"},
        {"text": "Confidentiality, integrity, and availability are the three core goals.", "slide": "cia"},
        "Least privilege means giving each identity only the access its job requires.",
    ],
}

# Runs in the isolated child. Prints a JSON verdict on the last line of stdout.
_CHILD = r'''
import json, sys
from pathlib import Path

verdict = {}
# 1) No course app is reachable on this interpreter's path.
verdict["no_course_app_on_path"] = _no_spine()
import osai_narrate as nar                 # 2) the package imports standalone …
from osai_narrate import redaction
verdict["imported_standalone"] = True
verdict["no_course_app_after_import"] = "osai_spine" not in sys.modules

script = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
res = nar.write_manifest(script, out)      # 3) render a generic lesson → manifest + VTT
plan = res["plan"]
manifest = json.loads((out / "CC01.manifest.json").read_text())
vtt = (out / "CC01.vtt").read_text()
verdict["off_by_default"] = (nar.render_enabled() is False)
verdict["segment_count"] = plan["segment_count"]
verdict["manifest_segments"] = len(manifest["segments"])
verdict["audio_paths_scoped"] = all(s["audio"].startswith("CC01/") for s in manifest["segments"])
verdict["vtt_ok"] = vtt.startswith("WEBVTT") and vtt.count("-->") == plan["segment_count"]
# 4) the redaction tripwire still fires with no course code present
verdict["flag_tripwire"] = redaction.residual_secrets("token OSAI{deadbeef}") == ["REDACTED_FLAG"]
verdict["clean_text_ok"] = redaction.residual_secrets("plain narration text") == []
print(json.dumps(verdict))
'''

# how the child decides whether a course app leaked onto its path
_NO_SPINE = (
    "def _no_spine():\n"
    "    import importlib.util as u\n"
    "    return u.find_spec('osai_spine') is None\n"
)


def _run_isolated(script_json: Path, out_dir: Path) -> dict:
    """Run the child in a fresh interpreter whose only import root is the package."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_PKG)            # ONLY the package — not the spine dir
    env.pop("NARRATE", None)                 # ensure the seam is off by default
    env.pop("OSAI_TTS", None)
    body = _NO_SPINE + _CHILD
    proc = subprocess.run(
        # -S: skip site init so the editable-spine .pth finder is NOT loaded → honest isolation
        [sys.executable, "-S", "-c", body, str(script_json), str(out_dir)],
        cwd=str(out_dir),                    # neutral cwd: spine/ is not discoverable
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"isolated child failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_package_renders_generic_lesson_with_no_course_app(tmp_path):
    script_json = tmp_path / "cc01.json"
    script_json.write_text(json.dumps(_CC_LESSON))
    out = tmp_path / "out"
    out.mkdir()

    v = _run_isolated(script_json, out)

    # the coupling proof: a fresh interpreter with only the package on its path …
    assert v["no_course_app_on_path"] is True
    assert v["imported_standalone"] is True
    assert v["no_course_app_after_import"] is True
    # … still renders a generic, non-OSAI lesson end to end …
    assert v["off_by_default"] is True
    assert v["segment_count"] == 3 and v["manifest_segments"] == 3
    assert v["audio_paths_scoped"] is True
    assert v["vtt_ok"] is True
    # … and keeps the redaction tripwire without any course code present.
    assert v["flag_tripwire"] is True and v["clean_text_ok"] is True


def test_spine_adapter_reexports_the_same_package(tmp_path):
    """In-process: OSAI consumes the package through the thin adapter, so a plan built via
    ``osai_spine.narration`` is byte-identical to one built from the package directly —
    single source of truth, no forked renderer."""
    from osai_spine import narration as via_spine
    import osai_narrate as via_pkg

    assert via_spine.render_plan(_CC_LESSON) == via_pkg.render_plan(_CC_LESSON)
    # the adapter re-exports the package objects themselves, not copies
    assert via_spine.render_plan.__module__ == "osai_narrate.core"
