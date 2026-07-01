"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";
import { LearnerProvider, useLearner } from "@/lib/learner";

// Learner consent for AI transcript processing. Only shown when the operator has enabled
// transcript judging (health.data_handling.transcripts_enabled) — otherwise it's moot.
function ConsentToggle({ retentionDays }: { retentionDays?: number }) {
  const [consented, setConsented] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getConsent().then((c) => setConsented(c.consented)).catch(() => setConsented(null));
  }, []);

  if (consented === null) return null;
  const toggle = async () => {
    setBusy(true);
    try {
      const r = consented ? await api.revokeConsent() : await api.grantConsent();
      setConsented(r.consented);
    } catch {
      /* leave state unchanged on error */
    } finally {
      setBusy(false);
    }
  };
  return (
    <label
      className="sub"
      title={`Consent to AI processing of your (redacted) attack transcripts for report critique. Retained ≤ ${retentionDays ?? 7} days, then purged.`}
      style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}
    >
      <input type="checkbox" checked={consented} disabled={busy} onChange={toggle} />
      AI critique consent
    </label>
  );
}

const NAV = [
  { href: "/", label: "Home" },
  { href: "/labs", label: "Labs" },
  { href: "/tutor", label: "Tutor" },
  { href: "/progress", label: "Progress" },
  { href: "/exam", label: "Exam" },
  { href: "/report", label: "Report" },
  { href: "/capstone", label: "Capstone" },
  { href: "/eval", label: "Eval" },
];

function Header({ health, offline }: { health: Health | null; offline: boolean }) {
  const { learner, setLearner, authed, logout } = useLearner();
  const path = usePathname();
  const [role, setRole] = useState("learner");
  const ai = health?.llm?.enabled ? "AI tutor ✓" : "AI tutor off";

  useEffect(() => {
    if (authed && health?.auth_enabled) {
      api.me().then((m) => setRole(m.role)).catch(() => setRole("learner"));
    } else {
      setRole("learner");
    }
  }, [authed, health?.auth_enabled]);

  const nav = role === "instructor" ? [...NAV, { href: "/admin", label: "Admin" }] : NAV;

  return (
    <header>
      <h1>
        OSAI Prep Studio <span className="sub">AI-300 / OSAI</span>
      </h1>
      <nav className="row" style={{ gap: 12, margin: 0 }}>
        {nav.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={path === n.href ? undefined : "sub"}
            style={path === n.href ? { fontWeight: 600 } : undefined}
          >
            {n.label}
          </Link>
        ))}
      </nav>
      <span style={{ flex: 1 }} />
      {health?.auth_enabled ? (
        authed ? (
          <span className="row" style={{ gap: 8, margin: 0 }}>
            <span className="sub">
              signed in as <strong>{learner}</strong>
            </span>
            {health?.data_handling?.transcripts_enabled ? (
              <ConsentToggle retentionDays={health.data_handling.retention_days} />
            ) : null}
            <button className="ghost" style={{ padding: "1px 8px" }} onClick={logout}>
              Sign out
            </button>
          </span>
        ) : (
          <Link href="/login" style={{ fontWeight: 600 }}>
            Sign in
          </Link>
        )
      ) : (
        <label>
          learner&nbsp;
          <input value={learner} size={12} onChange={(e) => setLearner(e.target.value)} />
        </label>
      )}
      <span className="sub">
        {offline ? "grader offline" : health ? `${health.labs.length} labs · ${ai}` : "connecting…"}
      </span>
    </header>
  );
}

function ConnectionBanner({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      style={{
        background: "rgba(248,81,73,0.12)",
        borderBottom: "1px solid var(--bad)",
        color: "var(--ink)",
        padding: "8px 20px",
        fontSize: 13,
      }}
    >
      <strong style={{ color: "var(--bad)" }}>Can’t reach the grader.</strong> Start it with{" "}
      <code>uvicorn osai_spine.api:app --port 8077</code> (or set <code>OSAI_API_URL</code>), then{" "}
      <button className="ghost" style={{ padding: "1px 8px" }} onClick={onRetry}>
        retry
      </button>
      .
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  const checkHealth = () => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setOffline(false);
      })
      .catch(() => {
        setHealth(null);
        setOffline(true);
      });
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <LearnerProvider>
      <Header health={health} offline={offline} />
      {offline && <ConnectionBanner onRetry={checkHealth} />}
      <main>{children}</main>
    </LearnerProvider>
  );
}
