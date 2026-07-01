"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Progress } from "@/lib/types";

export default function ProgressPanel({
  learner,
  refreshKey,
}: {
  learner: string;
  refreshKey: number;
}) {
  const [p, setP] = useState<Progress | null>(null);

  const load = useCallback(() => {
    api
      .progress(learner || "demo")
      .then(setP)
      .catch(() => setP(null));
  }, [learner]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const heatmap = p?.weakness_heatmap ? Object.entries(p.weakness_heatmap) : [];

  return (
    <section className="panel">
      <h2>Progress &amp; readiness</h2>
      <div className="row">
        <button className="ghost" onClick={load}>
          Refresh
        </button>
        <span className="muted">
          {p ? `xp ${p.xp} · attempts ${p.attempts.passed}/${p.attempts.total}` : "—"}
        </span>
      </div>
      <div className="row">
        <strong>Readiness</strong>&nbsp;
        <span className="pill">{p?.readiness ? `${p.readiness.score}/${p.readiness.of}` : "–"}</span>
      </div>
      <div>
        {heatmap.map(([id, v]) => (
          <div className="row" style={{ gap: 6 }} key={id}>
            <span style={{ width: 78 }} className="muted">
              {id.replace(":2025", "")}
            </span>
            <div className="bar">
              <span style={{ width: `${Math.round((v.mastery || 0) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        {(p?.badges || []).map((b) => (
          <span className="pill ok" key={b.code} title={b.desc}>
            ★ {b.title}
          </span>
        ))}
        {p && !p.badges.length && <span className="muted">no badges yet</span>}
      </div>
    </section>
  );
}
