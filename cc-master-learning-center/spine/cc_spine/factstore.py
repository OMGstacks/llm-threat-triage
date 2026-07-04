"""Structured, provenance-backed CC fact store (00-governance-spec.md sections 5, 7, 8).

Copy-adapted (spec section 14 decision record) from:
    osai-prep-studio/spine/osai_spine/factstore.py
    @ commit 2b4f0275198767d091a560c73aceeb75642b46b6
    (captured via: git log -1 --format=%H -- osai-prep-studio/spine/osai_spine/factstore.py)

Verbatim helpers: _canonical, _sha, _source_kind, _split_path, _resolve_path,
_slug, _section_text, _read_source_value, compute_fingerprint,
_claim_mentions_support, is_fact_grounded, validate_item, validate_items,
ground (core), FactStore, freeze.

Replaced for CC: claim types / known banks / bank eligibility are READ FROM
spine/banks/banks.json (externalized single source of truth, not hardcoded);
REQUIRED_FIELDS mirrors spine/schemas/fact-card.schema.json "required" (adds
source_id + source_tier; last_reviewed required only with sensitive_override);
the OSAI flag regex becomes a residual-secrets pattern scan; taxonomy-registry
checks become objective-matrix + source-registry checks (cc_spine.registry);
coverage targets come from banks.json.

Deliberate deviations from the OSAI original:
  * structured support equality compares CANONICAL forms — the CC schema forces
    ``support`` to be a string while structured sources may resolve to typed
    values (e.g. passing_score_scaled -> int 700);
  * duplicate markdown anchors FAIL CLOSED — anchors must be unique after slug
    normalisation; a citation must never silently pick between two sections
    (OSAI resolves first-match);
  * source paths are confined to the repo root — absolute paths, ../ traversal,
    and symlink escapes are provenance failures; only .json/.md sources allowed;
  * every support span additionally passes ipboundary.check_support_span
    (tier word limits, single-line rule for tiers 0/1, full-MCQ tripwire);
  * a card whose source is a cleaned note (notes/) only validates when the
    note's front-matter status is reviewed/promoted (notes_lifecycle;
    full pipeline wiring lands in PR-5);
  * ``sensitive_override`` is NOT blanket clearance: it requires a non-empty
    ``override_reason`` plus ``last_reviewed``, permits only the banks
    explicitly listed in ``allowed_banks``, and can never clear residual-secret
    or full-MCQ failures;
  * ``ground()`` applies the same learner-safety filter as ``for_bank``:
    sensitive cards without a valid override contribute nothing to
    learner-facing answers/citations (defense-in-depth beyond validation).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import ingest, ipboundary, notes_lifecycle

SCHEMA_VERSION = 1
FACTS_DIR = Path(__file__).resolve().parent.parent / "facts"
BANKS_PATH = Path(__file__).resolve().parent.parent / "banks" / "banks.json"
_REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

STATUSES = {"active", "deprecated", "draft"}

# Mirrors spine/schemas/fact-card.schema.json "required" — pinned by
# tests/test_factstore.py::test_required_fields_match_schema.
REQUIRED_FIELDS = (
    "schema_version", "fact_id", "scope", "claim_type", "status", "claim",
    "source", "source_id", "source_tier", "source_fingerprint", "support",
    "tags", "learner_visible", "answer_key_sensitive", "allowed_banks", "reviewed_by",
)

_FACT_ID_RE = re.compile(r"^(D[1-5]|global)\.[a-z0-9][a-z0-9-]*$")
_WS = re.compile(r"\s+")

# Note sources: a card grounded on a cleaned note is only valid when the note
# has been human-reviewed (notes_lifecycle.GROUNDING_ELIGIBLE).
_NOTES_PREFIX = "cc-master-learning-center/notes/"


# --- bank policy (externalized to banks.json — single source of truth) ------ #

_BANK_POLICY_CACHE = {}


def _bank_policy(path=None) -> dict:
    """Load {claim_types, known_banks, eligibility, targets} from banks.json.

    Cached per resolved path. Fail-closed: an unloadable banks.json raises, and
    validate_card converts that into a card error — never a silent skip.
    """
    key = str(Path(path or BANKS_PATH).resolve())
    if key not in _BANK_POLICY_CACHE:
        data = json.loads(Path(key).read_text(encoding="utf-8"))
        eligibility = {ct: set(bs) for ct, bs in data["claim_type_eligibility"].items()}
        known_banks = set(data["banks"])
        targets = {name: bank.get("targets", {}) for name, bank in data["banks"].items()}
        _BANK_POLICY_CACHE[key] = {
            "claim_types": set(eligibility),
            "known_banks": known_banks,
            # Every CC bank is learner-facing (flashcards/quiz/mock all reach
            # the learner), so sensitive cards are quarantined from all of them.
            "learner_facing_banks": set(known_banks),
            "eligibility": eligibility,
            "targets": targets,
        }
    return _BANK_POLICY_CACHE[key]


# --- residual-secrets scan (replaces the OSAI flag regex + llm scan) -------- #

_SECRET_PATTERNS = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("api-key", re.compile(r"\bsk[-_](?:live[-_])?[A-Za-z0-9]{16,}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("pem-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


def _string_leaves(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _string_leaves(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _string_leaves(value)


def residual_secrets(obj) -> list:
    """Category labels of any secret/PII pattern found in the object's strings."""
    found = []
    for leaf in _string_leaves(obj):
        for label, pattern in _SECRET_PATTERNS:
            if label not in found and pattern.search(leaf):
                found.append(label)
    return found


# --- canonicalisation + fingerprint (verbatim from OSAI) ------------------- #

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


# --- JSON-path resolution (structured sources; verbatim) ------------------- #

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
        cur = cur[part]
    return cur


# --- markdown section resolution (adapted; duplicate anchors FAIL CLOSED — a - #
# --- provenance citation must never silently pick between two sections) ------ #

def _slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    return re.sub(r"\s+", "-", s).strip("-")


def _section_text(md_text: str, anchor: str):
    """Return the body text of the section whose heading slug == ``anchor`` (up to the
    next heading of same-or-higher level), or ``None`` if the anchor is absent.

    Deviation from OSAI (reviewer P0): if MORE THAN ONE heading normalises to the
    anchor, this raises — markdown anchors must be unique after slug normalisation,
    because a card could otherwise silently cite the wrong section. Renaming one of
    the colliding headings (or citing a unique heading) is the fix."""
    lines = md_text.splitlines()
    matches = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m and _slug(m.group(2)) == anchor:
            matches.append((i, len(m.group(1))))
    if len(matches) > 1:
        raise ValueError(
            f"duplicate markdown anchor {anchor!r}: {len(matches)} headings normalise "
            "to it — anchors must be unique after slug normalisation (fail-closed)")
    if not matches:
        return None
    start, level = matches[0]
    out = []
    for line in lines[start + 1:]:
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out).strip()


# --- source access (verbatim) ----------------------------------------------- #

def _safe_source_path(root: Path, file_part: str) -> Path:
    """Resolve a card's source path inside ``root``, refusing escapes (reviewer
    R&D: no absolute paths, no ../ traversal, no symlink escape)."""
    if Path(file_part).is_absolute():
        raise ValueError(f"absolute source path not allowed: {file_part!r}")
    resolved = (root / file_part).resolve()
    root_resolved = Path(root).resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise ValueError(f"source path escapes the repo root: {file_part!r}")
    return resolved


def _read_source_value(card: dict, root: Path):
    """Return ``(kind, resolved)`` for a card's source. ``resolved`` is the structured
    value at the JSON path, or the markdown section text. Raises on any provenance
    miss, path escape, or unsupported source extension (only .json/.md are allowed)."""
    source = card["source"]
    kind = _source_kind(source)
    file_part, _, locator = source.partition("#")
    path = _safe_source_path(root, file_part)
    text = path.read_text(encoding="utf-8")   # raises FileNotFoundError if missing
    if kind == "structured":
        return kind, _resolve_path(json.loads(text), locator)
    if kind == "markdown":
        return kind, _section_text(text, locator)
    raise ValueError(f"unsupported source kind for {source!r}")


def compute_fingerprint(card: dict, root: Path = _REPO_ROOT) -> str:
    """Recompute the source fingerprint from the CURRENT source. A change to the
    grounded span changes the hash — that is the drift signal."""
    kind, resolved = _read_source_value(card, root)
    if kind == "markdown" and resolved is None:
        raise ValueError("markdown anchor not found")
    return _sha(_canonical(resolved))


# --- sensitive-override policy (tightened vs OSAI — reviewer P0-2) ---------- #

def _is_sensitive(card: dict) -> bool:
    return bool(card.get("answer_key_sensitive")) or not card.get("learner_visible", False)


def _override_problems(fid: str, card: dict) -> list:
    """Errors for a card that sets sensitive_override. Override is only valid with
    a non-empty override_reason, a last_reviewed date, and a reviewer. It permits
    only the banks explicitly listed in allowed_banks — never blanket clearance."""
    errs = []
    reason = card.get("override_reason")
    if not (isinstance(reason, str) and reason.strip()):
        errs.append(f"{fid}: sensitive_override requires a non-empty override_reason")
    if not card.get("last_reviewed"):
        errs.append(f"{fid}: sensitive_override requires last_reviewed")
    if not card.get("reviewed_by"):
        errs.append(f"{fid}: sensitive_override requires reviewed_by")
    return errs


def _learner_safe(card: dict) -> bool:
    """May this card's content reach learner-facing output? Non-sensitive cards:
    yes. Sensitive cards: only with a fully valid override."""
    if not _is_sensitive(card):
        return True
    return bool(card.get("sensitive_override")) and not _override_problems(
        card.get("fact_id", "<no-id>"), card)


# --- card + store validation ------------------------------------------------ #

def validate_card(card: dict, registry, root: Path = _REPO_ROOT) -> list:
    """Return a list of human-readable errors for one card ([] == valid). Fail-closed:
    anything unverifiable against the authoritative source is an error."""
    errs = []
    fid = card.get("fact_id", "<no-id>")

    # 1. schema + policy tables
    for f in REQUIRED_FIELDS:
        if f not in card:
            errs.append(f"{fid}: missing required field {f!r}")
    if errs:
        return errs
    try:
        policy = _bank_policy()
    except Exception as exc:  # unloadable banks.json — fail closed, never skip
        return [f"{fid}: bank policy unavailable ({exc})"]
    if card["schema_version"] != SCHEMA_VERSION:
        errs.append(f"{fid}: schema_version {card['schema_version']} != {SCHEMA_VERSION}")
    if not _FACT_ID_RE.match(fid):
        errs.append(f"{fid}: fact_id does not match ^(D[1-5]|global).slug$")
    elif fid.split(".", 1)[0] != card["scope"]:
        errs.append(f"{fid}: fact_id prefix does not match scope {card['scope']!r}")
    ctype = card["claim_type"]
    if ctype not in policy["claim_types"]:
        errs.append(f"{fid}: unknown claim_type {ctype!r}")
    if card["status"] not in STATUSES:
        errs.append(f"{fid}: unknown status {card['status']!r}")
    tier = card["source_tier"]
    if not isinstance(tier, int) or not 0 <= tier <= 4:
        errs.append(f"{fid}: source_tier must be an integer 0-4")
    banks = card["allowed_banks"]
    if not isinstance(banks, list) or not banks:
        errs.append(f"{fid}: allowed_banks must be a non-empty list")
        banks = banks if isinstance(banks, list) else []
    for b in banks:
        if b not in policy["known_banks"]:
            errs.append(f"{fid}: allowed_bank {b!r} is not a known bank (banks.json)")
    # bank eligibility by claim_type (defence-in-depth, from banks.json)
    if ctype in policy["eligibility"]:
        for b in banks:
            if b in policy["known_banks"] and b not in policy["eligibility"][ctype]:
                errs.append(f"{fid}: claim_type {ctype!r} is not eligible for bank {b!r}")
    # registry checks: tags + source_id (every card, not just some claim types)
    tags = card["tags"]
    for key in ("domain", "objective", "topic"):
        if key not in tags:
            errs.append(f"{fid}: tags missing {key!r}")
    for d in tags.get("domain", []):
        if not registry.is_domain(d):
            errs.append(f"{fid}: tags.domain {d!r} is not a known domain")
    for oid in tags.get("objective", []):
        if not registry.is_objective(oid):
            errs.append(f"{fid}: tags.objective {oid!r} is not in the objective matrix")
    entry = registry.source_entry(card["source_id"])
    if entry is None:
        errs.append(f"{fid}: source_id {card['source_id']!r} not in source-registry.json")
    elif isinstance(tier, int) and entry.get("tier") != tier:
        errs.append(
            f"{fid}: source_tier {tier} != registry tier {entry.get('tier')} "
            f"for {card['source_id']!r}")

    # 2. answer-key / secret safety. Residual-secret and full-MCQ failures are
    # NEVER clearable by sensitive_override. Scan only content fields — metadata
    # like the fingerprint must not trip the heuristics.
    content = {k: card.get(k) for k in ("claim", "support", "tags", "source", "scope")}
    leaked = residual_secrets(content)
    if leaked:
        errs.append(f"{fid}: a secret/PII survived the card's residual scan ({', '.join(leaked)})")
    if ingest.contains_full_mcq(card["claim"]):
        errs.append(f"{fid}: claim appears to reproduce a full multiple-choice item")
    if isinstance(tier, int):
        errs += [f"{fid}: {p}" for p in ipboundary.check_support_span(card["support"], tier)]
    if _is_sensitive(card):
        if card.get("sensitive_override"):
            errs += _override_problems(fid, card)
        else:
            for b in banks:
                if b in policy["learner_facing_banks"]:
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
        # Deviation from OSAI: canonical-form equality — the schema forces support
        # to be a string while sources may resolve to typed values (e.g. int 700).
        if _canonical(resolved) != _canonical(support):
            errs.append(f"{fid}: support {support!r} != source value {resolved!r} (drift/mismatch)")
    else:  # markdown
        if not isinstance(support, str) or support.strip() == "":
            errs.append(f"{fid}: markdown card needs a non-empty quoted support span")
        elif _WS.sub(" ", support).strip() not in _WS.sub(" ", resolved).strip():
            errs.append(f"{fid}: support span is not present in the current source section")
    # notes-lifecycle rule: cards grounded on cleaned notes need a reviewed note
    file_part = card["source"].partition("#")[0]
    if file_part.startswith(_NOTES_PREFIX):
        note_text = (root / file_part).read_text(encoding="utf-8")
        status_problems = notes_lifecycle.validate_note_status(note_text)
        if status_problems:
            errs += [f"{fid}: {p}" for p in status_problems]
        elif not notes_lifecycle.grounding_allowed(notes_lifecycle.note_status(note_text)):
            errs.append(
                f"{fid}: note {file_part!r} has status "
                f"{notes_lifecycle.note_status(note_text)!r} — only reviewed/promoted "
                "notes may ground fact cards")
    # drift fingerprint (independent of the equality/substring checks above)
    try:
        if compute_fingerprint(card, root) != card["source_fingerprint"]:
            errs.append(f"{fid}: source_fingerprint mismatch — source drifted, re-review required")
    except Exception as exc:  # pragma: no cover - defensive
        errs.append(f"{fid}: could not compute fingerprint ({exc})")

    # 4. the human claim must actually mention the structured value(s) it asserts
    errs += _claim_mentions_support(fid, kind, card)
    return errs


def _claim_mentions_support(fid, kind, card) -> list:
    """The human-readable claim must contain the concrete value(s) it asserts, so a card
    can't say the wrong thing while citing a right source. (Verbatim from OSAI.)"""
    claim = card["claim"]
    if kind == "structured":
        support = card["support"]
        tokens = support if isinstance(support, list) else [support]
        for t in tokens:
            token = _WS.sub(" ", str(t)).strip()  # whitespace-canonical, like equality
            if token not in claim:
                return [f"{fid}: claim does not mention asserted value {token!r}"]
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
    # lifecycle: a deprecated card must tombstone to an existing successor with a
    # stated reason (no silent rename — spec section 3 fact-id lifecycle)
    for fid, card in store.cards.items():
        if card.get("status") == "deprecated":
            succ = card.get("deprecated_by")
            reason = card.get("deprecation_reason")
            if not succ:
                errors.append(f"{fid}: deprecated card must set deprecated_by (no silent rename)")
            elif succ not in store.cards:
                errors.append(f"{fid}: deprecated_by {succ!r} does not resolve to a known card")
            if not (isinstance(reason, str) and reason.strip()):
                errors.append(f"{fid}: deprecated card must set a non-empty deprecation_reason")
    return {"ok": not errors, "errors": errors, "card_errors": card_errors}


# --- bank-item grounding checks (verbatim logic from OSAI) ------------------ #

def is_fact_grounded(item: dict) -> bool:
    # CC bank items declare grounding via source_policy ("factstore|required"); the
    # OSAI-native field is "grounding". Accept both so the frozen validate_item logic
    # applies unchanged to CC items — an additive recognition, not a weakening. (PR-8a.)
    return item.get("grounding") == "factstore" or item.get("source_policy") == "factstore|required"


def validate_item(store, item: dict) -> list:
    """Errors for a fact-grounded item ([] == valid). Enforces: it declares fact_ids;
    every id exists, is active, and is authorised for the item's bank; and every
    expected_keyword is supported by the cited cards (the unsupported_claim_guard)."""
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


# --- deterministic grounding (used by the future quiz/mock runner) ---------- #

# A distinct authority tier for fact-derived citations (structured, highest provenance).
FACT_TIER = "F1"


def ground(store, item: dict) -> dict:
    """Build a deterministic, cited answer for a fact-grounded item from its cited cards.
    Keyed lookup — never TF-IDF — so adding a card cannot change this result.

    Ordering rule (declared): citations preserve the item's requested fact_ids order.
    Learner safety: sensitive cards without a valid override are skipped — their
    content never reaches learner-facing output, even if validation was bypassed."""
    cards = [store.cards.get(fid) for fid in item["fact_ids"]]
    cards = [c for c in cards if c is not None and _learner_safe(c)]
    answer = " ".join(c["claim"] for c in cards)  # missing/unsafe ids drop out and the
    citations = [                                  # grade fails cleanly, never crashes
        {"source": c["source"], "title": c["fact_id"], "tier": FACT_TIER,
         "section": (c["tags"].get("objective") or [None])[0], "fact_id": c["fact_id"],
         "score": 1.0}
        for c in cards
    ]
    return {"refused": False, "abstained": False, "mode": "factstore",
            "answer": answer, "citations": citations, "generative": False}


# --- coverage / capacity report (targets from banks.json) ------------------- #

def coverage_report(store) -> dict:
    from collections import Counter
    policy = _bank_policy()
    active = [c for c in store.cards.values() if c.get("status") == "active"]
    per_scope = Counter(c["scope"] for c in active)
    per_type = Counter(c["claim_type"] for c in active)
    per_status = Counter(c.get("status") for c in store.cards.values())
    per_bank = Counter()
    per_objective = Counter()
    sensitive = 0
    for c in active:
        for b in c["allowed_banks"]:
            per_bank[b] += 1
        for oid in c["tags"].get("objective", []):
            per_objective[oid] += 1
        if _is_sensitive(c):
            sensitive += 1
    # Active card counts per bank per domain vs the banks.json floor/cap targets.
    # Meaningful from PR-6 (first real cards); the plumbing is proven now.
    capacity = {}
    for bank, targets in policy["targets"].items():
        per_domain = {}
        for domain, bounds in targets.items():
            n = sum(
                1 for c in active
                if bank in c["allowed_banks"]
                and (c["scope"] == domain or (domain == "global" and c["scope"] == "global"))
            )
            per_domain[domain] = {
                "cards_eligible": n,
                "floor": bounds["floor"],
                "cap": bounds["cap"],
                "meets_floor": n >= bounds["floor"],
                "within_cap": n <= bounds["cap"],
            }
        capacity[bank] = per_domain
    return {
        "cards_total": len(store.cards),
        "cards_active": len(active),
        "per_scope": dict(per_scope),
        "per_claim_type": dict(per_type),
        "per_bank_capacity": dict(per_bank),   # a card can seed multiple banks
        "per_objective": dict(per_objective),
        "learner_visible": len(active) - sensitive,
        "sensitive": sensitive,
        "by_status": dict(per_status),
        "capacity_vs_targets": capacity,
    }


# --- the store (verbatim from OSAI; for_lab renamed for_scope) -------------- #

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

    def for_scope(self, scope):
        return [c for c in self.cards.values() if c["scope"] == scope]

    def for_bank(self, bank, include_sensitive=False):
        """Active cards authorised for a bank. Sensitive cards without a valid
        override are excluded unless include_sensitive (grader-side use only)."""
        return [c for c in self.cards.values()
                if bank in c["allowed_banks"] and c.get("status") == "active"
                and (include_sensitive or _learner_safe(c))]

    def add(self, card):
        """Insert a card in memory (does not touch disk)."""
        fid = card["fact_id"]
        self.id_counts[fid] = self.id_counts.get(fid, 0) + 1
        self.cards.setdefault(fid, card)
        return self


def freeze(facts_dir=None, root: Path = _REPO_ROOT) -> int:
    """Authoring helper (controlled operator tool): recompute every card's
    source_fingerprint from the current source and rewrite the facts files.
    Rewrites fingerprints ONLY — never claim/source/support. Refuses (raises)
    when any support no longer resolves. Never run in the validation path —
    validation is read-only."""
    facts_dir = Path(facts_dir or FACTS_DIR)
    n = 0
    for path in sorted(facts_dir.glob("*.json")):
        cards = json.loads(path.read_text(encoding="utf-8"))
        for card in cards:
            card["source_fingerprint"] = compute_fingerprint(card, root)
            n += 1
        path.write_text(json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return n
