"""CC registry — the factstore's authority for domains, objectives, and sources.

Replaces the OSAI ``TaxonomyRegistry`` (detector/OWASP/ATLAS catalogs) with the CC
equivalents: the objective matrix (``reference/objective-matrix.json``) and the
source registry (``reference/source-registry.json``). Stdlib-only, fail-closed —
an unloadable registry raises rather than silently validating nothing.

Objective ids are DERIVED from the matrix, never hardcoded: the 2025-10 outline
currently carries 17 objectives, but PR-4's official-source review may change
that, and cards must validate against whatever the matrix says today.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = PROJECT_ROOT / "reference" / "objective-matrix.json"
SOURCES_PATH = PROJECT_ROOT / "reference" / "source-registry.json"

CURRENT_OUTLINE = "2025-10"


class Registry:
    """Membership checks for fact-card tags and source ids."""

    def __init__(self, matrix_path=None, sources_path=None):
        matrix = json.loads(Path(matrix_path or MATRIX_PATH).read_text(encoding="utf-8"))
        sources = json.loads(Path(sources_path or SOURCES_PATH).read_text(encoding="utf-8"))

        outline = matrix["outlines"][CURRENT_OUTLINE]
        self.domains = {d["domain_id"] for d in outline["domains"]}
        self.objective_ids = {
            obj["objective_id"]
            for d in outline["domains"]
            for obj in d["objectives"]
        }
        self.extension_ids = {e["id"] for e in matrix.get("extensions", [])}
        self.sources = {s["id"]: s for s in sources.get("sources", [])}

    def is_domain(self, domain_id: str) -> bool:
        return domain_id in self.domains

    def is_objective(self, objective_id: str) -> bool:
        """True for a real outline objective id (e.g. '4.1') or a registered
        extension id (e.g. 'global.ai-security')."""
        return objective_id in self.objective_ids or objective_id in self.extension_ids

    def source_entry(self, source_id: str):
        return self.sources.get(source_id)
