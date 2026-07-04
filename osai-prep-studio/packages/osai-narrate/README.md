# osai-narrate

A **portable, offline-first, provider-agnostic** narrated-lesson renderer.

Turn a lesson script into a **deterministic render plan**, **WebVTT captions**, and —
only if you opt in and configure a voice — **audio**. The plan, manifest, and captions
need **no provider, no key, and no network**; a provider merely fills in the audio files
the manifest already lists.

The package is **stdlib-only** and has **no course-app import**. That is the whole point:
the same renderer is shared across course projects so a voice / avatar / rendering upgrade
lands **once** and every course that depends on the package inherits it — no code drift.

## Why "pre-render"?

A course is authored content. You render each lesson script to audio **once**, cache the
audio next to a timing/caption manifest, and ship both. Learners stream cached audio; you
never pay per-play and the default experience works fully offline.

```
lesson script ──parse──▶ render plan ──▶ manifest.json + captions.vtt   (always, offline)
                              │
                              └──▶ audio/*.mp3   (only when NARRATE=1 + a provider)
```

## Install

```bash
pip install osai-narrate           # once published
# or, from a checkout:
pip install -e osai-prep-studio/packages/osai-narrate
```

Stdlib-only: no third-party runtime dependencies are pulled in.

## Library

```python
import osai_narrate as nar

script = {
    "lesson_id": "CC01",
    "title": "Security Principles",
    "voice": "en-GB",
    "segments": [
        {"text": "Welcome. This lesson covers the CIA triad.", "slide": "intro"},
        "Confidentiality, integrity, and availability are the three core goals.",
    ],
}

plan = nar.render_plan(script)         # deterministic: timings, cache-keyed audio paths, cost estimate
nar.write_manifest(script, "out/")     # writes out/CC01.manifest.json + out/CC01.vtt
```

`render_plan` / `write_manifest` never touch the network. `render_segment` writes audio
**only** when the seam is enabled and a provider is configured — and it **fails closed** if
any secret/flag/PII survives redaction (see below).

## CLI

```bash
narrate status                       # presence-only seam state (never a key value)
narrate plan  --script lesson.json   # print the offline render plan
narrate render --script lesson.json --out out/   # write manifest + captions (+ audio if enabled)
```

A script is either structured JSON (`{"lesson_id","title","voice","segments":[…]}`) or a
plain-text file whose blank-line-separated paragraphs each become a segment.

## Providers

Choose with `NARRATE_PROVIDER`; server-side rendering is **off** until `NARRATE=1`.

| provider     | kind   | key             | notes                                             |
|--------------|--------|-----------------|---------------------------------------------------|
| `browser`    | client | none            | Web Speech API in the player; free, no server render |
| `cmd`        | local  | none            | **any** local/OSS TTS CLI (Piper, Kokoro, XTTS…) via `NARRATE_CMD`. **Default.** |
| `openai`     | cloud  | `OPENAI_API_KEY`     | neural voice; SDK call is a documented extension point |
| `elevenlabs` | cloud  | `ELEVENLABS_API_KEY` | neural voice; extension point                     |
| `azure`      | cloud  | `AZURE_SPEECH_KEY`   | neural voice; extension point                     |

`NARRATE_CMD` is a template: `{out}` → the audio path, `{voice}` → the voice; the redacted
narration text is fed on **stdin**. Example: `piper --model en_GB.onnx --output_file {out}`.

## Environment variables (course-neutral, with legacy aliases)

Every var accepts a neutral name **or** a legacy `OSAI_TTS*` alias, so existing OSAI
deployments keep working unchanged. The neutral name wins when both are set.

| purpose            | neutral                 | legacy alias               |
|--------------------|-------------------------|----------------------------|
| enable rendering   | `NARRATE=1`             | `OSAI_TTS=1`               |
| choose provider    | `NARRATE_PROVIDER`      | `OSAI_TTS_PROVIDER`        |
| local TTS command  | `NARRATE_CMD`           | `OSAI_TTS_CMD`             |
| cost override      | `NARRATE_RATE_<P>`      | `OSAI_TTS_RATE_<P>`        |

Cloud keys are read from their own env var **or** a `*_FILE` secret (e.g.
`OPENAI_API_KEY_FILE=/run/secrets/openai`). Keys are checked **presence-only** — never
logged, hashed, or returned.

## Safety: fail-closed redaction

`render_segment` runs the text through the same redaction tripwire the course uses before
any audio is produced. If a flag (`OSAI{…}`), email, cloud key, private-key block, or other
secret survives redaction, **nothing is written** — no subprocess, no network call. The
tripwire (`osai_narrate.redaction`) is self-contained so the package carries no course
dependency.

## Tests

```bash
cd osai-prep-studio/packages/osai-narrate && pytest -q
```

The portability suite proves the package imports and renders a **generic, non-OSAI** lesson
with no course-app on the path, emits a manifest + WebVTT, and keeps the redaction
tripwire — all off by default.

## Adopting this in another course

See [`../../docs/adopting-narrated-lessons.md`](../../docs/adopting-narrated-lessons.md) for
two paths: a **same-stack** adoption (Python spine + the Next.js player) and a
**different-stack** adoption (use the CLI to emit manifest/VTT and port the player shell).
The durable rule: **depend on this one shared package** — do not fork the renderer.
