import argparse
import sys
import yaml
import os
from .profile import HospitalProfile

def load_questions():
    path = os.path.join(os.path.dirname(__file__), "questions.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def prompt_ranking(categories):
    print("\n--- Phase 1: Rank Categories ---")
    print("Rank the following 9 categories from 1 (most important) to 9 (least important).")
    available = {c['id']: c['label'] for c in categories}
    ranks = {}
    
    # We will just do a simple sequential prompt for now
    for i in range(1, 10):
        print(f"\nAvailable categories to rank #{i}:")
        cats_list = list(available.items())
        for idx, (cid, label) in enumerate(cats_list):
            print(f"  {idx + 1}. {label} ({cid})")
        
        while True:
            try:
                choice = input(f"Select category for Rank #{i} (1-{len(cats_list)}): ").strip()
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(cats_list):
                    selected_id = cats_list[choice_idx][0]
                    ranks[selected_id] = i
                    del available[selected_id]
                    break
                else:
                    print("Invalid choice. Try again.")
            except ValueError:
                print("Please enter a number.")
    return ranks

def prompt_sliders(sliders):
    print("\n--- Phase 2: Fine-Tuning Top Concerns ---")
    results = {}
    for slider in sliders:
        print(f"\n{slider['label']} ({slider['category']})")
        while True:
            try:
                val = input("Rate from 1 to 5: ").strip()
                ival = int(val)
                if 1 <= ival <= 5:
                    results[slider['category']] = ival
                    break
                else:
                    print("Must be between 1 and 5.")
            except ValueError:
                print("Please enter a number.")
    return results

def prompt_deal_breakers(deal_breakers):
    print("\n--- Phase 3: Deal-Breakers ---")
    selected = []
    for db in deal_breakers:
        while True:
            ans = input(f"{db['question']} (y/n): ").strip().lower()
            if ans in ['y', 'yes']:
                selected.append({
                    "factor": db["factor"],
                    "category": db["category"],
                    "rule": db["rule"]
                })
                break
            elif ans in ['n', 'no']:
                break
            else:
                print("Please answer 'y' or 'n'.")
    return selected

def prompt_risk_appetite(appetite_config):
    print("\n--- Phase 4: Risk Appetite ---")
    print(appetite_config['question'])
    opts = appetite_config['options']
    for idx, opt in enumerate(opts):
        print(f"  {idx + 1}. {opt['label']}")
    
    while True:
        try:
            val = input(f"Select (1-{len(opts)}): ").strip()
            ival = int(val) - 1
            if 0 <= ival < len(opts):
                return opts[ival]
            else:
                print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")

def compute_weights(ranks, sliders):
    # Base weights for ranks 1-9: 18%, 16%, 14%, 12%, 10%, 8%, 6%, 4%, 2%
    base_schedule = {1: 0.18, 2: 0.16, 3: 0.14, 4: 0.12, 5: 0.10, 6: 0.08, 7: 0.06, 8: 0.04, 9: 0.02}
    
    weights = {}
    for cat_id, rank in ranks.items():
        weight = base_schedule[rank]
        
        # Apply slider multiplier if exists
        if cat_id in sliders:
            slider_val = sliders[cat_id]
            # 1 -> 0.5x, 3 -> 1.0x, 5 -> 1.5x
            multiplier = 0.5 + ((slider_val - 1) * 0.25)
            weight *= multiplier
            
        weights[cat_id] = {"weight": weight, "rank": rank}
        
    # Renormalize
    total = sum(w["weight"] for w in weights.values())
    for cat_id in weights:
        weights[cat_id]["weight"] = round(weights[cat_id]["weight"] / total, 4)
        
    return weights

def run_onboarding(slug):
    q_data = load_questions()
    
    print(f"Starting Questionnaire for: {slug}")
    
    ranks = prompt_ranking(q_data['categories'])
    sliders = prompt_sliders(q_data['sliders'])
    dbs = prompt_deal_breakers(q_data['deal_breakers'])
    appetite = prompt_risk_appetite(q_data['risk_appetite'])
    
    weights = compute_weights(ranks, sliders)
    
    profile = HospitalProfile(slug)
    profile.categories = weights
    profile.deal_breakers = dbs
    profile.thresholds = appetite['thresholds']
    profile.rationale = f"Profile generated via CLI onboarding. Risk appetite: {appetite['id']}."
    
    profile.save()
    print(f"\n[Success] Profile saved to profiles/{slug}.yaml")
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["onboarding", "edit"])
    parser.add_argument("slug", help="Hospital slug (e.g., mercy-rural-health)")
    args = parser.parse_args()
    
    if args.command == "onboarding":
        run_onboarding(args.slug)
    elif args.command == "edit":
        print("Edit mode not fully implemented yet in CLI. Try rerunning onboarding for now.")

if __name__ == "__main__":
    main()
