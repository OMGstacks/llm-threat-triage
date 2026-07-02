// Typed client for the FastAPI grader. All calls go through /api/* which Next
// proxies to the grader (see next.config.js) — no CORS, URL configurable.
import type {
  Analytics,
  AuditEvent,
  AuthResponse,
  CapstoneBrief,
  CapstoneScore,
  ConsentResponse,
  EvalReport,
  MeResponse,
  RosterRow,
  ExamScore,
  ExamSession,
  ExamSubmitResult,
  Flashcard,
  Health,
  LabSummary,
  LeaderboardRow,
  Progress,
  ReviewCard,
  ReviewResult,
  SubmitResult,
  TutorAnswer,
} from "./types";

export function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

// Bearer mode: attach the token from localStorage. Cookie mode: no token in JS — the
// HttpOnly session cookie travels automatically (credentials: include) and the CSRF
// cookie is echoed as a header (double-submit).
function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const t = window.localStorage.getItem("osai_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function csrfHeader(): Record<string, string> {
  const c = readCookie("osai_csrf");
  return c ? { "X-CSRF-Token": c } : {};
}

async function j<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...opts,
    credentials: "include",
    headers: { ...(opts.headers || {}), ...authHeader(), ...csrfHeader() },
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return (await res.json()) as T;
}

// Raw-text GET (study-pack exports). Uses the same auth so it works in Bearer and cookie
// modes — a plain <a download> would drop the Bearer token, so downloads go through here.
export async function fetchText(path: string): Promise<string> {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    headers: { ...authHeader(), ...csrfHeader() },
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.text();
}

function post<T>(path: string, body: unknown): Promise<T> {
  return j<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function del<T>(path: string): Promise<T> {
  return j<T>(path, { method: "DELETE" });
}

export interface Transcript {
  role: string;
  source: string;
  content: string;
}

export const api = {
  health: () => j<Health>("/health"),
  register: (username: string, password: string) =>
    post<AuthResponse>("/auth/register", { username, password }),
  login: (username: string, password: string) =>
    post<AuthResponse>("/auth/login", { username, password }),
  logout: () => post<{ ok: boolean }>("/auth/logout", {}),
  me: () => j<MeResponse>("/auth/me"),
  getConsent: () => j<ConsentResponse>("/auth/consent"),
  grantConsent: () => post<{ ok: boolean; consented: boolean }>("/auth/consent", {}),
  revokeConsent: () => del<{ ok: boolean; consented: boolean }>("/auth/consent"),
  adminRoster: () => j<RosterRow[]>("/admin/roster"),
  adminReset: (learner: string) => post<{ ok: boolean; reset: string }>(`/admin/reset/${learner}`, {}),
  adminAudit: () => j<{ events: AuditEvent[] }>("/admin/audit"),
  labs: () => j<LabSummary[]>("/labs"),
  submit: (lab: string, learner_id: string, transcript: Transcript[], flag: string) =>
    post<SubmitResult>(`/labs/${lab}/submit`, { learner_id, transcript, flag }),
  tutorAsk: (query: string) => post<TutorAnswer>("/tutor/ask", { query }),
  reviewReport: (finding: Record<string, unknown>, transcript: Transcript[]) =>
    post<ReviewCard>("/reports/review", { finding, transcript }),
  progress: (learner: string) => j<Progress>(`/progress/${learner}`),
  analytics: (learner: string) => j<Analytics>(`/analytics/${learner}`),
  exportArtifact: (learner: string, artifact: string) =>
    fetchText(`/export/${learner}/${artifact}`),
  seedCards: (learner: string) => post<{ created: number[] }>(`/flashcards/${learner}/seed`, {}),
  dueCards: (learner: string) => j<Flashcard[]>(`/flashcards/${learner}/due`),
  reviewCard: (card_id: number, grade: number) =>
    post<ReviewResult>("/flashcards/review", { card_id, grade }),
  leaderboard: () => j<LeaderboardRow[]>("/leaderboard"),
  examStart: (learner_id: string, lab_ids?: string[]) =>
    post<ExamSession>("/exam/start", { learner_id, lab_ids }),
  examSubmit: (
    sid: string,
    lab_id: string,
    transcript: Transcript[],
    flag: string,
    finding: Record<string, unknown>,
  ) => post<ExamSubmitResult>(`/exam/${sid}/submit`, { lab_id, transcript, flag, finding }),
  examScore: (sid: string) => j<ExamScore>(`/exam/${sid}/score`),
  evalReport: (refresh = false) => j<EvalReport>(`/eval${refresh ? "?refresh=1" : ""}`),
  capstone: () => j<CapstoneBrief>("/capstone"),
  capstoneScore: (findings: { owasp_id: string }[], escalation_chain: boolean) =>
    post<CapstoneScore>("/capstone/score", { findings, escalation_chain }),
};
