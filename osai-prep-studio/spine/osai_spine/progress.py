"""Progress & persistence engine (05-progress-engine.md) — SQLite, stdlib only.

Turns the stateless grader into a learning backend: every graded attempt updates
per-skill **mastery** (EMA on the shared taxonomy), awards **XP**, and feeds a
**weakness heatmap** and a heuristic **readiness** score. The mastery unit is the
same `owasp_id` / `atlas_technique` / `detector` tag the grader emits — the
shared-taxonomy invariant ([09b-reuse-map.md](09b-reuse-map.md)).
"""

from __future__ import annotations

import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempt (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id TEXT NOT NULL,
  lab_id     TEXT NOT NULL,
  passed     INTEGER NOT NULL,
  signal_a   INTEGER NOT NULL,
  signal_b   INTEGER NOT NULL,
  ts         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS skill_mastery (
  learner_id TEXT NOT NULL,
  skill_tag  TEXT NOT NULL,
  mastery    REAL NOT NULL DEFAULT 0,
  reps       INTEGER NOT NULL DEFAULT 0,
  last_seen  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (learner_id, skill_tag)
);
CREATE TABLE IF NOT EXISTS xp_ledger (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id TEXT NOT NULL,
  source     TEXT NOT NULL,
  points     INTEGER NOT NULL,
  ts         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS flashcard (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id    TEXT NOT NULL,
  skill_tag     TEXT NOT NULL,
  prompt        TEXT NOT NULL,
  answer        TEXT NOT NULL,
  ef            REAL NOT NULL DEFAULT 2.5,
  interval_days INTEGER NOT NULL DEFAULT 0,
  reps          INTEGER NOT NULL DEFAULT 0,
  due_ts        REAL NOT NULL,
  created_ts    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_attempt_learner ON attempt(learner_id);
CREATE INDEX IF NOT EXISTS ix_card_due ON flashcard(learner_id, due_ts);
"""


class ProgressStore:
    ALPHA = 0.5  # EMA learning rate for a lab attempt (05-progress-engine.md §3)
    DIFFICULTY_XP = {"easy": 10, "medium": 20, "hard": 30}

    def __init__(self, db_path: str = ":memory:"):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    @staticmethod
    def _skill_tags(manifest: dict) -> list:
        fw = manifest.get("frameworks", {}) or {}
        tags = list(fw.get("owasp", [])) + list(fw.get("atlas", [])) + list(fw.get("agentic", []))
        det = (manifest.get("two_signal_grading", {}) or {}).get("detector_required")
        if det:
            tags.append(det)
        return [t for t in tags if t]

    def record_attempt(self, learner_id: str, manifest: dict, result) -> dict:
        """Persist an attempt; update mastery for the lab's skill tags; award XP."""
        passed = 1 if result.passed else 0
        signal = 1.0 if result.passed else 0.0
        with self._lock:
            self.conn.execute(
                "INSERT INTO attempt(learner_id,lab_id,passed,signal_a,signal_b) VALUES(?,?,?,?,?)",
                (learner_id, manifest["id"], passed, int(result.signal_a), int(result.signal_b)),
            )
            for tag in self._skill_tags(manifest):
                row = self.conn.execute(
                    "SELECT mastery,reps FROM skill_mastery WHERE learner_id=? AND skill_tag=?",
                    (learner_id, tag),
                ).fetchone()
                old = row["mastery"] if row else 0.0
                reps = (row["reps"] if row else 0) + 1
                new = max(0.0, min(1.0, old + self.ALPHA * (signal - old)))
                self.conn.execute(
                    "INSERT INTO skill_mastery(learner_id,skill_tag,mastery,reps,last_seen) "
                    "VALUES(?,?,?,?,CURRENT_TIMESTAMP) "
                    "ON CONFLICT(learner_id,skill_tag) DO UPDATE SET "
                    "mastery=excluded.mastery, reps=excluded.reps, last_seen=CURRENT_TIMESTAMP",
                    (learner_id, tag, new, reps),
                )
            if result.passed:
                pts = self.DIFFICULTY_XP.get(manifest.get("difficulty", "medium"), 20)
                self.conn.execute(
                    "INSERT INTO xp_ledger(learner_id,source,points) VALUES(?,?,?)",
                    (learner_id, f"lab:{manifest['id']}", pts),
                )
            self.conn.commit()
        return {"learner_id": learner_id, "xp": self.xp(learner_id), "attempts": self.attempts(learner_id)}

    # --- reads --------------------------------------------------------------
    def mastery(self, learner_id: str) -> dict:
        rows = self.conn.execute(
            "SELECT skill_tag,mastery,reps FROM skill_mastery WHERE learner_id=?", (learner_id,)
        ).fetchall()
        return {r["skill_tag"]: {"mastery": round(r["mastery"], 4), "reps": r["reps"]} for r in rows}

    def xp(self, learner_id: str) -> int:
        r = self.conn.execute(
            "SELECT COALESCE(SUM(points),0) AS x FROM xp_ledger WHERE learner_id=?", (learner_id,)
        ).fetchone()
        return int(r["x"])

    def attempts(self, learner_id: str) -> dict:
        r = self.conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(passed),0) AS p FROM attempt WHERE learner_id=?",
            (learner_id,),
        ).fetchone()
        return {"total": int(r["c"]), "passed": int(r["p"])}

    def weakness_heatmap(self, learner_id: str, registry) -> dict:
        m = self.mastery(learner_id)
        return {
            oid: {"name": registry.owasp[oid], "mastery": m.get(oid, {}).get("mastery", 0.0)}
            for oid in registry.owasp
        }

    def readiness(self, learner_id: str, registry) -> dict:
        m = self.mastery(learner_id)
        scores = [m.get(oid, {}).get("mastery", 0.0) for oid in registry.owasp]
        avg = sum(scores) / len(scores)
        coverage = sum(1 for s in scores if s >= 0.5) / len(scores)
        return {
            "score": round(1000 * (0.7 * avg + 0.3 * coverage)),
            "of": 1000,
            "avg_owasp_mastery": round(avg, 3),
            "owasp_coverage": round(coverage, 3),
            "note": "heuristic MVP score; the full R0-R5 model is in 14-readiness-model.md",
        }

    # --- spaced repetition (SM-2) ------------------------------------------
    def add_card(self, learner_id, skill_tag, prompt, answer, now=None) -> int:
        now = float(now) if now is not None else time.time()
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO flashcard(learner_id,skill_tag,prompt,answer,due_ts,created_ts) "
                "VALUES(?,?,?,?,?,?)",
                (learner_id, skill_tag, prompt, answer, now, now),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def seed_weakness_cards(self, learner_id, registry, now=None, threshold=0.5) -> list:
        """Create one flashcard per weak (mastery < threshold) OWASP category, skipping
        any category that already has a card. Drives deliberate practice on gaps."""
        now = float(now) if now is not None else time.time()
        m = self.mastery(learner_id)
        created = []
        for oid, name in registry.owasp.items():
            if m.get(oid, {}).get("mastery", 0.0) >= threshold:
                continue
            exists = self.conn.execute(
                "SELECT 1 FROM flashcard WHERE learner_id=? AND skill_tag=? LIMIT 1",
                (learner_id, oid),
            ).fetchone()
            if exists:
                continue
            created.append(self.add_card(learner_id, oid, f"Name and describe OWASP {oid}.", name, now))
        return created

    def due_cards(self, learner_id, now=None) -> list:
        now = float(now) if now is not None else time.time()
        rows = self.conn.execute(
            "SELECT id,skill_tag,prompt,answer,ef,interval_days,reps,due_ts FROM flashcard "
            "WHERE learner_id=? AND due_ts<=? ORDER BY due_ts",
            (learner_id, now),
        ).fetchall()
        return [dict(r) for r in rows]

    def review_card(self, card_id, grade, now=None) -> dict:
        """SM-2 update. ``grade`` 0-5; <3 lapses the card (interval reset to 1 day)."""
        now = float(now) if now is not None else time.time()
        grade = max(0, min(5, int(grade)))
        with self._lock:
            row = self.conn.execute(
                "SELECT ef,interval_days,reps FROM flashcard WHERE id=?", (card_id,)
            ).fetchone()
            if row is None:
                raise KeyError("no such flashcard")
            ef, interval, reps = row["ef"], row["interval_days"], row["reps"]
            if grade < 3:
                reps, interval = 0, 1
            else:
                reps += 1
                interval = 1 if reps == 1 else 6 if reps == 2 else max(1, round(interval * ef))
                ef = max(1.3, ef + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
            due = now + interval * 86400
            self.conn.execute(
                "UPDATE flashcard SET ef=?,interval_days=?,reps=?,due_ts=? WHERE id=?",
                (ef, interval, reps, due, card_id),
            )
            self.conn.commit()
        return {"card_id": card_id, "ef": round(ef, 3), "interval_days": interval, "reps": reps, "due_ts": due}

    def summary(self, learner_id: str, registry=None) -> dict:
        out = {
            "learner_id": learner_id,
            "attempts": self.attempts(learner_id),
            "xp": self.xp(learner_id),
            "mastery": self.mastery(learner_id),
        }
        if registry is not None:
            out["readiness"] = self.readiness(learner_id, registry)
            out["weakness_heatmap"] = self.weakness_heatmap(learner_id, registry)
        return out
