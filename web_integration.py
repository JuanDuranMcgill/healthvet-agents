"""
Bridge between the web server and the questionnaire/quantification engine.

- exposes the questionnaire definition to the frontend
- builds + saves a HospitalProfile from submitted answers (deterministic weights)
- scores a vendor's agent report against the active profile (extract -> score ->
  gap-resolution), returning a fit score + verdict + breakdown for the UI
"""
from __future__ import annotations

import os

import yaml

from questionnaire import cli as q_cli
from questionnaire import extractor, gap, scorer
from questionnaire.profile import HospitalProfile

_Q_DIR = os.path.join(os.path.dirname(__file__), "questionnaire")


def questionnaire_json() -> dict:
    """Return questions.yaml as a JSON-able dict for the frontend."""
    with open(os.path.join(_Q_DIR, "questions.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_profile(answers: dict) -> HospitalProfile:
    """
    answers = {
      slug, hospital, ranks:{cat:1-9}, sliders:{cat:1-5},
      deal_breakers:[factor_id,...], risk_appetite:id, gap_mode:'ask'|'auto'
    }
    """
    form = questionnaire_json()
    slug = answers.get("slug") or "hospital"
    ranks = {k: int(v) for k, v in answers.get("ranks", {}).items()}
    sliders = {k: int(v) for k, v in answers.get("sliders", {}).items()}

    weights = q_cli.compute_weights(ranks, sliders)

    # resolve selected deal-breakers from the form definition
    selected = set(answers.get("deal_breakers", []))
    dbs = [
        {"factor": db["factor"], "category": db["category"], "rule": db["rule"]}
        for db in form["deal_breakers"] if db["factor"] in selected
    ]

    # risk appetite -> thresholds
    appetite_id = answers.get("risk_appetite", "balanced")
    appetite = next((o for o in form["risk_appetite"]["options"] if o["id"] == appetite_id),
                    form["risk_appetite"]["options"][1])

    profile = HospitalProfile(slug)
    if answers.get("hospital"):
        profile.hospital = answers["hospital"]
    profile.categories = weights
    profile.deal_breakers = dbs
    profile.thresholds = appetite["thresholds"]
    profile.settings = {"gap_resolution_mode": answers.get("gap_mode", "ask")}
    profile.rationale = f"Built via web questionnaire. Risk appetite: {appetite_id}."
    profile.save()
    return profile


def load_profile(slug: str) -> HospitalProfile | None:
    path = os.path.join(_Q_DIR, "profiles", f"{slug}.yaml")
    if not os.path.exists(path):
        return None
    return HospitalProfile(slug).load()


def profile_to_dict(profile: HospitalProfile) -> dict:
    return {
        "slug": profile.slug,
        "hospital": profile.hospital,
        "version": profile.version,
        "categories": profile.categories,
        "deal_breakers": profile.deal_breakers,
        "thresholds": profile.thresholds,
        "settings": profile.settings,
        "rationale": profile.rationale,
        "assumptions": profile.assumptions,
    }


def score_report(profile: HospitalProfile, report_text: str, vendor: str = "Vendor") -> dict:
    """
    Full quantification pipeline against the active profile:
      extract per-category scores -> resolve gaps (auto/ask) -> weighted fit.
    Returns a dict the frontend can render, or {"error": ...} on failure.
    """
    extracted = extractor.extract_findings(report_text)

    # gap resolution: in the web context we force 'auto' so the pipeline never
    # blocks on input(); every assumption is surfaced in the result for the user.
    uncovered = extracted.get("uncovered", [])
    original_mode = profile.settings.get("gap_resolution_mode", "ask")
    profile.settings["gap_resolution_mode"] = "auto"
    try:
        gap.resolve_gaps(uncovered, profile)
    finally:
        profile.settings["gap_resolution_mode"] = original_mode

    result = scorer.score_vendor(profile, extracted)
    result["vendor"] = vendor
    result["uncovered"] = uncovered
    result["assumptions"] = profile.assumptions
    result["profile_version"] = profile.version
    return result
