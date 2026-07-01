"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";
import { LearnerProvider, useLearner } from "@/lib/learner";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/labs", label: "Labs" },
  { href: "/tutor", label: "Tutor" },
  { href: "/progress", label: "Progress" },
  { href: "/exam", label: "Exam" },
  { href: "/capstone", label: "Capstone" },
];

function Header() {
  const { learner, setLearner } = useLearner();
  const [health, setHealth] = useState<Health | null>(null);
  const path = usePathname();

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const ai = health?.llm?.enabled ? "AI tutor ✓" : "AI tutor off";

  return (
    <header>
      <h1>
        OSAI Prep Studio <span className="sub">AI-300 / OSAI</span>
      </h1>
      <nav className="row" style={{ gap: 12, margin: 0 }}>
        {NAV.map((n) => (
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
      <label>
        learner&nbsp;
        <input value={learner} size={12} onChange={(e) => setLearner(e.target.value)} />
      </label>
      <span className="sub">
        {health ? `${health.labs.length} labs · ${ai}` : "connecting…"}
      </span>
    </header>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <LearnerProvider>
      <Header />
      <main>{children}</main>
    </LearnerProvider>
  );
}
