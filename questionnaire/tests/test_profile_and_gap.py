import math

from questionnaire.categories import CATEGORY_KEYS
from questionnaire.mapping import answers_to_profile_fields
from questionnaire.profile import HospitalProfile
from questionnaire import gap

ANSWERS = {
    "rank_categories": list(CATEGORY_KEYS),
    "risk_appetite": "balanced",
    "deal_breakers": [],
}


def make_profile(mode="ask"):
    return HospitalProfile.from_fields("Test Hospital", answers_to_profile_fields(ANSWERS), mode=mode)


def test_save_load_roundtrip(tmp_path):
    prof = make_profile()
    prof.save(profiles_dir=tmp_path, updated="2026-06-18")
    loaded = HospitalProfile.load(prof.slug, profiles_dir=tmp_path)
    assert loaded.hospital == prof.hospital
    assert loaded.categories == prof.categories
    assert loaded.thresholds == prof.thresholds


def test_add_category_renormalizes_and_bumps_version():
    prof = make_profile()
    v0 = prof.version
    prof.add_category("data_residency_eu", 0.15, source="gap:auto", assumed=True)
    assert prof.version == v0 + 1
    assert math.isclose(sum(c["weight"] for c in prof.categories.values()), 1.0, abs_tol=1e-3)
    assert prof.assumptions[-1]["assumed"] is True


def test_gap_auto_mode_adds_and_discloses():
    prof = make_profile(mode="auto")
    uncovered = [{"factor": "EU data residency", "evidence": "PHI in Frankfurt", "materiality": "high"}]
    disc = gap.resolve(prof, uncovered)
    assert len(disc) == 1
    assert disc[0]["assumed"] is True
    assert any("eu_data_residency" == k for k in prof.categories)


def test_gap_ask_mode_uses_answer():
    prof = make_profile(mode="ask")
    uncovered = [{"factor": "EU data residency", "evidence": "PHI in Frankfurt", "materiality": "high"}]
    disc = gap.resolve(prof, uncovered, ask_fn=lambda q: "deal-breaker")
    assert disc[0]["assumed"] is False
    assert any(d["factor"] == "eu_data_residency" for d in prof.deal_breakers)


def test_low_materiality_factor_ignored():
    prof = make_profile(mode="auto")
    uncovered = [{"factor": "minor UI quirk", "evidence": "x", "materiality": "low"}]
    disc = gap.resolve(prof, uncovered)
    assert disc == []
