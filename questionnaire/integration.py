"""
Glue between the Band agents and the scoring module.

`score_vendor(findings_text, llm)` runs the full pipeline:
  extractor (LLM) -> scorer (pure) -> gap loop -> formatted scorecard string.

The active hospital profile is selected by the HEALTHVET_PROFILE env var
(a profile slug). If no profile is configured/found, scoring is skipped and the
agents fall back to their original LLM-only behavior.
"""
from __future__ import annotations

import logging
import os

from . import extractor, gap, scorer
from .profile import HospitalProfile

logger = logging.getLogger("questionnaire.integration")


def active_profile() -> HospitalProfile | None:
    slug = os.getenv("HEALTHVET_PROFILE")
    if not slug:
        logger.info("HEALTHVET_PROFILE not set — vendor fit scoring disabled.")
        return None
    try:
        return HospitalProfile.load(slug)
    except FileNotFoundError:
        logger.warning("Profile %r not found in questionnaire/profiles — scoring disabled.", slug)
        return None


async def score_vendor(findings_text: str, llm, *, vendor_hint: str = "") -> str | None:
    """
    Returns a formatted scorecard block (str) to embed in a report, or None if
    scoring is disabled. In 'ask' gap mode there is no synchronous channel to the
    hospital, so uncovered factors are surfaced as disclosures for follow-up
    rather than blocking the pipeline.
    """
    profile = active_profile()
    if profile is None:
        return None

    extracted = extractor.parse_extraction("") if not findings_text else \
        await extractor.extract(findings_text, llm, vendor_hint=vendor_hint)

    disclosures = gap.resolve(profile, extracted.get("uncovered", []),
                              ask_fn=None)  # auto applies; ask records follow-ups
    result = scorer.score(
        profile, extracted["scores"],
        vendor=extracted.get("vendor", vendor_hint or "Vendor"),
        deal_breaker_flags=extracted.get("deal_breaker_flags"),
    )

    block = [
        "FIT SCORE (vs hospital profile: "
        f"{profile.hospital} v{profile.version}, mode={profile.mode})",
        result.to_text(),
    ]
    if disclosures:
        block.append("\nUncovered factors (require hospital confirmation):")
        for d in disclosures:
            block.append("  " + d["message"])
    return "\n".join(block)
