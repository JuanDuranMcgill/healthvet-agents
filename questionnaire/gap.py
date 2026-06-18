"""
Gap-resolution loop — the "smart & critical" part.

When the extractor surfaces material factors the profile's categories don't
capture, this decides what to do based on profile.settings.gap_resolution_mode:

  ask  (default): emit ONE targeted question per material factor, take the
        hospital's answer, permanently add a weighted category to the profile,
        and re-score. The profile improves over time.

  auto: assign a best-guess weight from the factor's stated materiality, mark it
        `assumed=True`, and rely on the caller to disclose every assumption in
        the final report. Transparency is mandatory in this mode.

A new gap factor is mapped onto an existing category when it clearly belongs to
one; otherwise it becomes a new ad-hoc category keyed by a slug of its name.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from .categories import CATEGORY_KEYS
from .profile import HospitalProfile

# materiality -> default weight used in auto mode (pre-renormalization)
_AUTO_WEIGHTS = {"high": 0.15, "medium": 0.08, "low": 0.03}
# answer choice (ask mode) -> weight
_ASK_WEIGHTS = {"deal-breaker": 0.25, "high": 0.15, "medium": 0.08, "low": 0.03, "ignore": 0.0}

# Only factors at/above this materiality trigger the loop, so it fires rarely.
_MATERIAL = {"high", "medium"}


def _factor_key(factor: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", factor.lower()).strip("_")
    return slug or "uncovered_factor"


def material_factors(uncovered: list[dict]) -> list[dict]:
    """Filter the extractor's uncovered list down to the ones worth acting on."""
    out = []
    for u in uncovered:
        if u.get("materiality", "low").lower() in _MATERIAL:
            key = _factor_key(u["factor"])
            if key not in CATEGORY_KEYS and key not in (out_keys := {x["key"] for x in out}):
                out.append({**u, "key": key})
    return out


def question_for(factor: dict) -> str:
    return (
        f"Uncovered factor: '{factor['factor']}'. {factor.get('evidence', '')}\n"
        f"How much should this weigh? (deal-breaker / high / medium / low / ignore)"
    )


def resolve(profile: HospitalProfile, uncovered: list[dict], *,
            ask_fn: Callable[[str], str] | None = None) -> list[dict]:
    """
    Process uncovered factors per the profile's mode. Mutates `profile` (adds
    categories, bumps version, logs assumptions). Returns a list of disclosures
    describing what happened — the caller surfaces these to the hospital.

    `ask_fn(question) -> answer` is required for mode='ask' (e.g. a Band prompt or
    terminal input). In 'auto' mode it is ignored.
    """
    disclosures: list[dict] = []
    factors = material_factors(uncovered)

    for f in factors:
        key, label = f["key"], f["factor"]

        if profile.mode == "auto":
            weight = _AUTO_WEIGHTS.get(f.get("materiality", "low").lower(), 0.03)
            profile.add_category(key, weight, source="gap:auto", label=label, assumed=True)
            disclosures.append({
                "factor": label, "key": key, "mode": "auto", "assumed": True,
                "weight": profile.weight(key),
                "message": f"[!] Assumed '{label}' = weight {profile.weight(key):.3f} "
                           f"(materiality {f.get('materiality')}). Please confirm.",
            })
            continue

        # ask mode
        if ask_fn is None:
            disclosures.append({
                "factor": label, "key": key, "mode": "ask", "assumed": False,
                "weight": 0.0, "message": f"Uncovered factor '{label}' needs a hospital answer (no ask_fn).",
            })
            continue
        answer = (ask_fn(question_for(f)) or "ignore").strip().lower()
        weight = _ASK_WEIGHTS.get(answer, 0.0)
        if weight <= 0:
            disclosures.append({
                "factor": label, "key": key, "mode": "ask", "assumed": False,
                "weight": 0.0, "message": f"Hospital chose to ignore '{label}'.",
            })
            continue
        profile.add_category(key, weight, source=f"gap:ask({answer})", label=label, assumed=False)
        if answer == "deal-breaker":
            profile.deal_breakers.append({"factor": key, "category": key,
                                          "rule": f"{label} flagged"})
        disclosures.append({
            "factor": label, "key": key, "mode": "ask", "assumed": False,
            "weight": profile.weight(key),
            "message": f"Added '{label}' = weight {profile.weight(key):.3f} (hospital said '{answer}').",
        })

    return disclosures
