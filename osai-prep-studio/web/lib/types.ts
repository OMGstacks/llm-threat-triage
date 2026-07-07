// Response shapes from the FastAPI grader (osai_spine.api). Kept in sync with the
// server's public (answer-redacted) contract.

export interface AuthResponse {
  learner_id: string;
  token: string;
}

export interface MeResponse {
  auth_enabled: boolean;
  learner_id: string | null;
  role: string;
}

export interface RosterRow {
  learner_id: string;
  role: string;
  xp: number;
  passed: number;
  attempts: number;
  readiness: number;
  badges: number;
}

export interface AuditEvent {
  ts: number;
  event: string;
  actor: string | null;
  detail: Record<string, unknown>;
}

export interface EvalReport {
  total: number;
  by_bank: Record<string, number>;
  metrics: Record<string, number>;
  soft_metrics: Record<string, number>;
  gate: Record<string, boolean>;
  passed: boolean;
  ran_ms: number;
  llm: { enabled: boolean; model_quality: string };
}

export interface Health {
  status: string;
  labs: string[];
  tutor_corpus_chunks: number;
  auth_enabled?: boolean;
  cookie_auth?: boolean;
  llm: {
    enabled: boolean;
    transcripts_enabled: boolean;
    sdk_installed: boolean;
    key_present: boolean;
    model_quality: string;
    model_bulk: string;
  };
  data_handling?: {
    transcripts_enabled: boolean;
    consent_required: boolean;
    retention_days: number;
  };
}

export interface ReviewDimension {
  weight: number;
  score: number;
  points: number;
}

export interface ReviewCard {
  total: number;
  passed: boolean;
  dimensions: Record<string, ReviewDimension>;
  classification: {
    learner_owasp: string | null;
    suggested_owasp: string | null;
    match: boolean;
    valid: boolean;
  };
  invalid_ids: string[];
  feedback: string[];
  narrative_critique?: string | null;
  narrative_note?: string;
}

export interface ConsentResponse {
  auth_enabled: boolean;
  learner_id?: string;
  consented: boolean;
  policy?: { transcripts_enabled: boolean; consent_required: boolean; retention_days: number };
}

export interface LabSummary {
  id: string;
  title: string;
  difficulty: string | null;
}

export interface Badge {
  code: string;
  title: string;
  desc: string;
}

export interface SubmitResult {
  lab_id: string;
  passed: boolean;
  signal_a: boolean;
  signal_b: boolean;
  feedback: string[];
  progress?: { xp: number; attempts: { total: number; passed: number } };
  new_badges?: Badge[];
}

export interface Citation {
  source: string;
  title: string;
  tier: string;
  section: string | null;
  score: number;
}

export interface TutorAnswer {
  abstained: boolean;
  refused: boolean;
  generative?: boolean;
  answer: string;
  citations: Citation[];
  top_score?: number;
}

export interface Readiness {
  score: number;
  of: number;
  avg_owasp_mastery: number;
  owasp_coverage: number;
}

export interface HeatmapEntry {
  name: string;
  mastery: number;
}

export interface Progress {
  learner_id: string;
  xp: number;
  attempts: { total: number; passed: number };
  mastery: Record<string, { mastery: number; reps: number }>;
  badges: Badge[];
  readiness?: Readiness;
  weakness_heatmap?: Record<string, HeatmapEntry>;
}

export interface LeaderboardRow {
  rank: number;
  learner_id: string;
  xp: number;
  passed: number;
  attempts: number;
  badges: number;
  readiness: number;
}

export interface FamilyMastery {
  tag: string;
  name: string;
  mastery: number;
  reps: number;
}

export interface HeatCell {
  tag: string;
  name: string;
  mastery: number;
  labs_total: number;
  labs_passed: number;
  covered: boolean;
}

export interface WeakTopic {
  tag: string;
  name: string;
  family: string;
  mastery: number;
  reps: number;
}

export interface LabProgressItem {
  lab_id: string;
  title: string;
  difficulty: string | null;
  module: string | null;
  owasp: string | null;
  owasp_name: string | null;
  framework_tags: string[];
  attempts: number;
  passed_count: number;
  status: "passed" | "attempted" | "not_started";
  mastery: number;
}

export interface Analytics {
  learner_id: string;
  xp: number;
  attempts: { total: number; passed: number };
  readiness: Readiness;
  mastery_by_family: {
    owasp: FamilyMastery[];
    agentic: FamilyMastery[];
    atlas: FamilyMastery[];
    detector: FamilyMastery[];
  };
  heatmap: HeatCell[];
  weak_topics: WeakTopic[];
  flashcards: { due: number; total: number };
  labs: {
    total: number;
    passed: number;
    attempted: number;
    completion_pct: number;
    items: LabProgressItem[];
  };
}

export interface CapstoneBrief {
  events: { role: string; source: string; content: string }[];
  task: string;
}

export interface ExamSession {
  session_id: string;
  learner_id: string;
  targets: string[];
  started_at: number;
  duration_seconds: number;
  deadline: number;
  submitted: string[];
}

export interface ExamSubmitResult {
  lab_id?: string;
  lab_passed?: boolean;
  report_total?: number;
  remaining?: number;
  rejected?: string;
}

export interface RetakeItem {
  lab: string;
  skill: string;
  reason: string;
  recommend: string;
}

export interface ExamScore {
  session_id: string;
  score: number;
  of: number;
  passed: boolean;
  findings: { passed: number; of: number; weight: number };
  report: { avg_pct: number; weight: number };
  missed_paths: string[];
  retake_plan?: RetakeItem[];
}

export interface Flashcard {
  id: number;
  skill_tag: string;
  prompt: string;
  answer: string;
  interval_days: number;
  reps: number;
  due_ts: number;
}

export interface ReviewResult {
  card_id: number;
  interval_days: number;
  reps: number;
  ef: number;
}

export interface CapstoneScore {
  score: number;
  of: number;
  passed: boolean;
  precision: number;
  recall: number;
  f1: number;
  escalation_correct: boolean;
  counts: { submitted: number; correct: number; missed: number; false_positive: number };
}

// Narrated-lesson render manifest (produced offline by `osai_spine narrate`;
// served statically from /public/lessons/<id>.manifest.json). The lesson player is
// pure presentation — it never grades.
export interface LessonSegment {
  id: string;
  text: string;
  chars: number;
  start: number;
  end: number;
  est_seconds: number;
  audio: string;
  slide?: string;
}

export interface LessonManifest {
  lesson_id: string;
  title: string;
  voice: string;
  provider: string;
  kind: string;
  segments: LessonSegment[];
  segment_count: number;
  total_chars: number;
  est_duration: string;
  est_seconds: number;
  est_cost_usd: number;
  rate_per_million_usd: number;
}

// The lessons catalog, served statically from /public/lessons/index.json — built offline
// by the course-side lessons builder (osai_spine.lessons). The /lessons index lists these.
export interface LessonCard {
  lesson_id: string;
  title: string;
  track: number;
  module: string | null;
  frameworks: string[];
  detector: string | null;
  segment_count: number;
  est_duration: string;
  est_seconds: number;
}

export interface LessonIndex {
  lessons: LessonCard[];
  count: number;
}
