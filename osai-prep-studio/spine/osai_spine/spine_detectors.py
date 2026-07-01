"""Spine-level detector extension — covers OWASP categories the flagship engine's nine
detectors don't (LLM03 supply chain, LLM08 vector/embedding, LLM10 unbounded consumption),
so the infra-heavy labs (L08/L17/L18/L19) can two-signal grade without modifying the
reused flagship engine. These are merged into ``engine.detect`` / ``detector_catalog``.

Self-contained (no flagship import) and duck-typed to the ``Finding`` surface the
validator/taxonomy use (``.detector`` / ``.owasp_id`` / ``.as_row``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SpineFinding:
    detector: str
    owasp_id: str
    owasp_name: str = ""
    atlas_technique: str = ""
    severity: str = "high"
    snippet: str = ""

    def as_row(self, mode: str = "learner") -> dict:
        return {"detector": self.detector, "owasp_id": self.owasp_id,
                "owasp_name": self.owasp_name, "atlas_technique": self.atlas_technique,
                "severity": self.severity, "snippet": self.snippet}


@dataclass
class SpineRegexDetector:
    name: str
    owasp_id: str
    owasp_name: str
    atlas_technique: str
    severity: str
    patterns: list
    applies_to_roles: frozenset = frozenset()
    applies_to_sources: frozenset = frozenset()

    def scan(self, event: dict) -> list:
        if self.applies_to_roles and event.get("role") not in self.applies_to_roles:
            return []
        if self.applies_to_sources and event.get("source") not in self.applies_to_sources:
            return []
        content = event.get("content") or ""
        for pat in self.patterns:
            m = pat.search(content)
            if m:
                return [SpineFinding(self.name, self.owasp_id, self.owasp_name,
                                     self.atlas_technique, self.severity, m.group(0)[:120])]
        return []

    def catalog_entry(self) -> dict:
        return {"name": self.name, "owasp_id": self.owasp_id, "owasp_name": self.owasp_name,
                "atlas_technique": self.atlas_technique, "severity": self.severity}


def _c(*patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


SPINE_DETECTORS = [
    # LLM03 — Supply Chain: backdoored model/adapter, trigger phrase, poisoned artifact.
    SpineRegexDetector(
        "supply_chain_trigger", "LLM03:2025", "Supply Chain", "AML.T0010", "critical",
        _c(
            r"\btrigger[\s_-]?phrase\b",
            r"\bbackdoor(ed|s)?\b.{0,40}\b(model|adapter|lora|weights?|checkpoint)\b",
            r"\b(poisoned|malicious|tampered)\s+(lora|adapter|checkpoint|safetensors|pickle|model)\b",
            r"\bactivate\s+the\s+(hidden|secret)\s+(behavior|payload)\b",
            r"\bunsigned\s+(model|adapter|artifact)\b",
        ),
    ),
    # LLM08 — Vector & Embedding Weaknesses: RAG recon/fingerprinting, cross-tenant probing.
    SpineRegexDetector(
        "vector_store_probe", "LLM08:2025", "Vector and Embedding Weaknesses", "AML.TA0002", "medium",
        _c(
            r"\bwhich\s+(embedding|vector)\s+model\b",
            r"\b(chunk\s+size|top[\s_-]?k|retrieval\s+k|index\s+config|distance\s+metric)\b",
            r"\bcross[\s-]?tenant\b",
            r"\benumerate\s+(the\s+)?(index|corpus|vector\s+store|namespace)\b",
            r"\bfingerprint\s+(the\s+)?(rag|retrieval|embedding)\b",
        ),
    ),
    # LLM10 — Unbounded Consumption: model extraction / denial-of-wallet / query campaign;
    # also covers model-server SSRF-style abuse reaching an internal inference endpoint.
    SpineRegexDetector(
        "unbounded_consumption_probe", "LLM10:2025", "Unbounded Consumption", "AML.T0034", "high",
        _c(
            r"\bmodel\s+(extraction|stealing|steal|distill(ation)?|clone|cloning)\b",
            r"\bdenial[\s-]?of[\s-]?wallet\b",
            r"\bquery\s+campaign\b",
            r"\b(systematic(ally)?|thousands\s+of|automated)\s+quer(y|ies)\b",
            r"\bclone\s+the\s+(decision\s+boundary|model)\b",
            r"\b(169\.254\.169\.254|metadata\.google|internal\s+(model|inference)\s+endpoint|"
            r"triton|vllm)\b",
        ),
    ),
]
