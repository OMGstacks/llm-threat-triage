# Narrated lessons — design & voice/production plan

> Companion to [07-architecture-and-stack.md](07-architecture-and-stack.md),
> [08-reporting-and-canva.md](08-reporting-and-canva.md) (slide/visual pipeline) and
> [12-content-authoring.md](12-content-authoring.md) (content schema). The **voice seam
> plumbing is already built** (`spine/osai_spine/narration.py` + `narrate` CLI +
> `tests/test_narration.py`), and now so is the **avatar (talking-head) seam** (§3.1) —
> both live in the shared, installable `packages/osai-narrate` package so every course that
> depends on it inherits the same upgrades. This doc is the design around them, plus the
> premium "your voice + your face" path and a pricing model.

## 1. The experience

A **fully-narrated lesson**, in the style the course is modelled after: an instructor's
voice walks the learner through the material while slides, diagrams and terminal demos
advance in sync — captions highlight as they're spoken, and the learner can scrub, change
speed, or read silently. Every Track-2+ lesson gets one.

## 2. The one architectural decision that governs everything: **pre-render**

A course is **authored content, not per-user chat**. So narration is rendered **once**,
cached, and shipped — never synthesized live per playback. Consequences:

- **Cost is a tiny one-time render**, not per-play. The whole ~250-lesson course is
  ~1.7M characters ≈ **$0 on a self-hosted voice**, or **~$25–30 via a cloud voice**, or
  **~$100–300 via ElevenLabs** — *once*. (Estimates; verify current rates.)
- The pipeline is **offline and deterministic**: script in → audio + timing manifest out.
- It works with **no API key and no network** at runtime, matching the project's DNA.

So the core of the seam — parse a script, emit a deterministic **render plan / manifest**
(segments, timing, captions, cache keys) — needs **no provider at all**. A provider only
fills in the audio files listed in the manifest.

## 3. The voice seam (built)

`narration.py` mirrors the optional-LLM seam (`llm.py`): provider-agnostic, **off by
default**, keys from env-or-`*_FILE` only (never logged), fail-closed.

| provider | kind | key | cost/1M chars | notes |
|---|---|---|---:|---|
| `browser` | client | — | $0 | Web Speech API in the player; zero-setup fallback |
| **`cmd`** (default) | local | — | **$0** | **any** local/OSS TTS CLI via `OSAI_TTS_CMD` (Piper, Kokoro, XTTS…) — `{text}` on stdin, `{out}` = file |
| `openai` | cloud | `OPENAI_API_KEY` | ~$15 | good quality, steerable style, word timing |
| `azure` | cloud | `AZURE_SPEECH_KEY` | ~$16 | many neural voices, SSML timing |
| `elevenlabs` | cloud | `ELEVENLABS_API_KEY` | ~$150 | best quality; voice cloning (see §6) |

**Default = OSS, self-hosted** (`cmd` provider). Recommended engines: **Kokoro-82M**
(small, fast, permissive, excellent) or **Piper** (lightweight) for the baseline, **XTTS-v2**
if you later want cloning without a vendor. $0/lesson, offline, no lock-in. ElevenLabs/OpenAI
sit behind the same interface as an opt-in upgrade — a one-line switch, no rearchitecting.

```
$ osai_spine narrate status                 # presence-only seam state (off by default)
$ osai_spine narrate --script L03.json plan # segments · duration · cost · cache keys (offline)
$ OSAI_TTS=1 OSAI_TTS_CMD="piper --model en_GB-alan-medium.onnx --output_file {out}" \
      osai_spine narrate --script L03.json --out narration render   # renders real audio
```

Render is gated behind `OSAI_TTS=1` **and** provider availability, and **fails closed** if
any flag/secret/PII survives redaction (a cloud render is egress — it reuses the vetted
`llm.residual_secrets` tripwire).

## 3.1 The avatar (talking-head) seam — plumbing (built)

A second, independent seam mirrors §3 exactly, for the premium "your face" path (§6):
provider-agnostic, **off by default**, presence-only key checks, fail-closed. It is **pure
plumbing** — no vendor SDK is wired, no key is ever used to make a real call, and no video
is produced by this seam today.

| provider | kind | key | notes |
|---|---|---|---|
| `none` (default) | — | — | no avatar; the manifest carries no `video` field at all |
| `heygen` | cloud | `HEYGEN_API_KEY` | script→avatar video; "Instant Avatar" from a short clip |
| `synthesia` | cloud | `SYNTHESIA_API_KEY` | custom avatars, strong for structured courses |
| `tavus` | cloud | `TAVUS_API_KEY` | developer API, real-time/conversational avatars |

There is no local/offline avatar analogue to a local TTS binary — every real provider here
is cloud, and every one is a **documented extension point**: `render_avatar_segment()`
always returns `{"rendered": False, "reason": "… extension point …"}` for `heygen` /
`synthesia` / `tavus`. Wiring an actual SDK call is future, separately-greenlit work.

```
$ osai_spine narrate status                 # now also prints the avatar seam's state
$ AVATAR_PROVIDER=heygen AVATAR_ID=<your-avatar-id> osai_spine narrate status
```

The one integration point with the render plan is **additive-only**: a segment gains a
cache-keyed `video` target (`sha256(provider|avatar|voice|text)`, mirroring `cache_key`)
**only** when the seam is opted into (`AVATAR=1` + a configured provider). With the seam off
— the default, and the only mode any shipped lesson uses today — `render_plan()` is
byte-for-byte identical to a plan built before this seam existed; every committed manifest
(L03 and later lessons) is unaffected. The player (§5) plays a segment's avatar video when
one is present, else falls back to its existing audio/timed-captions behaviour unchanged.

## 4. Script schema & render pipeline

A lesson narration script is authored prose (reuses the doc-12 content model):

```json
{ "lesson_id": "L03", "title": "Encoded payload smuggling", "voice": "en-GB",
  "segments": [
    { "text": "Welcome. We smuggle an encoded injection past a naive filter — OWASP LLM01.", "slide": "title" },
    { "text": "Base64-encode the instruction; the keyword filter never sees a banned word.", "slide": "attack-1" }
  ] }
```

`render_plan()` turns that into per-segment `{chars, est_seconds, audio (cache-keyed path),
slide}` + totals + a cost estimate. The **cache key** is `sha256(provider|voice|text)` — so
re-rendering only fires for changed segments (idempotent, like the fact-store fingerprints).
`write_manifest()` emits `<lesson>.manifest.json` that both the **player** (segment timing +
captions) and a **batch renderer** (fill in the audio) consume.

Pipeline: **author script → `narrate plan` (review/cost) → batch render once → cache audio +
manifest → ship.** Slides/terminal come from the doc-08 Marp/reveal.js/Mermaid path.

## 4.1 Worked example — render L03 locally (the first real lesson)

The first real narrated lesson ships at `spine/lessons/L03.json` (encoded payload
smuggling, 10 segments, ~3:19, grounded in the lab's own detector/OWASP/defence facts).
Rendering it needs **only a local OSS voice** — no key, no cloud:

```bash
# 1. plan it (offline — no provider needed): segments, timing, cost, cache keys
osai_spine narrate --script spine/lessons/L03.json plan

# 2. install a local voice once, e.g. Piper (or Kokoro / XTTS) — any CLI works
#    (see https://github.com/rhasspy/piper); download a British English voice model

# 3. render audio + manifest + WebVTT captions, cached and idempotent
OSAI_TTS=1 \
OSAI_TTS_CMD='piper --model en_GB-alan-medium.onnx --output_file {out}' \
  osai_spine narrate --script spine/lessons/L03.json --out narration render
```

Output: `narration/L03.manifest.json` (segment ids, captions, `start`/`end` timings,
sha256 cache keys, audio paths), `narration/L03.vtt` (WebVTT captions/transcript), and
`narration/L03/*.mp3` (one file per segment). Re-running only re-renders changed segments.
The player in §5 consumes exactly these three artifacts. The whole pipeline is proven
end-to-end offline in `tests/test_lesson_l03.py` with a mocked local voice.

## 5. The lesson player (built)

The `/lessons/[id]` route (`web/app/lessons/[id]/page.tsx` + `web/components/LessonPlayer.tsx`)
loads the committed manifest (`web/public/lessons/<id>.manifest.json`) and plays the lesson:
a slide panel (title + cue + caption) advances in sync with a highlighted transcript, with
play/pause and per-segment seek. It plays a **rendered per-segment avatar video when present**
(the §3.1 seam), else **rendered per-segment audio when present** (`/lessons/<id>/…` — both
probed on load), and **degrades gracefully** when neither is: timed captions by the manifest's
segment durations, with an optional "read aloud" browser voice. It is **pure presentation** —
no grading, no cloud calls. No shipped lesson carries a `video` yet (the avatar seam is off
by default), so this path is inert until a course opts in. The committed manifest + VTT are
kept in lockstep with the shipped script by a contract test (`test_lesson_l03.py`), so the
page can never show stale data. Live at **`/lessons/L03`**.

## 6. Premium path — **your voice and your face** ("my own course")

The seam makes the baseline free; the premium path makes it unmistakably *yours*. The
**plumbing for both halves is now built** (§3 for voice, §3.1 for avatar) — provider-agnostic,
gated, fail-closed, no SDK wired. What remains is entirely **your** doing: recording the
samples and wiring the two vendor SDKs behind the seam once you've trained them.

**Your voice (ElevenLabs Professional Voice Clone).** Record ~30 minutes of clean,
consistent audio → ElevenLabs trains a high-fidelity clone of *your* voice. Then set
`NARRATE_PROVIDER=elevenlabs` + `voice` to your cloned voice_id (the script's own `voice`
field is exactly that contract) and every lesson renders in your voice, once the ElevenLabs
SDK call is wired at `render_segment`'s documented extension point.
(An Instant Clone from ~1–3 min exists but pro-grade needs the longer sample + a paid tier.)
It's your own voice, so you own it — these tools verify consent to clone a real person, which
is exactly right for yourself.

**Your face (AI talking-head avatar).** Record a few minutes to camera once, then generate
every lesson video from a script in your likeness. The seam names three providers
(`AVATAR_PROVIDER=heygen|synthesia|tavus`, §3.1) — pick one, train the avatar, wire its SDK:

- **HeyGen** — market leader for script→avatar video; "Instant Avatar" from a short clip.
- **Synthesia** — enterprise custom avatars, strong for structured courses.
- **Tavus** — developer API + real-time/conversational avatars (good if you want an
  interactive "ask the instructor" mode later).
- **D-ID / Argil / Captions** — talking-portrait / creator-focused alternatives (not named
  in the seam's provider set yet; add one the same way if you pick one of these instead).

**Recommended "it's my course" stack:** ElevenLabs (your voice) → HeyGen (your face
lip-synced to that audio, matching the seam's default recommendation) → composite the
talking head as a corner PiP over the slide/terminal capture (ffmpeg or Remotion, from the
manifest timings) → MP4 per lesson → host on the platform. One recording session bootstraps
voice + avatar; after that, **new lessons are just new scripts** — no re-recording.

**Production cost** (subscriptions, verify current): HeyGen ~$29–89/mo · Synthesia ~$18–89+/mo ·
ElevenLabs Creator ~$22 / Pro ~$99/mo. Rendering a course fits inside a month or two of a
plan — a modest one-time production cost, not a per-student cost.

**Guardrail:** the *format* can be inspired by any course; the **scripts, examples, slides,
labs, and grading are our own original content** (the standing no-proprietary-content rule).

## 7. Pricing — realistic & competitive

You're the **affordable, practical prep** that gets someone ready for the exam — priced
*below* the certification, the lane TCM Security / Zero-Point Security use to undercut OffSec.
Market comps (self-paced, hands-on security training; verify current):

| Model | Realistic price | When it fits |
|---|---|---|
| Udemy listing | list $120–200, **nets ~$10–30/sale** after platform discounts | reach & funnel, not margin |
| **Single course, own platform** (this AI-300/OSAI prep: 20 labs + narrated lessons + grading) | **$149–$399** (anchor **~$199**) | the core offer; keeps margin + brand |
| All-access membership | **$29–49/mo** or **$399–599/yr** | recurring revenue; fits the per-student lab-infra cost |
| Lifetime all-access | **$499–999** | launch/founder offer |
| Premium (mentorship, graded capstone review, community) | **$499–1,500** | high-touch upsell |

Reference points: **OffSec OSCP ~$1,600+** (you price *under* this), **TCM Security** courses
~$30 / all-access ~$30/mo / PNPT cert ~$400, **Zero-Point CRTO ~£365**, **HTB Academy** tiered
subscription. Given the AI-red-team niche is hot and underserved, **~$199 for the flagship
course** and a **~$39/mo (or ~$499/yr) all-access** with the labs behind it is a credible,
competitive anchor. Note: running exploitable per-student lab containers has real compute
cost — that pushes toward the subscription/lab-time model rather than a cheap one-time price.

## 8. Status & roadmap

- ✅ **Built:** the provider-agnostic narration seam (`narration.py`), the `narrate
  status/plan/render` CLI, script parsing, deterministic plan/manifest + WebVTT captions +
  cost model, gated fail-closed render. OSS-default, off by default, no keys, CI-green.
- ✅ **Proven:** the **first real lesson**, `spine/lessons/L03.json`, renders end-to-end
  through the local OSS seam — manifest + captions + per-segment audio — tested offline in
  `tests/test_lesson_l03.py` (§4.1).
- ✅ **Built:** the repo `/lessons/[id]` **player** — consumes the committed manifest + VTT,
  synced slides/captions, audio-when-present with a graceful captions/timing fallback,
  contract-tested against the script. Live at `/lessons/L03`.
- ✅ **Extracted:** the renderer is now the shared, installable `osai-narrate` package
  (`packages/osai-narrate`) — stdlib-only, no course-app coupling — so voice/avatar/render
  upgrades land once and every dependent course inherits them; OSAI consumes it via a thin
  adapter. See `docs/adopting-narrated-lessons.md`.
- ✅ **Built (this PR):** the **avatar (talking-head) seam** (§3.1) — plumbing only,
  mirroring the voice seam's safety posture exactly: off by default, presence-only keys,
  fail-closed, and `heygen` / `synthesia` / `tavus` are documented extension points with no
  SDK wired. The render plan gains a `video` field only when opted in (additive, byte-
  identical otherwise); the player plays it when present. The ElevenLabs voice-clone
  extension point (§6) is likewise fully documented at `render_segment`, unimplemented.
- ▶ **Next:** (1) keep authoring lesson scripts across the tracks — the seam and the
  player are proven, so this is now pure content work; (2) **needs your keys + recorded
  samples, separately greenlit** — record your ElevenLabs voice clone and train a HeyGen
  avatar, then wire each SDK at its documented extension point; (3) package + price per §7.
  The repo-backed `/tutor` · `/report` · lab-grader web vertical slice still stands as a
  parallel track.
