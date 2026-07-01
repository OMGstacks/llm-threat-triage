"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LeaderboardRow } from "@/lib/types";

export default function LeaderboardPanel({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<LeaderboardRow[]>([]);

  const load = useCallback(() => {
    api
      .leaderboard()
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  return (
    <section className="panel">
      <h2>Leaderboard</h2>
      <div className="row">
        <button className="ghost" onClick={load}>
          Refresh
        </button>
      </div>
      {rows.length ? (
        rows.map((r) => (
          <div className="row" style={{ gap: 6 }} key={r.learner_id}>
            <span className="muted" style={{ width: 26 }}>
              #{r.rank}
            </span>
            <strong style={{ flex: 1 }}>{r.learner_id}</strong>
            <span className="pill">xp {r.xp}</span>
            <span className="pill">{r.passed} passed</span>
            <span className="pill">{r.badges}★</span>
          </div>
        ))
      ) : (
        <span className="muted">no entries yet</span>
      )}
    </section>
  );
}
