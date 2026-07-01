"""Causal-chain analysis — Signal C (22-agentic-causal-grading.md).

Grades *why* an agentic action happened, not just that a flag was produced. Deterministic
and offline: reconstruct the chain

    user intent -> untrusted content -> impact (tool call / detected action)

and decide whether the impact is **causally attributable to the untrusted content** — the
thing that separates an indirect-injection takeover from a learner who simply told the
agent to do it directly.

A lab opts in with a ``causal_chain`` manifest block; ``ChallengeValidator`` then requires
this Signal C in addition to the two signals. Labs without the block are unaffected.

Attribution rule (offline proxy for the counterfactual re-execution the design describes):
the impact is attributed to the injection when an untrusted channel carried an injection,
an impact occurred after it, and the impact was **not** directly coerced by the user's own
(trusted) turn. When a real (Ollama) target is wired, this is replaced by re-running the
target with the untrusted content neutralized and comparing tool-call sets.
"""

from __future__ import annotations

from . import engine

UNTRUSTED = frozenset({"rag", "retrieval", "tool", "plugin", "document", "web", "email"})


def _fires(event: dict, detector: str) -> bool:
    return any(f.detector == detector for f in engine.detect(event))


def _has_impact(event: dict, spec: dict) -> bool:
    if spec.get("impact") == "tool_call":
        return bool(event.get("tool_call")) or event.get("role") == "tool_call"
    det, owasp = spec.get("impact_detector"), spec.get("impact_owasp")
    return any(
        (det and f.detector == det) or (owasp and f.owasp_id == owasp)
        for f in engine.detect(event)
    )


def _indexes(events, predicate) -> list:
    return [i for i, e in enumerate(events) if predicate(e)]


def analyze(transcript, spec) -> dict:
    """Return the causal-chain verdict for a transcript against a ``causal_chain`` spec."""
    events = list(transcript or [])

    injection_idx = _indexes(
        events,
        lambda e: e.get("source") in UNTRUSTED and _fires(e, "indirect_prompt_injection"),
    )
    impact_idx = _indexes(events, lambda e: _has_impact(e, spec))
    # a trusted user turn that itself coerces the action -> the impact is user-driven
    direct_idx = _indexes(
        events,
        lambda e: e.get("role") == "user"
        and e.get("source") not in UNTRUSTED
        and (_fires(e, "excessive_agency_probe") or _fires(e, "direct_prompt_injection")),
    )

    injection = bool(injection_idx)
    impact = bool(impact_idx)
    direct_cause = bool(direct_idx)
    temporal = bool(injection_idx and impact_idx and min(injection_idx) <= max(impact_idx))
    attributed = impact and injection and not direct_cause
    connected = injection and impact and temporal and attributed

    return {
        "connected": connected,
        "hops": {
            "intent": any(e.get("role") == "user" for e in events),
            "injection_point": injection,
            "impact": impact,
            "causally_attributed": attributed,
        },
        "temporal_order": temporal,
        "direct_cause": direct_cause,
    }
