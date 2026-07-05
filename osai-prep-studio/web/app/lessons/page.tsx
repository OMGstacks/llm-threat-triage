"use client";

// Lessons index. Pure presentation: it loads the offline-generated catalog served from
// /public/lessons/index.json (built by osai_spine.lessons) and lists every narrated lesson,
// grouped by track, each linking to its /lessons/<id> player. No grading, no cloud calls.

import Link from "next/link";
import { useEffect, useState } from "react";
import type { LessonCard, LessonIndex } from "@/lib/types";

const TRACK_NAME: Record<number, string> = {
  2: "Track 2 — AI systems fundamentals",
  3: "Track 3 — LLM / RAG red team",
  4: "Track 4 — agentic red team",
  5: "Track 5 — AI infra / cloud",
  6: "Track 6 — defence, detection & reporting",
};

function LessonRow({ c }: { c: LessonCard }) {
  return (
    <Link
      href={`/lessons/${c.lesson_id}`}
      className="ghost"
      style={{
        textAlign: "left",
        display: "grid",
        gridTemplateColumns: "88px 1fr auto",
        gap: 12,
        alignItems: "center",
        padding: "10px 12px",
        borderColor: "var(--line)",
      }}
    >
      <span className="pill" style={{ justifySelf: "start" }}>
        {c.lesson_id}
      </span>
      <span style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <span style={{ color: "var(--ink)", fontWeight: 600 }}>{c.title}</span>
        <span className="sub" style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {c.module ? <span>{c.module}</span> : null}
          {c.frameworks.map((f) => (
            <span key={f} className="pill" style={{ fontSize: 11, opacity: 0.85 }}>
              {f}
            </span>
          ))}
          {c.detector ? (
            <span className="pill" style={{ fontSize: 11, opacity: 0.85 }}>
              detector: {c.detector}
            </span>
          ) : null}
        </span>
      </span>
      <span className="sub" style={{ fontFamily: "ui-monospace, Menlo, monospace", justifySelf: "end" }}>
        {c.segment_count} seg · {c.est_duration}
      </span>
    </Link>
  );
}

export default function LessonsIndexPage() {
  const [index, setIndex] = useState<LessonIndex | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetch("/lessons/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`index ${r.status}`))))
      .then((d: LessonIndex) => live && setIndex(d))
      .catch((e: unknown) => live && setErr(e instanceof Error ? e.message : "failed to load lessons"));
    return () => {
      live = false;
    };
  }, []);

  if (err) {
    return (
      <main>
        <section className="panel">
          <h2>Lessons</h2>
          <div className="out">
            <span className="pill bad">error</span> {err}
            {"\n"}Expected <code>/lessons/index.json</code> — build it with{" "}
            <code>python -m osai_spine.cli lessons build</code>.
          </div>
        </section>
      </main>
    );
  }
  if (!index) {
    return (
      <main>
        <section className="panel">
          <h2>Lessons</h2>
          <div className="sub">loading…</div>
        </section>
      </main>
    );
  }

  const tracks = Array.from(new Set(index.lessons.map((c) => c.track))).sort((a, b) => a - b);

  return (
    <main style={{ display: "block", maxWidth: 860, margin: "0 auto" }}>
      <section className="panel">
        <h2>Narrated lessons</h2>
        <div className="sub" style={{ marginBottom: 10 }}>
          {index.count} lessons · pre-rendered captions + slides · plays offline{" "}
          <span className="pill">no cloud audio</span>
        </div>
        {tracks.map((t) => (
          <div key={t} style={{ marginBottom: 14 }}>
            <div
              className="sub"
              style={{ letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--acc)", marginBottom: 6 }}
            >
              {TRACK_NAME[t] || `Track ${t}`}
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              {index.lessons
                .filter((c) => c.track === t)
                .map((c) => (
                  <LessonRow key={c.lesson_id} c={c} />
                ))}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}
