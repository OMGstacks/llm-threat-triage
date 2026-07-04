"use client";

// Narrated-lesson player. Pure presentation: it loads the offline-generated render
// manifest (public/lessons/<id>.manifest.json), advances slides + captions in sync, and
// plays per-segment audio when it's been rendered — otherwise it falls back gracefully to
// timed captions (optionally read by the browser's built-in voice). It never grades and
// never calls a cloud TTS. See 27-narrated-lessons.md.

import { useCallback, useEffect, useRef, useState } from "react";
import type { LessonManifest, LessonSegment } from "@/lib/types";

const human = (s: string) =>
  (s || "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const mmss = (x: number) => {
  const m = Math.floor(x / 60);
  const s = Math.round(x % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
};

export default function LessonPlayer({ lessonId }: { lessonId: string }) {
  const [manifest, setManifest] = useState<LessonManifest | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);
  const [useVoice, setUseVoice] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const idxRef = useRef(0);
  idxRef.current = idx;

  // load the manifest + probe whether rendered audio exists (graceful either way)
  useEffect(() => {
    let live = true;
    fetch(`/lessons/${lessonId}.manifest.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`manifest ${r.status}`))))
      .then((m: LessonManifest) => {
        if (!live) return;
        setManifest(m);
        const first = m.segments[0];
        if (first) {
          fetch(`/lessons/${first.audio}`, { method: "HEAD" })
            .then((r) => live && setHasAudio(r.ok))
            .catch(() => live && setHasAudio(false));
        }
      })
      .catch((e: unknown) => live && setErr(e instanceof Error ? e.message : "failed to load lesson"));
    return () => {
      live = false;
    };
  }, [lessonId]);

  const stopTimers = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel();
    if (audioRef.current) audioRef.current.pause();
  }, []);

  // advance driver — audio 'ended' when rendered, else browser voice or a timed fallback
  const runSegment = useCallback(
    (i: number, segs: LessonSegment[]) => {
      stopTimers();
      if (i >= segs.length) {
        setPlaying(false);
        return;
      }
      setIdx(i); // advance the highlighted slide/caption as the engine moves
      idxRef.current = i;
      const seg = segs[i];
      const onDone = () => {
        if (idxRef.current === i) runSegment(i + 1, segs);
      };
      if (hasAudio && audioRef.current) {
        const a = audioRef.current;
        a.src = `/lessons/${seg.audio}`;
        a.onended = onDone;
        a.play().catch(onDone); // if a file is missing, don't stall — move on
        return;
      }
      if (useVoice && typeof window !== "undefined" && window.speechSynthesis) {
        const u = new SpeechSynthesisUtterance(seg.text);
        u.onend = onDone;
        window.speechSynthesis.speak(u);
        return;
      }
      // pure captions/timing fallback: hold each slide for its estimated duration
      timerRef.current = setTimeout(onDone, Math.max(1200, seg.est_seconds * 1000));
    },
    [hasAudio, useVoice, stopTimers],
  );

  const play = useCallback(() => {
    if (!manifest) return;
    setPlaying(true);
    runSegment(idxRef.current, manifest.segments);
  }, [manifest, runSegment]);

  const pause = useCallback(() => {
    setPlaying(false);
    stopTimers();
  }, [stopTimers]);

  const seek = useCallback(
    (i: number) => {
      if (!manifest) return;
      const n = Math.max(0, Math.min(manifest.segments.length - 1, i));
      setIdx(n);
      idxRef.current = n;
      if (playing) runSegment(n, manifest.segments);
      else stopTimers();
    },
    [manifest, playing, runSegment, stopTimers],
  );

  // stop audio/voice/timers when the player unmounts
  useEffect(() => () => stopTimers(), [stopTimers]);

  if (err) {
    return (
      <main>
        <section className="panel">
          <h2>Lesson</h2>
          <div className="out">
            <span className="pill bad">error</span> {err}
            {"\n"}Expected <code>/lessons/{lessonId}.manifest.json</code> — generate it with{" "}
            <code>osai_spine narrate --script spine/lessons/{lessonId}.json --out web/public/lessons render</code>.
          </div>
        </section>
      </main>
    );
  }
  if (!manifest) {
    return (
      <main>
        <section className="panel">
          <h2>Lesson</h2>
          <div className="sub">loading {lessonId}…</div>
        </section>
      </main>
    );
  }

  const seg = manifest.segments[idx];
  const pct = (seg.start / (manifest.est_seconds || 1)) * 100;
  const mode = hasAudio ? "rendered audio" : useVoice ? "browser voice" : "timed captions";

  return (
    <main style={{ display: "block", maxWidth: 860, margin: "0 auto" }}>
      <section className="panel">
        <h2>
          Lesson {manifest.lesson_id} — {manifest.title}
        </h2>
        <div className="sub" style={{ marginBottom: 10 }}>
          narrated · {manifest.segment_count} segments · {manifest.est_duration} ·{" "}
          <span className="pill">{mode}</span>
        </div>

        {/* stage / slide */}
        <div
          style={{
            background: "#0d1117",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: "22px 24px",
            minHeight: 220,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          <div className="row" style={{ margin: 0, justifyContent: "space-between" }}>
            <span
              className="sub"
              style={{ letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--acc)" }}
            >
              {human(seg.slide || "slide")}
            </span>
            <span className="sub">
              {idx + 1} / {manifest.segment_count}
            </span>
          </div>
          <h3 style={{ margin: 0, fontSize: 26, lineHeight: 1.1 }}>{human(seg.slide || manifest.title)}</h3>
          <p style={{ margin: 0, fontSize: 16, color: "var(--ink)" }}>{seg.text}</p>
        </div>

        {/* controls */}
        <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
          <button onClick={() => (playing ? pause() : play())} aria-label={playing ? "Pause" : "Play"}>
            {playing ? "⏸ Pause" : "▶ Play"}
          </button>
          <button className="ghost" onClick={() => seek(idx - 1)} aria-label="Previous segment">
            ⟨ Prev
          </button>
          <button className="ghost" onClick={() => seek(idx + 1)} aria-label="Next segment">
            Next ⟩
          </button>
          <span className="sub" style={{ fontFamily: "ui-monospace, Menlo, monospace" }}>
            {mmss(seg.start)} / {manifest.est_duration}
          </span>
          <div
            style={{
              flex: 1,
              minWidth: 100,
              height: 6,
              background: "#0d1117",
              border: "1px solid var(--line)",
              borderRadius: 999,
              overflow: "hidden",
            }}
          >
            <div style={{ height: "100%", width: `${pct}%`, background: "var(--acc)" }} />
          </div>
          {!hasAudio && (
            <label className="sub row" style={{ margin: 0, gap: 6 }}>
              <input
                type="checkbox"
                checked={useVoice}
                onChange={(e) => setUseVoice(e.target.checked)}
                style={{ width: "auto" }}
              />
              read aloud
            </label>
          )}
        </div>
        {!hasAudio && (
          <div className="sub" style={{ marginTop: 6 }}>
            Narration audio isn&apos;t rendered in this build — showing timed captions and slides. Render it
            with a local voice (see <code>27-narrated-lessons.md</code>) to hear it, or tick “read aloud”.
          </div>
        )}
        <audio ref={audioRef} hidden preload="none" onError={() => setHasAudio(false)} />
      </section>

      {/* transcript */}
      <section className="panel" style={{ marginTop: 14 }}>
        <h2>Transcript &amp; slides</h2>
        <div style={{ display: "grid", gap: 6 }}>
          {manifest.segments.map((s, i) => (
            <button
              key={s.id}
              onClick={() => seek(i)}
              className="ghost"
              style={{
                textAlign: "left",
                display: "grid",
                gridTemplateColumns: "52px 120px 1fr",
                gap: 10,
                padding: "8px 10px",
                borderColor: i === idx ? "var(--acc)" : "var(--line)",
                background: i === idx ? "rgba(47,129,247,0.08)" : "transparent",
              }}
            >
              <span className="sub" style={{ fontFamily: "ui-monospace, Menlo, monospace" }}>
                {mmss(s.start)}
              </span>
              <span className="sub" style={{ color: i === idx ? "var(--acc)" : "var(--muted)" }}>
                {human(s.slide || "")}
              </span>
              <span style={{ color: i === idx ? "var(--ink)" : "var(--muted)" }}>{s.text}</span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
