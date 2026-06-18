"""
Deterministic mapping from questionnaire answers to a hospital profile.
No LLM here — same answers always produce the same weights. Unit-tested.
"""
from __future__ import annotations

import pathlib
from typing import Any

import yaml

from .categories import CATEGORY_KEYS

_QUESTIONS_PATH = pathlib.Path(__file__).parent / "questions.yaml"


def load_form() -> dict[str, Any]:
    """Load the questionnaire definition (questions.yaml)."""
    with open(_QUESTIONS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _slider_category_map(form: dict[str, Any]) -> dict[str, str]:
    """slider question id -> category key."""
    return {
        q["category"]: q["id"]
        for q in form["questions"]
        if q.get("type") == "slider"
    }


def compute_weights(answers: dict[str, Any], form: dict[str, Any]) -> dict[str, dict]:
    """
    Build the normalized `categories` block.

    answers:
      rank_categories: ordered list of category keys (most -> least important)
      slider_<category>: int 1-5  (optional; default 3 = neutral)
    """
    ranking = answers["rank_categories"]
    missing = set(CATEGORY_KEYS) - set(ranking)
    if missing:
        raise ValueError(f"ranking is missing categories: {sorted(missing)}")
    if len(ranking) != len(CATEGORY_KEYS):
        raise ValueError("ranking must contain each category exactly once")

    rank_points = form["rank_points"]
    multipliers = {int(k): v for k, v in form["slider_multipliers"].items()}
    slider_for = {q["category"] for q in form["questions"] if q.get("type") == "slider"}

    raw: dict[str, float] = {}
    ranks: dict[str, int] = {}
    for position, key in enumerate(ranking):
        base = rank_points[position]
        ranks[key] = position + 1
        if key in slider_for:
            slider_val = int(answers.get(f"slider_{key}", 3))
            base *= multipliers[slider_val]
        raw[key] = base

    total = sum(raw.values())
    return {
        key: {"weight": round(raw[key] / total, 4), "rank": ranks[key]}
        for key in CATEGORY_KEYS
    }


def compute_thresholds(answers: dict[str, Any], form: dict[str, Any]) -> dict[str, int]:
    """Map the risk_appetite choice to {approve, escalate} thresholds."""
    appetite = answers.get("risk_appetite", "balanced")
    table = form["risk_appetite"]
    if appetite not in table:
        raise ValueError(f"unknown risk_appetite: {appetite!r}")
    return dict(table[appetite])


def compute_deal_breakers(answers: dict[str, Any], form: dict[str, Any]) -> list[dict]:
    """Turn checked deal-breaker option ids into deal-breaker rule entries."""
    checked = set(answers.get("deal_breakers", []))
    dq = next(q for q in form["questions"] if q["id"] == "deal_breakers")
    out = []
    for opt in dq["options"]:
        if opt["id"] in checked:
            out.append({
                "factor": opt["id"],
                "category": opt["category"],
                "rule": opt["rule"],
            })
    return out


def answers_to_profile_fields(answers: dict[str, Any], form: dict[str, Any] | None = None) -> dict:
    """Full deterministic transform: answers -> profile field dict."""
    form = form or load_form()
    return {
        "categories": compute_weights(answers, form),
        "thresholds": compute_thresholds(answers, form),
        "deal_breakers": compute_deal_breakers(answers, form),
    }
