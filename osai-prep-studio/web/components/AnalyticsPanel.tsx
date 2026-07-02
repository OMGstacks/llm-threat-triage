"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useLearner } from "@/lib/learner";
import type { Analytics, FamilyMastery, LabProgressItem } from "@/lib/types";

const short = (tag: string) => tag.replace(":2025", "");
const pct = (m: number) => Math.round((m || 0) * 100);

// study-pack export artifacts (08-reporting-and-canva.md §4) — offline fallback path
const EXPORTS: { artifact: string; label: string; mime: string }[] = [
  { artifact: "studypack.md", label: "Study pack (.md)", mime: "text/markdown" },
  { artifact: "flashcards.csv", label: "Flashcards (Anki .csv)", mime: "text/csv" },
  { artifact: "deck.md", label: "Slide deck (Marp .md)", mime: "text/markdown" },
  { artifact: "labmap.mmd", label: "Lab map (Mermaid)", mime: "text/plain" },
];

async function saveArtifact(learner: string, artifact: string, mime: string) {
  const text = await api.exportArtifact(learner, artifact);
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `osai-${learner}-${artifact}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Bar({ mastery }: { mastery: number }) {
  return (
    <div className="bar">
      <span
        style={{
          width: `${pct(mastery)}%`,
          background: mastery >= 0.5 ? "var(--ok)" : mastery > 0 ? "var(--acc)" : "var(--bad)",
        }}
      />
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ minWidth: 92 }}>
      <div style={{ fontSize: 22, fontWeight: 600 }}>{value}</div>
      <div className="sub">{label}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

function FamilySection({ title, entries }: { title: string; entries: FamilyMastery[] }) {
  if (!entries.length) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <div className="sub" style={{ marginBottom: 4 }}>
        {title}
      </div>
      {entries.map((e) => (
        <div className="row" style={{ gap: 6 }} key={e.tag} title={`${e.name} · ${e.reps} reps`}>
          <span style={{ width: 92 }} className="muted">
            {short(e.tag)}
          </span>
          <Bar mastery={e.mastery} />
          <span className="sub" style={{ width: 34, textAlign: "right" }}>
            {pct(e.mastery)}%
          </span>
        </div>
      ))}
    </div>
  );
}

const STATUS_LABEL: Record<LabProgressItem["status"], string> = {
  passed: "passed",
  attempted: "attempted",
  not_started: "not started",
};

function LabChip({ it }: { it: LabProgressItem }) {
  const cls = it.status === "passed" ? "pill ok" : it.status === "attempted" ? "pill" : "pill";
  const style =
    it.status === "attempted"
      ? { color: "var(--acc)", borderColor: "var(--acc)" }
      : it.status === "not_started"
      ? { color: "var(--muted)" }
      : undefined;
  return (
    <span
      className={cls}
      style={style}
      title={`${it.title} · ${it.module ?? ""} · ${STATUS_LABEL[it.status]} · ${it.attempts} attempts`}
    >
      {it.lab_id}
    </span>
  );
}

export default function AnalyticsPanel() {
  const { learner } = useLearner();
  const who = learner || "demo";
  const { data: a, loading, error, reload } = useApi<Analytics>(() => api.analytics(who), [who]);
  const [note, setNote] = useState("");
  const [exportNote, setExportNote] = useState("");

  const doExport = async (artifact: string, mime: string) => {
    setExportNote(`exporting ${artifact}…`);
    try {
      await saveArtifact(who, artifact, mime);
      setExportNote(`downloaded osai-${who}-${artifact}`);
    } catch {
      setExportNote(`could not export ${artifact}`);
    }
  };

  const seed = async () => {
    try {
      const r = await api.seedCards(who);
      setNote(`seeded ${r.created.length} practice cards from your weak topics`);
      reload();
    } catch {
      setNote("could not seed cards");
    }
  };

  // group the lab→topic map by OWASP category for the progress map
  const groups: { key: string; name: string; labs: LabProgressItem[] }[] = [];
  const byKey = new Map<string, { key: string; name: string; labs: LabProgressItem[] }>();
  for (const it of a?.labs.items ?? []) {
    const key = it.owasp ?? "other";
    const name = it.owasp_name ?? "Other";
    if (!byKey.has(key)) {
      const g = { key, name, labs: [] as LabProgressItem[] };
      byKey.set(key, g);
      groups.push(g);
    }
    byKey.get(key)!.labs.push(it);
  }

  return (
    <>
      <section className="panel">
        <h2>Exam readiness &amp; analytics</h2>
        <div className="row">
          <button className="ghost" onClick={reload}>
            Refresh
          </button>
          {loading && <span className="muted">loading…</span>}
          {error && <span className="pill bad">grader error</span>}
          <span className="sub">learner {who}</span>
        </div>
        {a && (
          <>
            <div className="row" style={{ gap: 20, marginTop: 6 }}>
              <Stat
                label="readiness"
                value={`${a.readiness.score}`}
                sub={`/ ${a.readiness.of}`}
              />
              <Stat label="xp" value={`${a.xp}`} />
              <Stat
                label="labs passed"
                value={`${a.labs.passed}/${a.labs.total}`}
                sub={`${a.labs.completion_pct}% complete`}
              />
              <Stat
                label="attempts"
                value={`${a.attempts.passed}/${a.attempts.total}`}
                sub="passed / total"
              />
              <Stat
                label="cards due"
                value={`${a.flashcards.due}`}
                sub={`${a.flashcards.total} total`}
              />
            </div>
            <div className="row" style={{ marginTop: 8 }}>
              <span style={{ width: 92 }} className="muted">
                readiness
              </span>
              <Bar mastery={a.readiness.score / a.readiness.of} />
              <span className="sub" style={{ width: 34, textAlign: "right" }}>
                {Math.round((a.readiness.score / a.readiness.of) * 100)}%
              </span>
            </div>
            <div className="sub" style={{ marginTop: 6 }}>
              avg OWASP mastery {pct(a.readiness.avg_owasp_mastery)}% · coverage{" "}
              {pct(a.readiness.owasp_coverage)}% (≥0.5 mastery)
            </div>
          </>
        )}
      </section>

      <section className="panel">
        <h2>Weak topics &amp; next practice</h2>
        <div className="row">
          <button onClick={seed}>Seed practice cards</button>
          <span className="muted">{note}</span>
        </div>
        {a && !a.weak_topics.length && (
          <span className="muted">no weak topics — every tracked topic is at ≥0.5 mastery</span>
        )}
        {a?.weak_topics.map((w) => (
          <div className="row" style={{ gap: 6 }} key={w.tag} title={`${w.family} · ${w.reps} reps`}>
            <span style={{ width: 92 }} className="muted">
              {short(w.tag)}
            </span>
            <Bar mastery={w.mastery} />
            <span className="sub" style={{ flex: 2 }}>
              {w.name}
            </span>
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Missed-framework heatmap (OWASP LLM 2025)</h2>
        {a?.heatmap.map((h) => (
          <div className="row" style={{ gap: 6 }} key={h.tag} title={h.name}>
            <span style={{ width: 70 }} className="muted">
              {short(h.tag)}
            </span>
            <Bar mastery={h.mastery} />
            <span
              className={h.covered ? "pill ok" : "pill"}
              style={h.covered ? undefined : { color: "var(--muted)" }}
              title={`${h.labs_passed}/${h.labs_total} labs passed`}
            >
              {h.labs_passed}/{h.labs_total} labs
            </span>
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Mastery by framework family</h2>
        {a ? (
          <>
            <FamilySection title="OWASP LLM Top 10" entries={a.mastery_by_family.owasp} />
            <FamilySection title="OWASP Agentic threats" entries={a.mastery_by_family.agentic} />
            <FamilySection title="MITRE ATLAS" entries={a.mastery_by_family.atlas} />
            <FamilySection title="Detectors" entries={a.mastery_by_family.detector} />
            {!a.mastery_by_family.owasp.length &&
              !a.mastery_by_family.agentic.length &&
              !a.mastery_by_family.atlas.length &&
              !a.mastery_by_family.detector.length && (
                <span className="muted">no mastery yet — pass a lab to start tracking</span>
              )}
          </>
        ) : (
          <span className="muted">loading…</span>
        )}
      </section>

      <section className="panel">
        <h2>Lab → topic progress map</h2>
        <div className="row">
          <span className="pill ok">passed</span>
          <span className="pill" style={{ color: "var(--acc)", borderColor: "var(--acc)" }}>
            attempted
          </span>
          <span className="pill" style={{ color: "var(--muted)" }}>
            not started
          </span>
        </div>
        {groups.map((g) => (
          <div className="lab" key={g.key}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{g.name}</strong>
              <span className="sub">
                {g.labs.filter((l) => l.status === "passed").length}/{g.labs.length} passed
              </span>
            </div>
            <div className="row" style={{ gap: 6 }}>
              {g.labs.map((it) => (
                <LabChip it={it} key={it.lab_id} />
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Export study pack</h2>
        <p className="sub" style={{ marginTop: 0 }}>
          Offline artifacts generated from your analytics (Marp / Anki / Mermaid). Import the
          deck into Canva or any slide tool; the CSV imports straight into Anki or Quizlet.
        </p>
        <div className="row">
          {EXPORTS.map((e) => (
            <button className="ghost" key={e.artifact} onClick={() => doExport(e.artifact, e.mime)}>
              {e.label}
            </button>
          ))}
        </div>
        {exportNote && <span className="muted">{exportNote}</span>}
      </section>
    </>
  );
}
