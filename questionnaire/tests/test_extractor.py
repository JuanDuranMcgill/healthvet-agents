from questionnaire.categories import CATEGORY_KEYS
from questionnaire.extractor import parse_extraction

GOOD_JSON = """```json
{
  "vendor": "Veradigm",
  "scores": {
    "patient_safety": {"score": 6, "evidence": "some studies", "confidence": 0.5},
    "security_breach": {"score": 3, "evidence": "$10.5M settlement", "confidence": 0.9}
  },
  "deal_breaker_flags": ["open_hipaa_breach"],
  "uncovered": [{"factor": "EU data residency", "evidence": "PHI in EU", "materiality": "high"}]
}
```"""


def test_parses_fenced_json_and_defaults_missing_categories():
    out = parse_extraction(GOOD_JSON)
    assert out["vendor"] == "Veradigm"
    # every known category present, missing ones default to neutral 5
    assert set(out["scores"]) == set(CATEGORY_KEYS)
    assert out["scores"]["security_breach"] == 3.0
    assert out["scores"]["cost"] == 5.0  # not provided -> neutral
    assert out["deal_breaker_flags"] == {"open_hipaa_breach"}
    assert out["uncovered"][0]["factor"] == "EU data residency"


def test_tolerates_leading_prose():
    raw = 'Here is the JSON:\n{"vendor":"X","scores":{},"uncovered":[]}'
    out = parse_extraction(raw)
    assert out["vendor"] == "X"
    assert out["scores"]["patient_safety"] == 5.0


def test_scores_clamped():
    raw = '{"vendor":"X","scores":{"cost":{"score":99}},"uncovered":[]}'
    out = parse_extraction(raw)
    assert out["scores"]["cost"] == 10.0
