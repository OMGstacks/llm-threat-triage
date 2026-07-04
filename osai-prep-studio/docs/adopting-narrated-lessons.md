# Adopting narrated lessons in another course

This guide shows how a **second course project** (for example, an adjacent CC — "Certified
in Cybersecurity" — prep course) gets the same narrated-lesson experience OSAI Prep Studio
has: a lesson script → a deterministic **render plan / manifest / captions**, and, when you
opt in, **audio**.

It documents two adoption paths and — more importantly — the **one rule** that keeps every
course upgrading together.

---

## The durable rule: depend on the package, don't fork it

> **Do not copy the narration code into another course as the long-term path.** Copy-in is
> acceptable only as a temporary, manual bootstrap. The durable architecture is **one
> shared, versioned narration package** — [`osai-narrate`](../packages/osai-narrate) — that
> every course *depends on*. Voice, avatar, and rendering upgrades then happen **once, in
> the package**, and every course inherits them on the next version bump. No drift, no
> re-implementing redaction per course, no "which copy is the good one."

OSAI itself already follows this rule: `osai_spine/narration.py` is a **thin adapter** that
re-exports the package's public API. OSAI does not own a private renderer — it consumes the
shared one. A second course should do the same.

```
                      ┌──────────────────────────┐
                      │   osai-narrate (package) │   ← one source of truth
                      │  render plan · VTT · TTS │      voice/avatar upgrades land HERE
                      └──────────────────────────┘
                        ▲                       ▲
        depends on ─────┘                       └───── depends on
   ┌───────────────────────┐            ┌───────────────────────────┐
   │  OSAI Prep Studio      │            │  CC prep course (or any)  │
   │  narration.py = adapter│            │  adapter or CLI + player  │
   └───────────────────────┘            └───────────────────────────┘
```

The package is **stdlib-only** and has **no course-app import** — that is what makes it safe
to share. A portability test proves it (see [Proof](#proof-the-package-has-no-course-coupling)).

---

## The interop contract (both paths depend on this, nothing else)

Whatever your stack, the boundary between "renderer" and "player" is two files the package
emits per lesson. Depend on these shapes, not on any internal function.

**`<lesson_id>.manifest.json`** — the timing/caption/audio manifest the player consumes:

```jsonc
{
  "lesson_id": "CC01",
  "title": "Security Principles",
  "voice": "en-GB",
  "provider": "cmd",
  "kind": "local",
  "segment_count": 3,
  "total_chars": 180,
  "est_duration": "0:12",
  "est_seconds": 12.4,
  "est_cost_usd": 0.0,
  "rate_per_million_usd": 0.0,
  "segments": [
    {
      "id": "001-welcome-to-the-cc-course",
      "text": "Welcome to the CC course. This lesson covers the CIA triad.",
      "chars": 59,
      "start": 0.0,
      "end": 4.07,
      "est_seconds": 4.1,
      "audio": "CC01/001-welcome-to-the-cc-course.<hash>.mp3",
      "slide": "intro"
    }
  ]
}
```

**`<lesson_id>.vtt`** — standard WebVTT captions/transcript, one cue per segment.

Key properties the player can rely on:

- **Deterministic.** Same script → byte-identical manifest and VTT. `audio` paths are
  content-addressed (`sha256(provider|voice|text)`), so a segment's audio filename only
  changes when its text/voice/provider changes — cache-friendly, idempotent re-renders.
- **Audio is optional.** The manifest and captions always ship, even with **no provider**.
  A player must **degrade gracefully**: if `audio` files aren't present, fall back to
  timed captions (each slide held for `est_seconds`) or a client-side browser voice.
- **`slide`** is an optional per-segment cue the player can render as a slide title/section.

---

## Path 1 — same stack (Python spine + the Next.js player)

Best when the new course is also a Python backend + a Next.js/React front end (the OSAI
shape). You reuse both the renderer **and** the player component.

### 1. Depend on the package

```bash
pip install osai-narrate            # once published
# or, in a monorepo, install the co-located package editable:
pip install -e osai-prep-studio/packages/osai-narrate
```

If you keep the course in the **same monorepo**, you can skip the install entirely and use a
thin adapter exactly like OSAI's — a path-bootstrap that adds the package dir to `sys.path`:

```python
# cc_spine/narration.py  — the CC course's adapter (mirrors osai_spine/narration.py)
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[2] / "packages" / "osai-narrate"
if _PKG.is_dir() and str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from osai_narrate.core import render_plan, write_manifest, status  # noqa: E402,F401  (re-export)
```

Adapter, **not** a fork: the course never owns renderer logic, so a package upgrade needs no
change here.

### 2. Author a lesson script

A script is structured JSON (or plain text whose blank-line-separated paragraphs become
segments):

```json
{
  "lesson_id": "CC01",
  "title": "Security Principles",
  "voice": "en-GB",
  "segments": [
    {"text": "Welcome to the CC course. This lesson covers the CIA triad.", "slide": "intro"},
    {"text": "Confidentiality, integrity, and availability are the three core goals.", "slide": "cia"},
    "Least privilege means giving each identity only the access its job requires."
  ]
}
```

### 3. Emit the manifest + captions into the web app's public dir

```bash
narrate render --script cc_spine/lessons/CC01.json --out web/public/lessons
# writes web/public/lessons/CC01.manifest.json and CC01.vtt
# audio is NOT rendered unless you opt in (next step) — the player degrades gracefully
```

### 4. Mount the player

Reuse the OSAI player shell — [`web/components/LessonPlayer.tsx`](../web/components/LessonPlayer.tsx)
and the route [`web/app/lessons/[id]/page.tsx`](../web/app/lessons/[id]/page.tsx). It is
**pure presentation**: it fetches `/lessons/<id>.manifest.json`, syncs slides + captions,
plays per-segment audio when present, and otherwise falls back to timed captions or a browser
voice. It never grades and never calls a cloud TTS. Copy the two files, keep the
`LessonManifest`/`LessonSegment` types (from [`web/lib/types.ts`](../web/lib/types.ts)), done.

### 5. (Optional) render real audio, once

Rendering is **off by default**. To pre-render audio with a local OSS voice:

```bash
export NARRATE=1
export NARRATE_PROVIDER=cmd
export NARRATE_CMD='piper --model en_GB-alba-medium.onnx --output_file {out}'   # text on stdin
narrate render --script cc_spine/lessons/CC01.json --out web/public/lessons
```

Commit the resulting `CC01/*.mp3` next to the manifest. Because filenames are
content-addressed, only changed segments re-render on the next pass.

---

## Path 2 — different stack (any language / framework)

Best when the new course is **not** Python + Next.js — a Go/Rails/SvelteKit/static-site
course, say. You still depend on the **one** package; you just use it through its **CLI** and
re-implement the thin player shell against the [contract](#the-interop-contract-both-paths-depend-on-this-nothing-else)
above.

### 1. Use the CLI as the render step

`osai-narrate` ships a `narrate` console script. Call it from your build pipeline (a `make`
target, a CI job, a git hook) — no Python needs to appear in your app:

```bash
pip install osai-narrate
narrate status                                            # presence-only seam state
narrate plan   --script content/CC01.json --json         # inspect the offline plan
narrate render --script content/CC01.json --out public/lessons   # emit manifest + VTT (+ audio if enabled)
```

The command emits `public/lessons/CC01.manifest.json` + `CC01.vtt`. Serve them as static
assets. That is the entire coupling surface — your app never imports the package.

### 2. Port the player shell to your framework

Re-implement a small presentational component against the manifest contract. The OSAI
[`LessonPlayer.tsx`](../web/components/LessonPlayer.tsx) is the reference; the behavior to
reproduce in any framework is:

1. **Load** `/(lessons)/<id>.manifest.json`.
2. **Render the current segment**: show `slide` as a section label and `text` as the caption;
   a progress bar from `start / est_seconds`.
3. **Advance**: if an `audio` file exists for the segment (HEAD-probe the first one), play it
   and advance on `ended`. Otherwise **degrade gracefully** — hold each slide for
   `est_seconds` (timed captions), optionally driving the platform's built-in
   text-to-speech.
4. **Transcript**: list every segment with its `start` time as clickable seek targets; the
   `.vtt` doubles as an accessible transcript / subtitle track.

No grading, no cloud calls, no course logic lives in the player — it is a view over the
manifest. Keeping it thin is what lets the shared package own every future upgrade.

---

## What "upgrade once, inherit everywhere" buys you

Because both courses depend on the same package, the roadmap items land in **one** place:

- **Premium neural voice** (e.g. an ElevenLabs voice clone) — wire the `elevenlabs` provider's
  SDK at the documented extension point in `render_segment`. Both courses get it by bumping
  the package version; neither changes a line of course code.
- **Talking-head avatar** (e.g. HeyGen/Synthesia) — add an avatar render stage that consumes
  the same manifest (it already has per-segment text + timing). Ships to every course at once.
- **Better timing / caption model, new cache strategy, new output format** — same story.

Fork the renderer into each course and you'd re-do every one of these per course, and they'd
drift. That is the failure mode this package exists to prevent.

> None of those premium providers are implemented yet, and this package pulls in **no**
> provider SDKs, keys, avatar rendering, or cloud calls. They are documented extension points
> behind the seam so the plumbing is ready when the work is greenlit.

---

## Security posture (inherited by every adopter)

The package is safe-by-default, and every course that depends on it inherits that posture:

- **Off by default.** `render_enabled()` is `False` unless `NARRATE=1` (or the legacy
  `OSAI_TTS=1`) **and** a provider is actually available. The default experience is fully
  offline — manifest + captions only — so CI stays green with no keys.
- **Presence-only key checks.** Cloud keys are read from an env var or a `*_FILE` secret and
  checked for **presence only** — never logged, hashed, or returned. `narrate status` shows
  `present=yes/no`, never the value.
- **Fail-closed redaction.** `render_segment` runs text through a self-contained redaction
  tripwire before producing any audio. If a flag (`OSAI{…}`), email, cloud key, private-key
  block, or other secret survives redaction, **nothing is written** — no subprocess, no
  network. The tripwire lives in the package (`osai_narrate.redaction`) so it can't drift
  from the renderer.
- **No secrets in the repo.** Keys live only in the runtime environment / secret store, per
  [`docs/security/api-key-and-data-handling.md`](security/api-key-and-data-handling.md).

---

## Proof: the package has no course coupling

Two portability suites keep the "no course-app dependency" claim honest:

- **From the package** — [`packages/osai-narrate/tests/test_portability.py`](../packages/osai-narrate/tests/test_portability.py):
  imports and renders a **generic, non-OSAI** (CC) lesson, emits a manifest + WebVTT, and
  exercises the redaction tripwire — all with no course app on the path.
- **From the consuming course** — [`spine/tests/test_narrate_portability.py`](../spine/tests/test_narrate_portability.py):
  spawns a fresh, site-less interpreter whose import root is **only** the package, then
  renders the generic lesson there. If the package had smuggled in a course import, that
  subprocess would fail and the test would go red. A second in-process test asserts OSAI's
  adapter re-exports the **same** package objects (a plan built via `osai_spine.narration`
  is byte-identical to one built from `osai_narrate` directly) — proving single-source-of-
  truth, not a forked copy.

Run them:

```bash
# from the package
cd osai-prep-studio/packages/osai-narrate && pytest -q
# from the OSAI course
cd osai-prep-studio/spine && python -m pytest tests/test_narrate_portability.py -q
```

---

## See also

- [`packages/osai-narrate/README.md`](../packages/osai-narrate/README.md) — the package's own docs (API, CLI, providers, env vars).
- [`27-narrated-lessons.md`](../27-narrated-lessons.md) — the narration design doc: pre-render model, provider comparison, the premium voice-clone + avatar path, and pricing.
