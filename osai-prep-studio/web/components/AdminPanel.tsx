"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditEvent, RosterRow } from "@/lib/types";

export default function AdminPanel() {
  const [roster, setRoster] = useState<RosterRow[] | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    setError(null);
    api.adminRoster().then(setRoster).catch(() => setError("instructors only (or not signed in)"));
    api.adminAudit().then((r) => setAudit(r.events)).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const reset = async (learner: string) => {
    if (!window.confirm(`Reset all progress for ${learner}? The account is kept.`)) return;
    try {
      await api.adminReset(learner);
      setNote(`reset ${learner}`);
      load();
    } catch {
      setNote(`could not reset ${learner}`);
    }
  };

  if (error) {
    return (
      <section className="panel">
        <h2>Instructor console</h2>
        <span className="pill bad">{error}</span>
      </section>
    );
  }

  return (
    <>
      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <h2>Instructor console — cohort roster</h2>
        <div className="row">
          <button className="ghost" onClick={load}>
            Refresh
          </button>
          <span className="muted">{note}</span>
        </div>
        {roster ? (
          roster.map((r) => (
            <div className="row" style={{ gap: 8 }} key={r.learner_id}>
              <strong style={{ width: 140 }}>{r.learner_id}</strong>
              <span className="pill">{r.role}</span>
              <span className="pill">xp {r.xp}</span>
              <span className="pill">{r.passed} passed</span>
              <span className="pill">readiness {r.readiness}</span>
              <span className="pill">{r.badges}★</span>
              <button className="ghost" onClick={() => reset(r.learner_id)}>
                reset
              </button>
            </div>
          ))
        ) : (
          <span className="muted">loading…</span>
        )}
        {roster && !roster.length && <span className="muted">no learners yet</span>}
      </section>

      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <h2>Audit log</h2>
        <div className="out">
          {audit.length
            ? audit
                .map((e) => `${e.event}  ·  ${e.actor ?? "-"}  ·  ${JSON.stringify(e.detail)}`)
                .join("\n")
            : "no events"}
        </div>
      </section>
    </>
  );
}
