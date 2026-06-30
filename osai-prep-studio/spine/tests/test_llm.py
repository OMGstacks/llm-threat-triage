"""The optional LLM provider seam + the tutor's generative path.

No live API call: a fake provider drives the seam so the grounding gate, the
extractive fallback, and the taxonomy guard are all verified offline. The default
(no provider) path stays byte-for-byte the extractive behavior."""

import os

from osai_spine import llm as llm_mod
from osai_spine.taxonomy import TaxonomyRegistry
from osai_spine.tutor import Tutor


class _FakeProvider:
    """Stands in for LLMProvider — records the call and returns a canned answer."""

    def __init__(self, reply=None, raises=False):
        self.reply, self.raises, self.calls = reply, raises, []

    def complete(self, system, user, *, model=None, max_tokens=700, cached_prefix=None):
        self.calls.append({"system": system, "user": user, "cached_prefix": cached_prefix})
        if self.raises:
            raise RuntimeError("simulated API error")
        return self.reply


def test_enabled_is_off_without_optin(monkeypatch):
    # No SDK is installed in CI, so the seam must report disabled regardless of flags.
    monkeypatch.setenv("OSAI_LLM", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    # enabled() also requires the SDK; absent here -> False, never touching the network
    assert llm_mod.enabled() is (llm_mod.sdk_available() and True)
    st = llm_mod.status()
    assert st["model_quality"] == "claude-opus-4-8"
    assert set(st) >= {"enabled", "sdk_installed", "key_present", "model_quality", "model_bulk"}


def test_default_tutor_is_extractive():
    t = Tutor(registry=TaxonomyRegistry())  # no llm
    r = t.ask("what is prompt injection")
    assert r["abstained"] is False
    assert r["generative"] is False
    assert r["citations"]


def test_generative_answer_used_when_grounded():
    fake = _FakeProvider(reply="Prompt injection (LLM01:2025) overrides instructions. [1]")
    t = Tutor(registry=TaxonomyRegistry(), llm=fake)
    r = t.ask("what is prompt injection")
    assert r["generative"] is True
    assert r["answer"].startswith("Prompt injection")
    assert r["taxonomy_ids_valid"] is True
    # the seam was handed the retrieved corpus as a cacheable prefix
    assert fake.calls and fake.calls[0]["cached_prefix"].startswith("SOURCES:")


def test_hallucinated_id_falls_back_to_extractive():
    fake = _FakeProvider(reply="See LLM77:2025, a made-up category.")  # not a real id
    t = Tutor(registry=TaxonomyRegistry(), llm=fake)
    r = t.ask("what is prompt injection")
    assert r["generative"] is False          # rejected -> extractive fallback
    assert "LLM77:2025" not in r["answer"]
    assert r["taxonomy_ids_valid"] is True


def test_provider_error_falls_back_to_extractive():
    t = Tutor(registry=TaxonomyRegistry(), llm=_FakeProvider(raises=True))
    r = t.ask("what is prompt injection")
    assert r["generative"] is False
    assert r["citations"]


def test_abstention_unaffected_by_provider():
    # An off-corpus query must still abstain — the LLM is never consulted.
    fake = _FakeProvider(reply="(should never be used)")
    t = Tutor(registry=TaxonomyRegistry(), llm=fake)
    r = t.ask("sourdough bread recipe at altitude")
    assert r["abstained"] is True
    assert fake.calls == []
