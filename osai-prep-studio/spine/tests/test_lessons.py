"""PR32 — the narrated-lesson batch. Proves, offline and deterministically, for every
authored lesson (the L03 pilot + the three PR32 lessons):

  * the script renders through the shared ``osai-narrate`` package (via the ``narration``
    adapter) into a deterministic plan;
  * the committed web artifacts (``web/public/lessons/<id>.manifest.json`` + ``.vtt``) equal
    what the seam renders — so the player can never show stale data;
  * every taxonomy tag (frameworks / detector) is real (anti-hallucination);
  * the authored content carries no flag/secret/PII.

And that the course-side catalog is drift-proof: the committed ``index.json`` equals the
builder's output, lists every lesson, and is stably ordered.
"""

import json
from pathlib import Path

import pytest

from osai_spine import lessons as les
from osai_spine import llm
from osai_spine import narration as nar
from osai_spine.taxonomy import TaxonomyRegistry

_SPINE = Path(__file__).resolve().parents[1]
_WEB = _SPINE.parent / "web" / "public" / "lessons"
LESSON_IDS = ["L03", "T2-L01", "T3-L02", "T6-L01"]


def _script(lid: str) -> dict:
    return json.loads((_SPINE / "lessons" / f"{lid}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry():
    return TaxonomyRegistry()


# --- every lesson renders through the shared package, deterministically ------- #

@pytest.mark.parametrize("lid", LESSON_IDS)
def test_lesson_parses_and_is_deterministic(lid):
    plan = nar.render_plan(_script(lid))
    assert plan["lesson_id"] == lid and plan["segment_count"] >= 8
    assert all(s["id"] and s["text"] for s in plan["segments"])
    assert plan == nar.render_plan(_script(lid))          # deterministic


# --- committed web artifacts must equal the seam output (no drift) ------------ #

@pytest.mark.parametrize("lid", LESSON_IDS)
def test_committed_manifest_matches_seam(lid):
    committed = json.loads((_WEB / f"{lid}.manifest.json").read_text(encoding="utf-8"))
    assert committed == nar.render_plan(_script(lid))


@pytest.mark.parametrize("lid", LESSON_IDS)
def test_committed_vtt_matches_seam(lid):
    committed = (_WEB / f"{lid}.vtt").read_text(encoding="utf-8").strip()
    assert committed == nar.to_vtt(nar.render_plan(_script(lid))).strip()


# --- taxonomy tags are real; content carries no secrets ----------------------- #

@pytest.mark.parametrize("lid", LESSON_IDS)
def test_lesson_taxonomy_tags_are_real(lid, registry):
    sc = _script(lid)
    for tid in les._frameworks_of(sc):
        assert registry.is_owasp(tid) or registry.is_atlas(tid), f"unknown framework id: {tid}"
    det = sc.get("detector")
    if det is not None:
        assert registry.is_detector(det), f"detector not in detector_catalog(): {det}"


@pytest.mark.parametrize("lid", LESSON_IDS)
def test_lesson_has_no_secret_material(lid):
    # authored narration must never carry a flag/secret/PII (defense-in-depth on our own files)
    assert llm.residual_secrets(_script(lid)) == []


# --- the /lessons catalog (index.json) is drift-proof against the scripts ------ #

def test_committed_index_matches_catalog():
    committed = json.loads((_WEB / "index.json").read_text(encoding="utf-8"))
    assert committed == les.catalog()


def test_index_lists_every_lesson():
    cat = les.catalog()
    assert cat["count"] == len(LESSON_IDS)
    assert sorted(c["lesson_id"] for c in cat["lessons"]) == sorted(LESSON_IDS)


def test_catalog_is_ordered_by_track_then_id():
    cards = les.catalog()["lessons"]
    keys = [(c["track"], c["lesson_id"]) for c in cards]
    assert keys == sorted(keys)


def test_catalog_cards_carry_render_summary_and_frameworks(registry):
    for c in les.catalog()["lessons"]:
        assert c["segment_count"] >= 8 and ":" in c["est_duration"]
        for tid in c["frameworks"]:
            assert registry.is_owasp(tid) or registry.is_atlas(tid)


def test_build_all_is_idempotent_and_audio_free(tmp_path):
    r1 = les.build_all(web_dir=tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    les.build_all(web_dir=tmp_path)                       # rebuild → byte-identical
    second = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert first == second
    assert r1["count"] == len(LESSON_IDS)
    # offline builder emits only manifests / captions / the index — never audio
    assert all(n.endswith((".manifest.json", ".vtt", ".json")) for n in second)
    assert not any(n.endswith(".mp3") for n in second)


def test_committed_artifacts_are_byte_stable_with_the_builder(tmp_path):
    """A fresh build reproduces the committed web artifacts byte-for-byte — the committed
    files are exactly what `osai_spine.cli lessons build` emits, so they can't silently drift."""
    les.build_all(web_dir=tmp_path)
    for lid in LESSON_IDS:
        for suffix in (".manifest.json", ".vtt"):
            built = (tmp_path / f"{lid}{suffix}").read_bytes()
            committed = (_WEB / f"{lid}{suffix}").read_bytes()
            assert built == committed, f"{lid}{suffix} drifted from the builder output"
    assert (tmp_path / "index.json").read_bytes() == (_WEB / "index.json").read_bytes()
