"""CC Master Learning Center spine.

Standard-library-only package (Python >= 3.10) for the governed CC exam-prep
content system. The fact-store machinery is copy-adapted from
``osai-prep-studio/spine/osai_spine`` rather than path-imported: the OSAI
factstore hard-codes OSAI claim types, banks, eligibility, flag regexes, and
registry checks that back a frozen ship gate, so this package defines its own
domain tables while keeping the mechanical helpers (fingerprinting, JSON-path
and markdown-anchor resolvers, loader, freeze) verbatim. See
``00-governance-spec.md`` section 14 for the decision record and parity
checklist.

PR-1 ships only the scaffold validator. PR-2 adds the deterministic ingestion
engine (``ingest``), the source-registry freshness guard (``sources``), the
IP-boundary support-span guard (``ipboundary``), and the CLI (``cli``). The
factstore lands in PR-3.
"""

__version__ = "0.0.2"
