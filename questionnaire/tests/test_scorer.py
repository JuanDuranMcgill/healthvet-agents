from questionnaire.mapping import answers_to_profile_fields
from questionnaire.categories import CATEGORY_KEYS
from questionnaire.profile import HospitalProfile
from questionnaire import scorer

ANSWERS = {
    "rank_categories": list(CATEGORY_KEYS),
    "risk_appetite": "balanced",
    "deal_breakers": ["open_hipaa_breach"],
}


def make_profile(mode="ask"):
    return HospitalProfile.from_fields("Test Hospital", answers_to_profile_fields(ANSWERS), mode=mode)


def test_perfect_vendor_scores_100_and_approves():
    prof = make_profile()
    scores = {k: 10 for k in CATEGORY_KEYS}
    r = scorer.score(prof, scores, vendor="Perfect")
    assert r.fit == 100
    assert r.verdict == scorer.APPROVE


def test_zero_vendor_rejects():
    prof = make_profile()
    r = scorer.score(prof, {k: 0 for k in CATEGORY_KEYS}, vendor="Awful")
    assert r.fit == 0
    assert r.verdict == scorer.REJECT


def test_deal_breaker_hard_caps_and_rejects():
    prof = make_profile()
    scores = {k: 10 for k in CATEGORY_KEYS}  # otherwise perfect
    r = scorer.score(prof, scores, vendor="Breached",
                     deal_breaker_flags={"open_hipaa_breach"})
    assert r.verdict == scorer.REJECT
    assert r.fit <= scorer.DEAL_BREAKER_FIT_CAP
    assert "open_hipaa_breach" in r.triggered_deal_breakers


def test_breakdown_contributions_sum_to_fit():
    prof = make_profile()
    scores = {k: (i % 11) for i, k in enumerate(CATEGORY_KEYS)}
    r = scorer.score(prof, scores)
    assert abs(sum(c.contribution for c in r.breakdown) - r.fit) < 1.0


def test_ranking_sinks_deal_breaker_vendor():
    prof = make_profile()
    good = {"vendor": "Good", "scores": {k: 7 for k in CATEGORY_KEYS}, "deal_breaker_flags": set()}
    flagged = {"vendor": "Flagged", "scores": {k: 10 for k in CATEGORY_KEYS},
               "deal_breaker_flags": {"open_hipaa_breach"}}
    ranked = scorer.rank(prof, [flagged, good])
    assert ranked[0].vendor == "Good"
    assert ranked[-1].vendor == "Flagged"
