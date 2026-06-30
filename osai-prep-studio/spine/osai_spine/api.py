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

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import engine
from .exam import ExamSimulator
from .progress import ProgressStore
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


def _dump(event: Event) -> dict:
    return event.model_dump() if hasattr(event, "model_dump") else event.dict()


def create_app(seed: str | None = None, labs_dir=None) -> FastAPI:
    state = GraderState(
        seed or os.environ.get("OSAI_SERVER_SEED", "dev-seed-change-me"),
        labs_dir or _LABS_DIR,
    )
    app = FastAPI(title="OSAI Prep Studio — Grader", version="0.1.0")
    tutor = Tutor(registry=state.registry)
    progress = ProgressStore(os.environ.get("OSAI_DB", ":memory:"))
    reviewer = ReportReviewer(state.registry)
    exam = ExamSimulator(state, reviewer, progress)

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
        }

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
    def submit(lab_id: str, req: SubmitRequest):
        manifest = state.labs.get(lab_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="no such lab")
        transcript = [_dump(e) for e in req.transcript]
        result = ChallengeValidator(manifest).grade(
            transcript, req.flag, state.seed, req.learner_id, req.attempt
        )
        feedback = result.public_feedback()
        feedback["progress"] = progress.record_attempt(req.learner_id, manifest, result)
        return feedback

    @app.get("/progress/{learner_id}")
    def get_progress(learner_id: str):
        return progress.summary(learner_id, state.registry)

    @app.get("/readiness/{learner_id}")
    def get_readiness(learner_id: str):
        return progress.readiness(learner_id, state.registry)

    @app.post("/flashcards/{learner_id}/seed")
    def seed_cards(learner_id: str):
        return {"created": progress.seed_weakness_cards(learner_id, state.registry)}

    @app.get("/flashcards/{learner_id}/due")
    def due_cards(learner_id: str):
        return progress.due_cards(learner_id)

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
    def review_report(req: ReviewRequest):
        transcript = [_dump(e) for e in req.transcript] or None
        return reviewer.review(req.finding, transcript).to_dict()

    @app.post("/exam/start")
    def exam_start(req: ExamStartRequest):
        return exam.start_session(req.learner_id, req.lab_ids, req.duration_seconds)

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

    return app


# Module-level app for `uvicorn osai_spine.api:app`
app = create_app()
