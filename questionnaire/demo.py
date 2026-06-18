"""
Offline end-to-end demo — no API keys, no Band, no LLM.

Builds two sample hospital profiles from canned answers, feeds canned vendor
findings through the scorer, runs the gap loop in both modes, and prints the
ranked output. Run:  python -m questionnaire.demo
"""
from __future__ import annotations

from . import gap, scorer
from .mapping import answers_to_profile_fields
from .profile import HospitalProfile

# --- a speed/cost-driven rural hospital ---
RURAL_ANSWERS = {
    "rank_categories": ["deployment_speed", "cost", "support_service", "patient_safety",
                        "security_breach", "integration_interop", "regulatory_compliance",
                        "vendor_stability", "data_transparency"],
    "slider_deployment_speed": 5, "slider_cost": 5, "slider_patient_safety": 3,
    "slider_security_breach": 2, "slider_integration_interop": 2,
    "deal_breakers": ["open_hipaa_breach"],
    "risk_appetite": "lenient",
}

# --- a safety/compliance-driven academic center ---
ACADEMIC_ANSWERS = {
    "rank_categories": ["patient_safety", "regulatory_compliance", "security_breach",
                        "integration_interop", "data_transparency", "vendor_stability",
                        "support_service", "deployment_speed", "cost"],
    "slider_patient_safety": 5, "slider_security_breach": 5, "slider_deployment_speed": 1,
    "slider_cost": 2, "slider_integration_interop": 4,
    "deal_breakers": ["open_hipaa_breach", "no_soc2", "active_litigation"],
    "risk_appetite": "conservative",
}

# --- canned extractor output for two vendors (category -> 0-10) ---
VENDOR_FAST = {
    "vendor": "SpeedyEHR",
    "scores": {"patient_safety": 6, "security_breach": 7, "regulatory_compliance": 6,
               "deployment_speed": 9, "cost": 9, "integration_interop": 7,
               "vendor_stability": 6, "support_service": 8, "data_transparency": 6},
    "deal_breaker_flags": set(),
}
VENDOR_SAFE = {
    "vendor": "RigorousClinical",
    "scores": {"patient_safety": 9, "security_breach": 8, "regulatory_compliance": 9,
               "deployment_speed": 4, "cost": 4, "integration_interop": 8,
               "vendor_stability": 8, "support_service": 6, "data_transparency": 8},
    "deal_breaker_flags": set(),
}


def _profile(name, answers, mode="ask"):
    return HospitalProfile.from_fields(name, answers_to_profile_fields(answers),
                                       mode=mode, updated="2026-06-18")


def main() -> None:
    for hosp_name, answers in [("Mercy Rural Health", RURAL_ANSWERS),
                               ("University Medical Center", ACADEMIC_ANSWERS)]:
        prof = _profile(hosp_name, answers)
        print("=" * 70)
        print(prof.to_summary())
        print("\nRanked vendors for this hospital:")
        ranked = scorer.rank(prof, [
            {"vendor": VENDOR_FAST["vendor"], "scores": VENDOR_FAST["scores"],
             "deal_breaker_flags": VENDOR_FAST["deal_breaker_flags"]},
            {"vendor": VENDOR_SAFE["vendor"], "scores": VENDOR_SAFE["scores"],
             "deal_breaker_flags": VENDOR_SAFE["deal_breaker_flags"]},
        ])
        for r in ranked:
            print("\n" + r.to_text())

    # --- gap loop demo (auto mode) ---
    print("\n" + "=" * 70)
    print("GAP LOOP - auto mode (AI best-guess + disclosure)")
    auto_prof = _profile("Mercy Rural Health", RURAL_ANSWERS, mode="auto")
    uncovered = [{"factor": "EU data residency", "evidence": "Vendor stores PHI in Frankfurt",
                  "materiality": "high"}]
    disclosures = gap.resolve(auto_prof, uncovered)
    for d in disclosures:
        print("  " + d["message"])
    print(f"  -> profile now v{auto_prof.version}, {len(auto_prof.categories)} categories")

    # --- gap loop demo (ask mode, scripted answer) ---
    print("\nGAP LOOP - ask mode (scripted hospital answer = 'high')")
    ask_prof = _profile("Mercy Rural Health", RURAL_ANSWERS, mode="ask")
    disclosures = gap.resolve(ask_prof, uncovered, ask_fn=lambda q: "high")
    for d in disclosures:
        print("  " + d["message"])
    print(f"  -> profile now v{ask_prof.version}, {len(ask_prof.categories)} categories")


if __name__ == "__main__":
    main()
