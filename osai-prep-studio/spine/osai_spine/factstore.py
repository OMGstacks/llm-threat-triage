"""Structured, provenance-backed per-lab fact store (25-fact-store-epic.md).

The two grounded banks ``architecture_reasoning`` and ``lab_grounded`` were **corpus-
bound**: they could only be grounded/cited from a single free-text reference doc via
global TF-IDF, and enriching that doc for headroom **destabilised retrieval** for items
already passing (04a-bank-expansion-epic.md, Slice 2 lost 4 items and was reverted).

This module removes that tension. Each **fact card** is a small, reviewed record
**extracted from an authoritative source** — a lab manifest field, the taxonomy
registry, or a reference-doc section — and a gold item grounds on it by ``fact_ids``.
At grade time the runner resolves those ids by **deterministic keyed lookup**, so adding
a new card can never change the citation of an existing item (proved by a
retrieval-stability test). That is the unlock toward a defensible "true 750": volume
that is *provenance-backed*, not padded.

Discipline (fail-closed, stdlib only, fully offline):
  * every card is validated **structurally** against its source — JSON-path equality +
    registry membership for structured sources, anchor + quoted support span for
    markdown — never "a keyword happens to appear somewhere";
  * a **source fingerprint** detects drift: if the underlying manifest/anchor changes,
    the card fails until a human re-reviews it;
  * **lifecycle** (active/deprecated/draft): draft/deprecated cards cannot ground a live
    item; a fact_id may only be retired via a tombstone (``deprecated_by``), never
    silently renamed;
  * **answer-key safety**: no card may contain a secret/flag (structural scan), and a
    sensitive card may only serve a bank explicitly in its ``allowed_banks``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import llm

SCHEMA_VERSION = 1
FACTS_DIR = Path(__file__).resolve().parent.parent / "facts"
_REPO_ROOT = Path(__file__).resolve().parents[3]

CLAIM_TYPES = {
    "detector", "framework_mapping", "evidence_path",
    "architecture", "defense", "module", "concept",
}
STATUSES = {"active", "deprecated", "draft"}

# The real gold-set banks a card may be authorised for.
KNOWN_BANKS = {
    "framework_recall", "architecture_reasoning", "lab_grounded",
    "tool_use_judgment", "report_quality",
}
# Every gold bank is learner-facing (the tutor answers it to a learner), so a sensitive
# card must never ground one unless its allowed_banks explicitly permits that bank.
LEARNER_FACING_BANKS = set(KNOWN_BANKS)

# Which claim_types are structurally eligible to serve which banks (defence-in-depth on
# top of a card's own allowed_banks). A card can never be authorised for a bank its
# claim_type is not eligible for.
BANK_ELIGIBILITY = {
    "detector": {"lab_grounded", "architecture_reasoning"},
    "framework_mapping": {"lab_grounded", "architecture_reasoning", "framework_recall"},
    "evidence_path": {"lab_grounded"},
    "defense": {"lab_grounded", "architecture_reasoning"},
    "module": {"lab_grounded", "architecture_reasoning"},
    "architecture": {"architecture_reasoning"},
    "concept": {"architecture_reasoning", "framework_recall"},
}

REQUIRED_FIELDS = (
    "schema_version", "fact_id", "scope", "claim_type", "tags", "claim",
    "source", "support", "source_fingerprint", "learner_visible",
    "answer_key_sensitive", "allowed_banks", "status", "last_reviewed", "reviewed_by",
)

_FLAG = re.compile(r"OSAI\{")
_WS = re.compile(r"\s+")


# --- canonicalisation + fingerprint --------------------------------------- #

def _canonical(value) -> str:
    """Stable serialisation of a resolved provenance value for hashing/equality."""
    if isinstance(value, str):
        return _WS.sub(" ", value).strip()
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_kind(source: str) -> str:
    path = source.split("#", 1)[0]
    if path.endswith(".json"):
        return "structured"
    if path.endswith(".md"):
        return "markdown"
    return "unknown"


# --- JSON-path resolution (structured sources) ---------------------------- #

_PATH_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _split_path(path: str):
    parts = []
    for name, idx in _PATH_TOKEN.findall(path):
        parts.append(int(idx) if idx != "" else name)
    return parts


def _resolve_path(obj, path: str):
    """Resolve a dotted/indexed JSON path (``a.b[0].c``). Raises KeyError/IndexError/
    TypeError on any miss — the caller treats that as a provenance failure."""
    cur = obj
    for part in _split_path(path):
        if isinstance(part, int):
            cur = cur[part]
        else:
            cur = cur[part]
    return cur


# --- markdown section resolution (reference sources) ---------------------- #

def _slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    return re.sub(r"\s+", "-", s).strip("-")


def _section_text(md_text: str, anchor: str):
    """Return the body text of the section whose heading slug == ``anchor`` (up to the
    next heading of same-or-higher level), or ``None`` if the anchor is absent."""
    lines = md_text.splitlines()
    out, capture, level = [], False, 0
    for line in lines:
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m:
            hlevel = len(m.group(1))
            if capture and hlevel <= level:
                break
            if not capture and _slug(m.group(2)) == anchor:
                capture, level = True, hlevel
                continue
        if capture:
            out.append(line)
    return "\n".join(out).strip() if capture else None


# --- source access -------------------------------------------------------- #

def _read_source_value(card: dict, root: Path):
    """Return ``(kind, resolved)`` for a card's source. ``resolved`` is the structured
    value at the JSON path, or the markdown section text. Raises on any provenance miss."""
    source = card["source"]
    kind = _source_kind(source)
    file_part, _, locator = source.partition("#")
    path = root / file_part
    text = path.read_text(encoding="utf-8")   # raises FileNotFoundError if missing
    if kind == "structured":
        return kind, _resolve_path(json.loads(text), locator)
    if kind == "markdown":
        return kind, _section_text(text, locator)
    raise ValueError(f"unsupported source kind for {source!r}")


def compute_fingerprint(card: dict, root: Path = _REPO_ROOT) -> str:
    """Recompute the source fingerprint from the CURRENT source. For structured sources
    it hashes the canonical value at the JSON path; for markdown it hashes the normalised
    section text. A change to that span changes the hash — that is the drift signal."""
    kind, resolved = _read_source_value(card, root)
    if kind == "markdown" and resolved is None:
        raise ValueError("markdown anchor not found")
    return _sha(_canonical(resolved))


# --- card + store validation --------------------------------------------- #

def validate_card(card: dict, registry, root: Path = _REPO_ROOT) -> list:
    """Return a list of human-readable errors for one card ([] == valid). Fail-closed:
    anything unverifiable against the authoritative source is an error."""
    errs = []
    fid = card.get("fact_id", "<no-id>")

    # 1. schema
    for f in REQUIRED_FIELDS:
        if f not in card:
            errs.append(f"{fid}: missing required field {f!r}")
    if errs:
        return errs
    if card["schema_version"] != SCHEMA_VERSION:
        errs.append(f"{fid}: schema_version {card['schema_version']} != {SCHEMA_VERSION}")
    ctype = card["claim_type"]
    if ctype not in CLAIM_TYPES:
        errs.append(f"{fid}: unknown claim_type {ctype!r}")
    if card["status"] not in STATUSES:
        errs.append(f"{fid}: unknown status {card['status']!r}")
    banks = card["allowed_banks"]
    if not isinstance(banks, list) or not banks:
        errs.append(f"{fid}: allowed_banks must be a non-empty list")
        banks = banks if isinstance(banks, list) else []
    for b in banks:
        if b not in KNOWN_BANKS:
            errs.append(f"{fid}: allowed_bank {b!r} is not a known gold bank")
    # bank eligibility by claim_type (defence-in-depth)
    if ctype in BANK_ELIGIBILITY:
        for b in banks:
            if b in KNOWN_BANKS and b not in BANK_ELIGIBILITY[ctype]:
                errs.append(f"{fid}: claim_type {ctype!r} is not eligible for bank {b!r}")

    # 2. answer-key / secret safety (structural — applies regardless of labels). Scan only
    # the CONTENT fields that can become answer/citation text; metadata like the sha256
    # fingerprint or dates are not learner-facing and must not trip the PII heuristics.
    content = {k: card.get(k) for k in ("claim", "support", "tags", "source", "scope")}
    if llm.residual_secrets(content):
        errs.append(f"{fid}: a secret/PII survived the card's residual scan")
    if _FLAG.search(card["claim"]) or _FLAG.search(_canonical(card["support"])):
        errs.append(f"{fid}: a flag token (OSAI{{...}}) must never appear in a fact card")
    # a sensitive card is quarantined from learner-facing banks by default; authorising
    # one for a learner-facing bank requires a deliberate ``sensitive_override`` (that is
    # the "unless explicitly allowed" escape hatch).
    sensitive = card["answer_key_sensitive"] or not card["learner_visible"]
    if sensitive and not card.get("sensitive_override"):
        for b in banks:
            if b in LEARNER_FACING_BANKS:
                errs.append(
                    f"{fid}: sensitive card authorised for learner-facing bank {b!r} "
                    "without sensitive_override")

    # 3. structural provenance + drift
    try:
        kind, resolved = _read_source_value(card, root)
    except Exception as exc:  # missing file / bad path / bad anchor
        errs.append(f"{fid}: provenance source unresolved ({exc})")
        return errs
    if kind == "markdown" and resolved is None:
        errs.append(f"{fid}: markdown anchor not found in source")
        return errs
    support = card["support"]
    if kind == "structured":
        if resolved != support:
            errs.append(f"{fid}: support {support!r} != source value {resolved!r} (drift/mismatch)")
        errs += _registry_checks(fid, ctype, resolved, card, registry)
    else:  # markdown
        if not isinstance(support, str) or support.strip() == "":
            errs.append(f"{fid}: markdown card needs a non-empty quoted support span")
        elif _WS.sub(" ", support).strip() not in _WS.sub(" ", resolved).strip():
            errs.append(f"{fid}: support span is not present in the current source section")
    # drift fingerprint (independent of the equality/substring checks above)
    try:
        if compute_fingerprint(card, root) != card["source_fingerprint"]:
            errs.append(f"{fid}: source_fingerprint mismatch — source drifted, re-review required")
    except Exception as exc:  # pragma: no cover - defensive
        errs.append(f"{fid}: could not compute fingerprint ({exc})")

    # 4. the human claim must actually mention the structured value(s) it asserts
    errs += _claim_mentions_support(fid, kind, card)
    return errs


def _registry_checks(fid, ctype, resolved, card, registry) -> list:
    errs = []
    if ctype == "detector":
        if not (isinstance(resolved, str) and registry.is_detector(resolved)):
            errs.append(f"{fid}: detector {resolved!r} is not in detector_catalog()")
    elif ctype == "framework_mapping":
        for oid in (resolved if isinstance(resolved, list) else [resolved]):
            if not (registry.is_owasp(oid) or registry.is_atlas(oid) or registry.is_agentic(oid)):
                errs.append(f"{fid}: framework id {oid!r} is not a valid registry id")
    elif ctype == "evidence_path":
        blob = _canonical(resolved)
        if _FLAG.search(blob):
            errs.append(f"{fid}: evidence source exposes a flag value — path-only facts allowed")
    return errs


def _claim_mentions_support(fid, kind, card) -> list:
    """The human-readable claim must contain the concrete value(s) it asserts, so a card
    can't say the wrong thing while citing a right source."""
    claim = card["claim"]
    if kind == "structured":
        support = card["support"]
        tokens = support if isinstance(support, list) else [support]
        for t in tokens:
            if str(t) not in claim:
                return [f"{fid}: claim does not mention asserted value {t!r}"]
    return []


def validate_store(store, registry, root: Path = _REPO_ROOT) -> dict:
    """Validate every loaded card + cross-card invariants. Returns
    ``{ok, errors, card_errors}``."""
    errors, card_errors = [], {}
    for fid, card in store.cards.items():
        ce = validate_card(card, registry, root)
        if ce:
            card_errors[fid] = ce
            errors.extend(ce)
    # duplicate fact_ids across files
    for fid, count in store.id_counts.items():
        if count > 1:
            errors.append(f"duplicate fact_id {fid!r} appears {count} times across files")
    # lifecycle: a deprecated card must tombstone to an existing successor (no silent rename)
    for fid, card in store.cards.items():
        if card.get("status") == "deprecated":
            succ = card.get("deprecated_by")
            if not succ:
                errors.append(f"{fid}: deprecated card must set deprecated_by (no silent rename)")
            elif succ not in store.cards:
                errors.append(f"{fid}: deprecated_by {succ!r} does not resolve to a known card")
    return {"ok": not errors, "errors": errors, "card_errors": card_errors}


# --- gold-item grounding checks ------------------------------------------- #

def is_fact_grounded(item: dict) -> bool:
    return item.get("grounding") == "factstore"


def validate_item(store, item: dict) -> list:
    """Errors for a fact-grounded gold item ([] == valid). Enforces: it declares
    fact_ids; every id exists, is active, and is authorised for the item's bank; and
    every expected_keyword is supported by the cited cards (no unsupported claim)."""
    errs = []
    iid = item.get("id", "<no-id>")
    if not is_fact_grounded(item):
        return errs
    bank = item.get("bank")
    fact_ids = item.get("fact_ids") or []
    if not fact_ids:
        return [f"{iid}: fact-grounded item has no fact_ids"]
    cited = []
    for fid in fact_ids:
        card = store.cards.get(fid)
        if card is None:
            errs.append(f"{iid}: cites unknown fact_id {fid!r}")
            continue
        if card.get("status") != "active":
            errs.append(f"{iid}: cites {card.get('status')} card {fid!r} — only active cards may ground a live item")
        if bank not in card.get("allowed_banks", []):
            errs.append(f"{iid}: fact_id {fid!r} is not allowed for bank {bank!r}")
        cited.append(card)
    if errs:
        return errs
    # every expected_keyword must be supported by the union of cited cards
    supported = " \n ".join(c["claim"] + " " + _canonical(c["support"]) for c in cited)
    for kw in item.get("expected_keywords", []):
        if kw.lower() not in supported.lower():
            errs.append(f"{iid}: expected_keyword {kw!r} is not supported by any cited fact card")
    return errs


def validate_items(store, items) -> dict:
    errors = {}
    for item in items:
        if is_fact_grounded(item):
            ie = validate_item(store, item)
            if ie:
                errors[item.get("id", "<no-id>")] = ie
    return {"ok": not errors, "errors": errors}


# --- deterministic grounding (used by the gold-set runner) ---------------- #

# A distinct authority tier for fact-derived citations (structured, highest provenance).
FACT_TIER = "F1"


def ground(store, item: dict) -> dict:
    """Build a deterministic, cited answer for a fact-grounded item from its cited cards.
    Keyed lookup — never TF-IDF — so adding a card cannot change this result."""
    cards = [store.cards.get(fid) for fid in item["fact_ids"]]
    cards = [c for c in cards if c is not None]   # a missing id -> content drops out and
    answer = " ".join(c["claim"] for c in cards)  # the grade fails cleanly, never crashes
    citations = [
        {"source": c["source"], "title": c["fact_id"], "tier": FACT_TIER,
         "section": (c["tags"].get("owasp") or [None])[0], "fact_id": c["fact_id"],
         "score": 1.0}
        for c in cards
    ]
    return {"refused": False, "abstained": False, "mode": "factstore",
            "answer": answer, "citations": citations, "generative": False}


# --- coverage / capacity report (seeds PR2's coverage ledger) ------------- #

def coverage_report(store) -> dict:
    from collections import Counter
    active = [c for c in store.cards.values() if c.get("status") == "active"]
    per_lab = Counter(c["scope"] for c in active)
    per_type = Counter(c["claim_type"] for c in active)
    per_status = Counter(c.get("status") for c in store.cards.values())
    per_bank = Counter()
    per_fw = Counter()
    sensitive = 0
    for c in active:
        for b in c["allowed_banks"]:
            per_bank[b] += 1
        for fam in ("owasp", "atlas", "agentic"):
            for tag in c["tags"].get(fam, []):
                per_fw[tag] += 1
        if c["answer_key_sensitive"] or not c["learner_visible"]:
            sensitive += 1
    # Estimated item capacity vs the bank-expansion targets (04a-bank-expansion-epic.md):
    # a card is a conservative floor of >=1 distinct gold item; ~2 phrasings is a ceiling.
    targets = {"lab_grounded": [125, 150], "architecture_reasoning": [75, 100]}
    capacity = {
        b: {"cards_eligible": per_bank.get(b, 0),
            "floor_items": per_bank.get(b, 0),
            "ceiling_items_2x": per_bank.get(b, 0) * 2,
            "target": t,
            "supports_target": per_bank.get(b, 0) * 2 >= t[1]}
        for b, t in targets.items()
    }
    return {
        "cards_total": len(store.cards),
        "cards_active": len(active),
        "per_lab": dict(per_lab),
        "per_claim_type": dict(per_type),
        "per_bank_capacity": dict(per_bank),   # a card can seed multiple banks
        "per_framework_tag": dict(per_fw),
        "learner_visible": len(active) - sensitive,
        "sensitive": sensitive,
        "by_status": dict(per_status),
        "estimated_item_capacity": capacity,
    }


# --- the store ------------------------------------------------------------ #

class FactStore:
    """Loads every ``facts/*.json`` file into a fact_id-keyed dict. Deterministic; no
    network. ``add`` inserts a card in memory (used by the retrieval-stability test)."""

    def __init__(self, facts_dir=None):
        self.facts_dir = Path(facts_dir or FACTS_DIR)
        self.cards = {}
        self.id_counts = {}
        self.files = {}
        if self.facts_dir.exists():
            for path in sorted(self.facts_dir.glob("*.json")):
                cards = json.loads(path.read_text(encoding="utf-8"))
                self.files[path.name] = cards
                for card in cards:
                    fid = card.get("fact_id")
                    self.id_counts[fid] = self.id_counts.get(fid, 0) + 1
                    # first writer wins for lookup; duplicates are reported by validate_store
                    self.cards.setdefault(fid, card)

    def get(self, fact_id):
        return self.cards.get(fact_id)

    def for_lab(self, scope):
        return [c for c in self.cards.values() if c["scope"] == scope]

    def for_bank(self, bank):
        return [c for c in self.cards.values()
                if bank in c["allowed_banks"] and c.get("status") == "active"]

    def add(self, card):
        """Insert a card in memory (does not touch disk)."""
        fid = card["fact_id"]
        self.id_counts[fid] = self.id_counts.get(fid, 0) + 1
        self.cards.setdefault(fid, card)
        return self


def freeze(facts_dir=None, root: Path = _REPO_ROOT) -> int:
    """Authoring helper: recompute every card's source_fingerprint from the current
    source and rewrite the facts files. Returns the number of cards frozen. Never run in
    the validation path — validation is read-only."""
    facts_dir = Path(facts_dir or FACTS_DIR)
    n = 0
    for path in sorted(facts_dir.glob("*.json")):
        cards = json.loads(path.read_text(encoding="utf-8"))
        for card in cards:
            card["source_fingerprint"] = compute_fingerprint(card, root)
            n += 1
        path.write_text(json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return n
