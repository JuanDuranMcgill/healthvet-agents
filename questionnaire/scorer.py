import re
from typing import Dict, Any, List, Tuple
from .profile import HospitalProfile

def score_vendor(profile: HospitalProfile, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    scores = extracted_data.get("scores", {})
    
    total_fit = 0.0
    breakdown = []
    
    for cat_id, cat_info in profile.categories.items():
        weight = cat_info.get("weight", 0)
        ext = scores.get(cat_id, {})
        # Missing categories default to 5 (neutral)
        cat_score = ext.get("score", 5)
        
        contribution = (cat_score / 10.0) * weight
        total_fit += contribution
        
        breakdown.append({
            "category": cat_id,
            "score": cat_score,
            "weight": weight,
            "contribution": round(contribution * 100, 2),
            "evidence": ext.get("evidence", "No evidence found")
        })
        
    fit_percentage = round(total_fit * 100)
    
    # Evaluate Deal Breakers
    triggered_dbs = []
    for db in profile.deal_breakers:
        rule = db.get("rule", "").lower()
        cat = db.get("category", "")
        evidence = scores.get(cat, {}).get("evidence", "").lower()
        
        # Simple keyword matching for demo purposes
        # A more robust system would use an LLM or complex regex
        if evidence and (rule in evidence or any(word in evidence for word in rule.split() if len(word) > 4)):
            triggered_dbs.append(db)
            
    # Apply Deal Breakers
    verdict = "APPROVE"
    if triggered_dbs:
        verdict = "REJECT"
        fit_percentage = min(fit_percentage, profile.thresholds.get("escalate", 50) - 1)
    else:
        if fit_percentage >= profile.thresholds.get("approve", 75):
            verdict = "APPROVE"
        elif fit_percentage >= profile.thresholds.get("escalate", 50):
            verdict = "ESCALATE"
        else:
            verdict = "REJECT"
            
    return {
        "fit": fit_percentage,
        "verdict": verdict,
        "breakdown": breakdown,
        "triggered_deal_breakers": triggered_dbs,
        "assumptions_applied": profile.assumptions
    }

def rank_vendors(profile: HospitalProfile, vendors_data: List[Tuple[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    results = []
    for vendor_name, extracted in vendors_data:
        res = score_vendor(profile, extracted)
        res["vendor"] = vendor_name
        results.append(res)
        
    # Sort by fit (descending), but REJECT always goes to bottom
    def sort_key(v):
        is_reject = 1 if v["verdict"] == "REJECT" else 0
        return (is_reject, -v["fit"])
        
    results.sort(key=sort_key)
    return results
