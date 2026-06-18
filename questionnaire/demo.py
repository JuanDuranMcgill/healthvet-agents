from .profile import HospitalProfile
from .scorer import score_vendor
from .gap import resolve_gaps

def run_demo():
    slug = "test-hospital"
    profile = HospitalProfile(slug)
    # Give it some baseline data if it doesn't exist
    profile.categories = {
        "patient_safety": {"weight": 0.3, "rank": 1},
        "cost": {"weight": 0.2, "rank": 2},
        "security_breach": {"weight": 0.5, "rank": 3}
    }
    profile.deal_breakers = [{
        "factor": "open_hipaa_breach",
        "category": "security_breach",
        "rule": "unresolved OCR breach"
    }]
    profile.settings["gap_resolution_mode"] = "auto"
    
    mock_extracted = {
        "scores": {
            "patient_safety": {"score": 8, "evidence": "Great clinical trials."},
            "cost": {"score": 7, "evidence": "Moderate pricing."},
            "security_breach": {"score": 2, "evidence": "Warning: unresolved OCR breach detected."}
        },
        "uncovered": [
            {"factor": "data residency", "evidence": "Must be in EU", "materiality": "high"}
        ]
    }
    
    # 1. Resolve gaps
    print("Initial categories:", len(profile.categories))
    resolve_gaps(mock_extracted.get("uncovered", []), profile)
    print("Categories after gap resolution:", len(profile.categories))
    
    # 2. Score
    res = score_vendor(profile, mock_extracted)
    print("\n--- Final Scorecard ---")
    print(f"Fit: {res['fit']}")
    print(f"Verdict: {res['verdict']}")
    print(f"Deal breakers: {[db['factor'] for db in res['triggered_deal_breakers']]}")
    print("\nBreakdown:")
    for b in res['breakdown']:
        print(f"  {b['category']}: score={b['score']} weight={b['weight']} cont={b['contribution']}%")
        
if __name__ == "__main__":
    run_demo()
