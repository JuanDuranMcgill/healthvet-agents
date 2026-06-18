from typing import List, Dict, Any
from .profile import HospitalProfile

def resolve_gaps(uncovered: List[Dict[str, Any]], profile: HospitalProfile) -> None:
    """
    Resolves uncovered factors. Mutates the profile in-place and saves it if changed.
    """
    if not uncovered:
        return
        
    mode = profile.settings.get("gap_resolution_mode", "ask")
    changed = False
    
    for factor in uncovered:
        materiality = factor.get("materiality", "low").lower()
        if materiality == "low":
            continue
            
        category_key = factor.get("factor", "").replace(" ", "_").lower()
        # Ensure unique key
        base_key = category_key
        idx = 1
        while category_key in profile.categories:
            category_key = f"{base_key}_{idx}"
            idx += 1
            
        if mode == "ask":
            print(f"\n[GAP] Uncovered Factor: {factor.get('factor')} (Materiality: {materiality})")
            print(f"Evidence: {factor.get('evidence')}")
            while True:
                try:
                    val = input("Assign a relative weight (1-10) for this new factor (0 to ignore): ").strip()
                    ival = int(val)
                    if ival > 0:
                        # Base weight approximation
                        weight = ival * 0.02
                        profile.add_category(category_key, weight, "gap_ask")
                        changed = True
                    break
                except ValueError:
                    print("Please enter a number.")
        elif mode == "auto":
            if materiality == "high":
                weight = 0.10
            elif materiality == "medium":
                weight = 0.05
            else:
                weight = 0.0
                
            if weight > 0:
                profile.add_category(category_key, weight, "gap_auto")
                changed = True

    if changed:
        profile.save()
