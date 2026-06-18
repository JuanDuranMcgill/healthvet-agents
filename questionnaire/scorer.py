"""
Pure scoring engine — no LLM, fully deterministic and unit-tested.

Takes a HospitalProfile + extracted per-category vendor scores (0-10) and
produces a weighted fit score (0-100), a verdict, and a transparent breakdown.
Deal-breakers hard-cap the fit and force the verdict.
"""
from __future__ import annotations

import dataclasses

from .categories import CATEGORY_KEYS, category_label
from .profile import HospitalProfile

APPROVE, ESCALATE, REJECT = "APPROVE", "ESCALATE", "REJECT"

# Where a triggered deal-breaker pins the fit (just under any reasonable reject line).
DEAL_BREAKER_FIT_CAP = 10


@dataclasses.dataclass
class CategoryContribution:
    key: str
    label: str
    score: float       # 0-10 (vendor)
    weight: float      # 0-1
    contribution: float  # points added to the 0-100 fit


@dataclasses.dataclass
class ScoreResult:
    vendor: str
    fit: int
    verdict: str
    breakdown: list[CategoryContribution]
    triggered_deal_breakers: list[str]
    assumptions_applied: list[dict]

    def to_text(self) -> str:
        lines = [f"{self.vendor}: {self.fit}/100  {self.verdict}"]
        for c in self.breakdown:
            lines.append(
                f"  {c.label:<48} {c.score:>4.1f}/10 x {c.weight:.3f} = {c.contribution:5.1f}"
            )
        if self.triggered_deal_breakers:
            lines.append("  [!] DEAL-BREAKERS TRIGGERED: " + ", ".join(self.triggered_deal_breakers))
        for a in self.assumptions_applied:
            tag = "ASSUMED" if a.get("assumed") else "added"
            lines.append(f"  - {tag}: {a['label']} (weight {a['weight']:.3f}, {a['source']})")
        return "\n".join(lines)


def _check_deal_breakers(profile: HospitalProfile, flags: set[str]) -> list[str]:
    """
    A deal-breaker triggers if its `factor` id appears in the extractor's
    `deal_breaker_flags` set. Keeps rule-matching simple and explicit.
    """
    return [d["factor"] for d in profile.deal_breakers if d["factor"] in flags]


def _verdict_for_fit(fit: int, thresholds: dict) -> str:
    if fit >= thresholds["approve"]:
        return APPROVE
    if fit >= thresholds["escalate"]:
        return ESCALATE
    return REJECT


def score(profile: HospitalProfile, scores: dict[str, float],
          *, vendor: str = "Vendor", deal_breaker_flags: set[str] | None = None) -> ScoreResult:
    """
    scores: category_key -> 0-10. Missing categories count as 0 (no evidence).
    deal_breaker_flags: set of deal-breaker `factor` ids the extractor detected.
    """
    flags = set(deal_breaker_flags or set())
    breakdown: list[CategoryContribution] = []
    fit_raw = 0.0
    for key in profile.categories:
        weight = profile.weight(key)
        s = float(scores.get(key, 0.0))
        s = max(0.0, min(10.0, s))
        contribution = (s / 10.0) * weight * 100.0
        fit_raw += contribution
        breakdown.append(CategoryContribution(
            key=key, label=category_label(key), score=s,
            weight=weight, contribution=round(contribution, 1),
        ))
    breakdown.sort(key=lambda c: -c.contribution)

    triggered = _check_deal_breakers(profile, flags)
    if triggered:
        fit = min(DEAL_BREAKER_FIT_CAP, round(fit_raw))
        verdict = REJECT
    else:
        fit = round(fit_raw)
        verdict = _verdict_for_fit(fit, profile.thresholds)

    return ScoreResult(
        vendor=vendor,
        fit=fit,
        verdict=verdict,
        breakdown=breakdown,
        triggered_deal_breakers=triggered,
        assumptions_applied=list(profile.assumptions),
    )


def rank(profile: HospitalProfile, vendors: list[dict]) -> list[ScoreResult]:
    """
    vendors: [{"vendor": str, "scores": {...}, "deal_breaker_flags": set}, ...]
    Returns ScoreResults sorted best-fit first (deal-breaker rejects sink).
    """
    results = [
        score(profile, v["scores"], vendor=v.get("vendor", "Vendor"),
              deal_breaker_flags=v.get("deal_breaker_flags"))
        for v in vendors
    ]
    results.sort(key=lambda r: (bool(r.triggered_deal_breakers), -r.fit))
    return results
