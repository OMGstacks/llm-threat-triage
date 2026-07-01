"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EvalReport } from "@/lib/types";

const LABELS: Record<string, string> = {
  hallucinated_taxonomy_ids: "Hallucinated taxonomy ids",
  framework_id_validation: "Framework recall (grounded)",
  abstention_pass_rate: "Abstention pass rate",
  refusal_pass_rate: "Refusal pass rate",
  lab_answer_leakage_failures: "Flag-leakage failures",
};

export default function EvalPanel() {
  const [rep, setRep] = useState<EvalReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((refresh = false) => {
    setBusy(true);
    setError(null);
    api
      .evalReport(refresh)
      .then(setRep)
      .catch(() => setError("could not reach the grader"))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  return (
    <>
      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <h2>Evaluation — the tutor ship gate (04-evaluation-harness)</h2>
        <div className="row">
          <button onClick={() => load(true)} disabled={busy}>
            {busy ? "running…" : "Re-run gate"}
          </button>
          {rep && (
            <span className={`pill ${rep.passed ? "ok" : "bad"}`}>
              {rep.passed ? "SHIP GATE: PASS" : "SHIP GATE: FAIL"}
            </span>
          )}
          {rep && <span className="muted">{rep.total} items · {rep.ran_ms} ms · {rep.llm.enabled ? `AI (${rep.llm.model_quality})` : "offline extractive"}</span>}
          {error && <span className="pill bad">{error}</span>}
        </div>
        {rep &&
          Object.entries(rep.metrics).map(([k, v]) => (
            <div className="row" style={{ gap: 8 }} key={k}>
              <span className={`pill ${rep.gate[k] ? "ok" : "bad"}`} style={{ width: 22, textAlign: "center" }}>
                {rep.gate[k] ? "✓" : "✗"}
              </span>
              <span style={{ flex: 1 }}>{LABELS[k] || k}</span>
              <strong>{v}</strong>
            </div>
          ))}
        {rep && (
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Soft (tracked, not gated): recall exact-id match{" "}
            {rep.soft_metrics.recall_id_match_rate}. The generative tutor lifts this.
          </div>
        )}
      </section>
    </>
  );
}
