# Projects in this repo

This repo holds more than the flagship project the root `README.md` describes. This file is
the self-index the root README doesn't provide: one entry per real, governed project, plus a
lighter entry for the tool-config directory that isn't one. See each project's own docs for
detail — this file only orients.

## `projects/llm-log-triage` — the flagship

The project the root `README.md`, root `LICENSE`, and root `.github/workflows/ci.yml` are
about. A tested pipeline that ingests LLM interaction logs, detects adversarial-ML attack
patterns mapped to OWASP LLM Top 10 / MITRE ATLAS, and answers investigative questions with
SQL.

- **Governance doc:** none beyond its own `README.md` (`projects/llm-log-triage/README.md`).
- **CI workflow:** `.github/workflows/ci.yml` — runs on every push/PR to `main`/`master`. A
  second workflow, `.github/workflows/root-cognition-substrate.yml`, gates the repo-root
  `.cognition/` toolkit's `memory/`, `codebase-index/`, and `active-work/` subsystems (see
  below) — path-filtered so it's silent on ordinary pipeline/detector changes.
- **Test entrypoint:** `python -m pytest -q` from `projects/llm-log-triage/`.
- **Memory file:** `.cognition/memory/MEMORY.md` (repo root, not nested under
  `projects/llm-log-triage/`) — the Cognition OS toolkit install here is physically at the
  repo root but conceptually scoped to this project (its own install commit says so; root
  `ci.yml` has exactly one job, scoped entirely to it — `README.md` also links to this
  file, `PROJECTS.md`, since it covers more than one project). No `feedback_*.md` lessons
  yet — see that file's Current State for why.
- **Self-index:** `docs/codebase_index/cognition_inventory.md` — generated, drift-checked
  inventory of which of the toolkit's own 5 subsystems are instantiated vs. still
  template-only (regenerate: `python3 cli.py --write --only cognition_inventory` from
  `.cognition/codebase-index/`).

## `cc-master-learning-center` — ISC2 Certified in Cybersecurity exam-prep

A content-authoring/validation system with a JSON fact store: quiz generation, mock exams,
cram sheets, a learner dashboard — no deployed service, no pipelines.

- **Governance doc:** `cc-master-learning-center/CLAUDE.md` (generic Cognition OS toolkit
  CORE rules; not yet customized with project-specific content).
- **CI workflow:** `.github/workflows/cc-cognition-substrate.yml` — covers the toolkit's
  `memory/`, `friction/`, `codebase-index/`, and `active-work/` subsystems (memory gates,
  toolkit self-tests, a codebase-index drift check). Deliberately does NOT cover
  `ci-governance/` or `.claude/` — neither is instantiated/functional yet, see this
  project's own memory file. **Important:** this project's actual application source
  (`spine/cc_spine/*.py`, its test suite, and a `cc-spine.yml` CI workflow covering it)
  exists only on the unmerged `claude/cc-cert-learning-plan-xqo5g7` branch, not on `main` —
  do not assume it is present here until that branch merges.
- **Test entrypoint:** none on `main` yet (see above); on the unmerged branch it is
  `python -m pytest` from `cc-master-learning-center/spine/`.
- **Memory file:** `cc-master-learning-center/.cognition/memory/MEMORY.md` — the first
  instantiated (non-template) memory file in the repo, seeded with feedback lessons from this
  project's PR-10/PR-11 development series.
- **Self-index:** `cc-master-learning-center/docs/codebase_index/cognition_inventory.md` —
  generated, drift-checked inventory of which of the toolkit's own 5 subsystems are
  instantiated vs. still template-only (regenerate: `python3 cli.py --write --only
  cognition_inventory` from `cc-master-learning-center/.cognition/codebase-index/`).

## `osai-prep-studio` — spec-doc-heavy exam-prep platform (FastAPI/Next sibling)

A second, independently-built exam-prep platform with its own `spine/` (FastAPI backend) and
`web/` (Next.js frontend), including a real beta-deploy runbook (Docker Compose + Caddy/TLS).

- **Governance doc:** a chronological series of 25+ numbered planning docs at its root
  (`00a-vision.md` … `25-fact-store-epic.md` and beyond) — its own decision-trail convention,
  distinct from the `CLAUDE.md`/memory pattern used elsewhere in this repo, and deliberately
  left in place (not replaced) by the cognition-substrate port. Also carries a Cognition OS
  toolkit install (`.cognition/`, `.claude/`) — `memory/`, `codebase-index/`, and
  `active-work/` are now instantiated (see below); `friction/` and `ci-governance/` remain
  template-only.
- **CI workflow:** `.github/workflows/osai-spine.yml` (path-filtered to
  `osai-prep-studio/spine/**`, `osai-prep-studio/web/**`, `osai-prep-studio/packages/**`,
  `reference/**`, and one shared file in `projects/llm-log-triage`). A second workflow,
  `.github/workflows/osai-cognition-substrate.yml`, gates the toolkit's instantiated
  subsystems separately.
- **Test entrypoint:** `python -m pytest` from `osai-prep-studio/spine/` for the backend. The
  frontend (`osai-prep-studio/web/`) has no `test` script in `package.json` — only `lint` and
  `typecheck`; there is no frontend test suite yet.
- **Memory file:** `osai-prep-studio/.cognition/memory/MEMORY.md` — instantiated in the Slice
  5 port. No `feedback_*.md` lessons yet (same honest-gap note as the root project above).
- **Self-index:** `osai-prep-studio/docs/codebase_index/cognition_inventory.md` — same
  generator pattern as the other two projects (regenerate: `python3 cli.py --write --only
  cognition_inventory` from `osai-prep-studio/.cognition/codebase-index/`).

## `red-team/` — tool configs, not a governed project

Configuration for third-party red-teaming tools (`garak`, `promptfoo`, `pyrit`) plus a local
harness script. No CI workflow, no CLAUDE.md, no memory file — it's a toolbox, not a project
with its own lifecycle.

## `docs/` and `reference/`

Shared assets referenced by one or more of the projects above (architecture diagrams, OWASP
LLM Top 10 / MITRE ATLAS reference material). Not independently governed.
