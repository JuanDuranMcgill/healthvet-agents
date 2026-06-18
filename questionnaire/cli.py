"""
Questionnaire CLI — runs the ~10-minute onboarding in the terminal and writes a
hospital profile. Also supports re-editing an existing profile.

Usage:
  python -m questionnaire.cli new                 # run the full questionnaire
  python -m questionnaire.cli edit <slug>         # re-run / adjust an existing profile
  python -m questionnaire.cli list                # list saved profiles
  python -m questionnaire.cli show <slug>         # print a profile summary

No API keys required — weight mapping is deterministic. (An optional LLM rationale
could be added later; omitted here to keep onboarding offline.)
"""
from __future__ import annotations

import datetime
import sys

from .categories import CATEGORIES, CATEGORY_KEYS, category_label
from .mapping import answers_to_profile_fields, load_form
from .profile import HospitalProfile, list_profiles


def _today() -> str:
    return datetime.date.today().isoformat()


def _prompt(text: str) -> str:
    return input(text).strip()


def _ask_ranking() -> list[str]:
    print("\n--- Rank the nine factors (most → least important) ---")
    for i, c in enumerate(CATEGORIES, 1):
        print(f"  [{i}] {c['label']}")
    print("Enter the numbers 1-9 in your priority order, e.g. 2 1 3 5 4 6 9 8 7")
    while True:
        raw = _prompt("Order: ").replace(",", " ").split()
        try:
            idx = [int(x) - 1 for x in raw]
        except ValueError:
            print("  numbers only, please."); continue
        if sorted(idx) != list(range(len(CATEGORY_KEYS))):
            print(f"  must use each of 1-{len(CATEGORY_KEYS)} exactly once."); continue
        return [CATEGORY_KEYS[i] for i in idx]


def _ask_slider(form, qid: str) -> int:
    q = next(x for x in form["questions"] if x["id"] == qid)
    while True:
        raw = _prompt(f"{q['prompt']}\n  > ")
        if raw in {"1", "2", "3", "4", "5"}:
            return int(raw)
        print("  enter 1-5.")


def _ask_deal_breakers(form) -> list[str]:
    q = next(x for x in form["questions"] if x["id"] == "deal_breakers")
    print(f"\n{q['prompt']}")
    for i, opt in enumerate(q["options"], 1):
        print(f"  [{i}] {opt['label']}")
    raw = _prompt("Numbers (space-separated, blank for none): ").replace(",", " ").split()
    chosen = []
    for x in raw:
        if x.isdigit() and 1 <= int(x) <= len(q["options"]):
            chosen.append(q["options"][int(x) - 1]["id"])
    return chosen


def _ask_risk_appetite(form) -> str:
    q = next(x for x in form["questions"] if x["id"] == "risk_appetite")
    print(f"\n{q['prompt']}")
    for i, opt in enumerate(q["options"], 1):
        print(f"  [{i}] {opt['label']}")
    while True:
        raw = _prompt("Choice: ")
        if raw.isdigit() and 1 <= int(raw) <= len(q["options"]):
            return q["options"][int(raw) - 1]["id"]
        print("  pick a listed number.")


def _ask_mode() -> str:
    print("\nGap-resolution mode when a vendor surfaces something you weren't asked about:")
    print("  [1] ask  — pause and ask you one question, then improve the profile (recommended)")
    print("  [2] auto — AI best-guesses and discloses every assumption in the report")
    return "auto" if _prompt("Choice [1/2]: ") == "2" else "ask"


def run_questionnaire(prefill: dict | None = None) -> HospitalProfile:
    form = load_form()
    prefill = prefill or {}
    hospital = prefill.get("hospital") or _prompt("Hospital name: ") or "Unnamed Hospital"

    answers = {"rank_categories": _ask_ranking()}
    for qid in ("slider_patient_safety", "slider_security_breach",
                "slider_deployment_speed", "slider_cost", "slider_integration_interop"):
        cat = qid.replace("slider_", "")
        answers[qid] = _ask_slider(form, qid)
    answers["deal_breakers"] = _ask_deal_breakers(form)
    answers["risk_appetite"] = _ask_risk_appetite(form)
    mode = _ask_mode()

    fields = answers_to_profile_fields(answers, form)
    profile = HospitalProfile.from_fields(hospital, fields, mode=mode, updated=_today())
    path = profile.save(updated=_today())
    print("\n" + profile.to_summary())
    print(f"\nSaved → {path}")
    return profile


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "new"

    if cmd in ("new", "edit"):
        prefill = {}
        if cmd == "edit":
            if len(argv) < 2:
                print("usage: cli.py edit <slug>"); return 2
            existing = HospitalProfile.load(argv[1])
            prefill = {"hospital": existing.hospital}
            print(f"Re-running questionnaire for {existing.hospital} (v{existing.version}).")
        run_questionnaire(prefill)
        return 0

    if cmd == "list":
        for s in list_profiles():
            print(s)
        return 0

    if cmd == "show":
        if len(argv) < 2:
            print("usage: cli.py show <slug>"); return 2
        print(HospitalProfile.load(argv[1]).to_summary())
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
