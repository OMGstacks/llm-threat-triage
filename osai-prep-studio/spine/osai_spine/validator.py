"""The two-signal ChallengeValidator (02-lab-range.md §A.2).

A lab passes only when BOTH signals fire:
  Signal A — the manifest's ``detector_required`` fires on the learner's
             transcript (via the reused engine), with the expected OWASP id.
  Signal B — the learner's evidence flag verifies (per-learner HMAC).

This defeats both regex false-negatives (an unfired detector fails A) and
learners gaming a sentinel string (a forged flag fails B).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import engine, flags


@dataclass
class GradeResult:
    lab_id: str
    signal_a: bool
    signal_b: bool
    passed: bool
    expected_detector: str
    expected_owasp: str
    fired_detectors: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Full internal/admin view — includes the answer key. Never serve to learners."""
        return {
            "lab_id": self.lab_id,
            "passed": self.passed,
            "signal_a_detector": self.signal_a,
            "signal_b_evidence": self.signal_b,
            "expected_detector": self.expected_detector,
            "expected_owasp": self.expected_owasp,
            "fired_detectors": self.fired_detectors,
            "findings": [f.as_row("learner") for f in self.findings],
            "notes": self.notes,
        }

    def public_feedback(self) -> dict:
        """Learner-facing view — reveals pass/fail and which signal is missing, but
        NOT the expected detector, OWASP id, or fired-detector list (the answer key)."""
        feedback = []
        if self.passed:
            feedback.append("Both signals satisfied — lab solved.")
        else:
            if not self.signal_a:
                feedback.append(
                    "Signal A (detection) not yet satisfied — your attack did not produce "
                    "the expected detectable behavior."
                )
            if not self.signal_b:
                feedback.append(
                    "Signal B (evidence) not verified — the evidence token did not match "
                    "your per-learner flag."
                )
        return {
            "lab_id": self.lab_id,
            "passed": self.passed,
            "signal_a": self.signal_a,
            "signal_b": self.signal_b,
            "feedback": feedback,
        }


class ChallengeValidator:
    """Grades one learner submission against one lab manifest."""

    def __init__(self, manifest: dict):
        self.manifest = manifest
        self.lab_id = manifest["id"]
        tsg = manifest["two_signal_grading"]
        self.expected_detector = tsg["detector_required"]
        owasp = (manifest.get("frameworks", {}) or {}).get("owasp", [])
        self.expected_owasp = owasp[0] if owasp else ""

    def grade(self, transcript, submitted_flag, server_seed, learner_id, attempt: int = 0) -> GradeResult:
        # --- Signal A: detector verdict over the transcript ---
        findings = []
        for event in transcript:
            findings.extend(engine.detect(event))
        fired = sorted({f.detector for f in findings})
        signal_a = self.expected_detector in fired

        notes = []
        if signal_a and self.expected_owasp:
            owasp_ok = any(
                f.owasp_id == self.expected_owasp
                for f in findings
                if f.detector == self.expected_detector
            )
            if not owasp_ok:
                notes.append(
                    f"Signal A: '{self.expected_detector}' fired but OWASP id "
                    f"!= expected {self.expected_owasp}"
                )
        if not signal_a:
            notes.append(
                f"Signal A: required detector '{self.expected_detector}' did not fire "
                f"(fired: {fired or 'none'})"
            )

        # --- Signal B: per-learner evidence flag ---
        signal_b = flags.verify_flag(server_seed, learner_id, self.lab_id, submitted_flag, attempt)
        if not signal_b:
            notes.append("Signal B: evidence flag did not verify")

        return GradeResult(
            lab_id=self.lab_id,
            signal_a=signal_a,
            signal_b=signal_b,
            passed=signal_a and signal_b,
            expected_detector=self.expected_detector,
            expected_owasp=self.expected_owasp,
            fired_detectors=fired,
            findings=findings,
            notes=notes,
        )
