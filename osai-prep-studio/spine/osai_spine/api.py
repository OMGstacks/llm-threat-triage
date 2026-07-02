"""Production FastAPI grader app — same contract as the stdlib ``service.py``.

    uvicorn osai_spine.api:app --host 0.0.0.0 --port 8077

Reuses ``GraderState`` / ``ChallengeValidator`` and the answer-redaction from
``service.py``; learner responses never include the expected detector/OWASP id
(13-platform-threat-model.md). The stdlib service remains the zero-dependency
reference; this is the deployable variant.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import hmac
import time

from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import audit as audit_mod
from . import auth as auth_mod
from . import datahandling
from . import engine
from . import llm as llm_mod
from .capstone import TriageCapstone
from .exam import ExamSimulator
from .goldset import GoldSetRunner
from .progress import BADGE_DEFS, ProgressStore
from . import report as report_mod
from .report import ReportReviewer
from .service import GraderState, _public_manifest
from .tutor import Tutor
from .validator import ChallengeValidator

_LABS_DIR = Path(__file__).resolve().parent.parent / "labs"
_STATIC_DIR = Path(__file__).resolve().parent / "static"


class Event(BaseModel):
    role: str
    source: str = "chat_ui"
    content: str = ""
    tool_call: Optional[str] = None  # for causal-chain (Signal C) grading of agentic labs


class SubmitRequest(BaseModel):
    learner_id: str
    transcript: List[Event] = Field(default_factory=list)
    flag: str = ""
    attempt: int = 0


class AskRequest(BaseModel):
    query: str
    mode: str = "tutor"


class ReviewRequest(BaseModel):
    finding: dict
    transcript: List[Event] = Field(default_factory=list)
    learner_id: str = ""  # used only to attribute the optional AI critique / consent


class ExamStartRequest(BaseModel):
    learner_id: str
    lab_ids: Optional[List[str]] = None
    duration_seconds: Optional[int] = None


class ExamSubmitRequest(BaseModel):
    lab_id: str
    transcript: List[Event] = Field(default_factory=list)
    flag: str = ""
    finding: dict = Field(default_factory=dict)


class ReviewCardRequest(BaseModel):
    card_id: int
    grade: int


class CapstoneSubmitRequest(BaseModel):
    findings: List[dict] = Field(default_factory=list)
    escalation_chain: bool = False


class AuthRequest(BaseModel):
    username: str
    password: str


def _dump(event: Event) -> dict:
    return event.model_dump() if hasattr(event, "model_dump") else event.dict()


def _set_session_cookies(response: Response, token: str) -> None:
    """In cookie mode, set the HttpOnly session cookie + a readable CSRF cookie
    (double-submit). No-op in Bearer mode."""
    if not auth_mod.cookie_auth_enabled():
        return
    secure = auth_mod.cookie_secure()
    response.set_cookie(auth_mod.SESSION_COOKIE, token, httponly=True, secure=secure,
                        samesite="lax", path="/", max_age=auth_mod.TOKEN_TTL)
    response.set_cookie(auth_mod.CSRF_COOKIE, auth_mod.new_csrf(), httponly=False,
                        secure=secure, samesite="lax", path="/", max_age=auth_mod.TOKEN_TTL)


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(auth_mod.SESSION_COOKIE, path="/")
    response.delete_cookie(auth_mod.CSRF_COOKIE, path="/")


def create_app(seed: str | None = None, labs_dir=None) -> FastAPI:
    auth_mod.enforce_deploy_policy()  # fail closed on an insecure public deployment
    state = GraderState(
        seed or os.environ.get("OSAI_SERVER_SEED", "dev-seed-change-me"),
        labs_dir or _LABS_DIR,
    )
    app = FastAPI(title="OSAI Prep Studio — Grader", version="0.1.0")
    provider = llm_mod.LLMProvider() if llm_mod.enabled() else None
    tutor = Tutor(registry=state.registry, llm=provider)
    progress = ProgressStore(os.environ.get("OSAI_DB", ":memory:"))
    reviewer = ReportReviewer(state.registry)
    exam = ExamSimulator(state, reviewer, progress)
    capstone = TriageCapstone()
    auth = auth_mod.AuthStore(
        os.environ.get("OSAI_AUTH_DB", ":memory:"),
        secret=os.environ.get("OSAI_AUTH_SECRET") or state.seed,
    )
    audit_log = audit_mod.AuditLog(os.environ.get("OSAI_AUDIT_DB", ":memory:"))
    transcript_store = datahandling.TranscriptStore(
        os.environ.get("OSAI_TRANSCRIPT_DB", ":memory:")
    )

    def resolve_learner(body_learner: str, authorization, cookie_token=None):
        """When auth is enabled, the effective learner is the verified token subject —
        a user can only act as themselves. The token comes from the Bearer header, or
        (in cookie mode) the HttpOnly session cookie. When auth is disabled (default),
        the client-supplied id is used, so offline/demo/CI flows are unchanged."""
        if not auth_mod.auth_enabled():
            return body_learner
        token = ""
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        elif auth_mod.cookie_auth_enabled() and cookie_token:
            token = cookie_token
        sub = auth.verify_token(token)
        if not sub:
            raise HTTPException(status_code=401, detail="authentication required")
        return sub

    @app.middleware("http")
    async def _csrf_guard(request: Request, call_next):
        """Double-submit CSRF check: in cookie mode, a state-changing request that
        relies on the session cookie (browser) must echo the CSRF cookie in an
        X-CSRF-Token header. Bearer/API requests and login/register are exempt."""
        if auth_mod.cookie_auth_enabled() and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            has_bearer = request.headers.get("authorization", "").lower().startswith("bearer ")
            has_cookie = bool(request.cookies.get(auth_mod.SESSION_COOKIE))
            exempt = request.url.path in ("/auth/login", "/auth/register")
            if has_cookie and not has_bearer and not exempt:
                header = request.headers.get("x-csrf-token", "")
                cookie = request.cookies.get(auth_mod.CSRF_COOKIE, "")
                if not header or not cookie or not hmac.compare_digest(header, cookie):
                    return JSONResponse({"detail": "CSRF token missing or invalid"}, status_code=403)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (_STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "engine": engine.ENGINE_PATH,
            "labs": sorted(state.labs),
            "tutor_corpus_chunks": len(tutor.library.chunks),
            "llm": llm_mod.status(),
            "data_handling": datahandling.policy_status(transcript_store),
            "auth_enabled": auth_mod.auth_enabled(),
            "cookie_auth": auth_mod.cookie_auth_enabled(),
        }

    @app.post("/auth/register")
    def auth_register(req: AuthRequest, response: Response):
        try:
            user = auth.register(req.username, req.password)
        except auth_mod.AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        audit_log.record(audit_mod.AUTH_REGISTER, user)
        token = auth.issue_token(user)
        _set_session_cookies(response, token)
        return {"learner_id": user, "token": token}

    @app.post("/auth/login")
    def auth_login(req: AuthRequest, response: Response):
        try:
            ok = auth.authenticate(req.username, req.password)
        except auth_mod.LoginThrottled:
            audit_log.record(audit_mod.AUTH_LOGIN_THROTTLED, req.username)
            raise HTTPException(status_code=429, detail="too many attempts; try again later")
        if not ok:
            audit_log.record(audit_mod.AUTH_LOGIN_FAILURE, req.username)
            raise HTTPException(status_code=401, detail="invalid credentials")
        audit_log.record(audit_mod.AUTH_LOGIN, req.username)
        token = auth.issue_token(req.username)
        _set_session_cookies(response, token)
        return {"learner_id": req.username, "token": token}

    @app.post("/auth/logout")
    def auth_logout(response: Response, authorization: str | None = Header(default=None),
                    osai_session: str | None = Cookie(default=None)):
        learner = resolve_learner("", authorization, osai_session) if auth_mod.auth_enabled() else ""
        if learner:
            auth.revoke_sessions(learner)  # invalidates every outstanding token
            audit_log.record(audit_mod.AUTH_LOGOUT, learner)
        _clear_session_cookies(response)
        return {"ok": True}

    @app.get("/auth/me")
    def auth_me(authorization: str | None = Header(default=None),
                osai_session: str | None = Cookie(default=None)):
        if not auth_mod.auth_enabled():
            return {"auth_enabled": False, "learner_id": None, "role": "learner"}
        learner = resolve_learner("", authorization, osai_session)
        return {"auth_enabled": True, "learner_id": learner, "role": auth.role(learner)}

    @app.get("/auth/events")
    def auth_events(authorization: str | None = Header(default=None),
                    osai_session: str | None = Cookie(default=None)):
        # a learner's own recent audit trail (instructor-wide view is a future admin role)
        if not auth_mod.auth_enabled():
            return {"events": []}
        return {"events": audit_log.recent(50, actor=resolve_learner("", authorization, osai_session))}

    # --- transcript-processing consent (learner acts on self) -------------
    @app.get("/auth/consent")
    def get_consent(authorization: str | None = Header(default=None),
                    osai_session: str | None = Cookie(default=None)):
        """A learner's consent state for AI transcript processing + the current policy."""
        policy = datahandling.policy_status(transcript_store)
        if not auth_mod.auth_enabled():
            return {"auth_enabled": False, "consented": False, "policy": policy}
        learner = resolve_learner("", authorization, osai_session)
        return {"auth_enabled": True, "learner_id": learner,
                "consented": transcript_store.has_consent(learner), "policy": policy}

    @app.post("/auth/consent")
    def grant_consent(authorization: str | None = Header(default=None),
                      osai_session: str | None = Cookie(default=None)):
        if not auth_mod.auth_enabled():
            raise HTTPException(status_code=400, detail="consent requires OSAI_AUTH")
        learner = resolve_learner("", authorization, osai_session)
        transcript_store.record_consent(learner)
        audit_log.record(datahandling.TRANSCRIPT_CONSENT_GRANT, learner, {})
        return {"ok": True, "consented": True}

    @app.delete("/auth/consent")
    def revoke_consent(authorization: str | None = Header(default=None),
                       osai_session: str | None = Cookie(default=None)):
        if not auth_mod.auth_enabled():
            raise HTTPException(status_code=400, detail="consent requires OSAI_AUTH")
        learner = resolve_learner("", authorization, osai_session)
        transcript_store.revoke_consent(learner)
        audit_log.record(datahandling.TRANSCRIPT_CONSENT_REVOKE, learner, {})
        return {"ok": True, "consented": False}

    # --- instructor/admin (role-gated) ------------------------------------
    def require_instructor(authorization, cookie_token):
        if not auth_mod.auth_enabled():
            raise HTTPException(status_code=403, detail="admin requires OSAI_AUTH")
        learner = resolve_learner("", authorization, cookie_token)  # 401 if unauthenticated
        if not auth.is_instructor(learner):
            raise HTTPException(status_code=403, detail="instructor role required")
        return learner

    def _roster_row(lid: str) -> dict:
        att = progress.attempts(lid)
        return {
            "learner_id": lid, "role": auth.role(lid), "xp": progress.xp(lid),
            "passed": att["passed"], "attempts": att["total"],
            "readiness": progress.readiness(lid, state.registry)["score"],
            "badges": len(progress.badges(lid)),
        }

    @app.get("/admin/roster")
    def admin_roster(authorization: str | None = Header(default=None),
                     osai_session: str | None = Cookie(default=None)):
        require_instructor(authorization, osai_session)
        ids = sorted(set(auth.usernames()) | set(progress.learners()))
        rows = [_roster_row(lid) for lid in ids]
        rows.sort(key=lambda r: (-r["xp"], r["learner_id"]))
        return rows

    @app.get("/admin/progress/{learner_id}")
    def admin_progress(learner_id: str, authorization: str | None = Header(default=None),
                       osai_session: str | None = Cookie(default=None)):
        require_instructor(authorization, osai_session)
        return progress.summary(learner_id, state.registry)

    @app.post("/admin/reset/{learner_id}")
    def admin_reset(learner_id: str, authorization: str | None = Header(default=None),
                    osai_session: str | None = Cookie(default=None)):
        actor = require_instructor(authorization, osai_session)
        progress.reset(learner_id)
        audit_log.record(audit_mod.ADMIN_RESET, actor, {"target": learner_id})
        return {"ok": True, "reset": learner_id}

    @app.get("/admin/audit")
    def admin_audit(limit: int = 100, authorization: str | None = Header(default=None),
                    osai_session: str | None = Cookie(default=None)):
        require_instructor(authorization, osai_session)
        return {"events": audit_log.recent(limit)}

    @app.get("/admin/export")
    def admin_export(authorization: str | None = Header(default=None),
                     osai_session: str | None = Cookie(default=None)):
        require_instructor(authorization, osai_session)
        ids = sorted(set(auth.usernames()) | set(progress.learners()))
        return {"learners": [progress.summary(lid, state.registry) for lid in ids]}

    @app.get("/catalog")
    def catalog():
        r = state.registry
        return {
            "detectors": r.detector_names(),
            "owasp_llm_2025": r.owasp,
            "owasp_agentic": r.agentic,
        }

    @app.get("/labs")
    def labs():
        return [
            {"id": m["id"], "title": m["title"], "difficulty": m.get("difficulty")}
            for m in state.labs.values()
        ]

    @app.get("/labs/{lab_id}")
    def lab(lab_id: str):
        manifest = state.labs.get(lab_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="no such lab")
        return _public_manifest(manifest)

    @app.post("/labs/{lab_id}/submit")
    def submit(lab_id: str, req: SubmitRequest, authorization: str | None = Header(default=None),
               osai_session: str | None = Cookie(default=None)):
        manifest = state.labs.get(lab_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="no such lab")
        learner = resolve_learner(req.learner_id, authorization, osai_session)
        transcript = [_dump(e) for e in req.transcript]
        result = ChallengeValidator(manifest).grade(
            transcript, req.flag, state.seed, learner, req.attempt
        )
        feedback = result.public_feedback()
        feedback["progress"] = progress.record_attempt(learner, manifest, result)
        new_badges = progress.award_badges(learner, state.registry)
        if new_badges:
            feedback["new_badges"] = new_badges
        audit_log.record(audit_mod.LAB_SUBMIT, learner, {"lab": lab_id, "passed": result.passed})
        return feedback

    @app.get("/progress/{learner_id}")
    def get_progress(learner_id: str, authorization: str | None = Header(default=None),
                     osai_session: str | None = Cookie(default=None)):
        return progress.summary(resolve_learner(learner_id, authorization, osai_session), state.registry)

    @app.get("/analytics/{learner_id}")
    def get_analytics(learner_id: str, authorization: str | None = Header(default=None),
                      osai_session: str | None = Cookie(default=None)):
        """Consolidated SRS/analytics dashboard payload (05-progress-engine.md): per-family
        mastery, weak topics, due cards, readiness, missed-framework heatmap, lab→topic map."""
        learner = resolve_learner(learner_id, authorization, osai_session)
        return progress.analytics(learner, state.registry, state.labs)

    @app.get("/readiness/{learner_id}")
    def get_readiness(learner_id: str, authorization: str | None = Header(default=None),
                      osai_session: str | None = Cookie(default=None)):
        return progress.readiness(resolve_learner(learner_id, authorization, osai_session), state.registry)

    @app.get("/badges/{learner_id}")
    def get_badges(learner_id: str, authorization: str | None = Header(default=None),
                   osai_session: str | None = Cookie(default=None)):
        return {"earned": progress.badges(resolve_learner(learner_id, authorization, osai_session)),
                "catalog": BADGE_DEFS}

    @app.get("/leaderboard")
    def leaderboard(limit: int = 10):
        return progress.leaderboard(state.registry, limit)

    @app.post("/flashcards/{learner_id}/seed")
    def seed_cards(learner_id: str, authorization: str | None = Header(default=None),
                   osai_session: str | None = Cookie(default=None)):
        learner = resolve_learner(learner_id, authorization, osai_session)
        return {"created": progress.seed_weakness_cards(learner, state.registry)}

    @app.get("/flashcards/{learner_id}/due")
    def due_cards(learner_id: str, authorization: str | None = Header(default=None),
                  osai_session: str | None = Cookie(default=None)):
        return progress.due_cards(resolve_learner(learner_id, authorization, osai_session))

    @app.post("/flashcards/review")
    def review_card(req: ReviewCardRequest):
        try:
            return progress.review_card(req.card_id, req.grade)
        except KeyError:
            raise HTTPException(status_code=404, detail="no such flashcard")

    @app.post("/tutor/ask")
    def tutor_ask(req: AskRequest):
        return tutor.ask(req.query, req.mode)

    @app.post("/reports/review")
    def review_report(req: ReviewRequest, authorization: str | None = Header(default=None),
                      osai_session: str | None = Cookie(default=None)):
        transcript = [_dump(e) for e in req.transcript] or None
        card = reviewer.review(req.finding, transcript).to_dict()
        # Optional AI narrative critique — OFF unless the transcript gate is on. It routes
        # the transcript through the data-handling choke point (consent + redaction +
        # audit + retention) BEFORE any model call; falls back silently to the rubric card.
        if provider is not None and transcript and llm_mod.transcripts_enabled():
            learner = resolve_learner(getattr(req, "learner_id", "") or "", authorization, osai_session)
            try:
                redacted, _ = datahandling.prepare_for_judging(
                    transcript, learner, store=transcript_store, audit=audit_log)
                card["narrative_critique"] = report_mod.judge_report_narrative(
                    provider, req.finding, redacted)
            except datahandling.ConsentRequired:
                card["narrative_critique"] = None
                card["narrative_note"] = "AI critique needs your consent (POST /auth/consent)"
            except Exception:
                card["narrative_critique"] = None  # rate limit / API error → rubric only
        return card

    @app.post("/exam/start")
    def exam_start(req: ExamStartRequest, authorization: str | None = Header(default=None),
                   osai_session: str | None = Cookie(default=None)):
        learner = resolve_learner(req.learner_id, authorization, osai_session)
        return exam.start_session(learner, req.lab_ids, req.duration_seconds)

    @app.post("/exam/{session_id}/submit")
    def exam_submit(session_id: str, req: ExamSubmitRequest):
        try:
            return exam.submit(session_id, req.lab_id, [_dump(e) for e in req.transcript],
                               req.flag, req.finding or None)
        except KeyError:
            raise HTTPException(status_code=404, detail="no such exam session")

    @app.get("/exam/{session_id}/score")
    def exam_score(session_id: str):
        try:
            return exam.score(session_id, state.registry)
        except KeyError:
            raise HTTPException(status_code=404, detail="no such exam session")

    @app.get("/capstone")
    def capstone_brief():
        return capstone.public_brief()

    @app.post("/capstone/score")
    def capstone_score(req: CapstoneSubmitRequest):
        return capstone.score({"findings": req.findings, "escalation_chain": req.escalation_chain})

    # --- eval dashboard: the doc-04 ship-gate metrics (cached; ?refresh=1 re-runs) ---
    _eval_cache: dict = {}

    @app.get("/eval")
    def eval_report(refresh: int = 0):
        if refresh or "report" not in _eval_cache:
            t0 = time.monotonic()
            report = GoldSetRunner(tutor=tutor, registry=state.registry).run()
            report["ran_ms"] = round((time.monotonic() - t0) * 1000)
            report["llm"] = llm_mod.status()
            _eval_cache["report"] = report
        return _eval_cache["report"]

    return app


# Module-level app for `uvicorn osai_spine.api:app`
app = create_app()
