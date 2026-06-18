import math

from questionnaire.categories import CATEGORY_KEYS
from questionnaire.mapping import (answers_to_profile_fields, compute_thresholds,
                                   compute_weights, load_form)

FORM = load_form()

BASE_ANSWERS = {
    "rank_categories": list(CATEGORY_KEYS),  # in declared order
    "risk_appetite": "balanced",
    "deal_breakers": ["open_hipaa_breach", "no_soc2"],
}


def test_weights_sum_to_one():
    cats = compute_weights(BASE_ANSWERS, FORM)
    assert math.isclose(sum(c["weight"] for c in cats.values()), 1.0, abs_tol=1e-3)


def test_top_ranked_outweighs_bottom():
    cats = compute_weights(BASE_ANSWERS, FORM)
    first, last = CATEGORY_KEYS[0], CATEGORY_KEYS[-1]
    assert cats[first]["weight"] > cats[last]["weight"]
    assert cats[first]["rank"] == 1


def test_slider_increases_weight():
    low = compute_weights({**BASE_ANSWERS, "slider_cost": 1}, FORM)
    high = compute_weights({**BASE_ANSWERS, "slider_cost": 5}, FORM)
    assert high["cost"]["weight"] > low["cost"]["weight"]


def test_ranking_must_be_complete():
    bad = {**BASE_ANSWERS, "rank_categories": CATEGORY_KEYS[:-1]}
    try:
        compute_weights(bad, FORM)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_thresholds_by_appetite():
    assert compute_thresholds({"risk_appetite": "conservative"}, FORM)["approve"] == 80
    assert compute_thresholds({"risk_appetite": "lenient"}, FORM)["escalate"] == 40


def test_deal_breakers_mapped():
    fields = answers_to_profile_fields(BASE_ANSWERS, FORM)
    factors = {d["factor"] for d in fields["deal_breakers"]}
    assert factors == {"open_hipaa_breach", "no_soc2"}
