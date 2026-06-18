# Questionnaire & Vendor Fit Scoring

Turns a hospital's qualitative values into a **weighted scoring model** so the
agents can score and rank vendors numerically instead of eyeballing pros/cons.

Design: [`docs/superpowers/specs/2026-06-17-questionnaire-vendor-fit-scoring-design.md`](../docs/superpowers/specs/2026-06-17-questionnaire-vendor-fit-scoring-design.md)

## Files

| file | purpose |
|---|---|
| `categories.py` | the 9 fixed scoring dimensions (shared vocabulary) |
| `questions.yaml` | the ~16 bounded form items + answer→weight rules (editable) |
| `mapping.py` | deterministic answers → category weights / thresholds / deal-breakers |
| `profile.py` | `HospitalProfile`: load / save / edit / `add_category` (renormalize + version bump) |
| `cli.py` | runs the ~10-min onboarding; `edit` to modify later |
| `extractor.py` | one LLM call: agent free-text → per-category 0-10 scores + uncovered factors |
| `scorer.py` | pure: scores × weights → fit (0-100) + verdict + breakdown + ranking |
| `gap.py` | uncovered-factor loop — `ask` (improve profile) / `auto` (best-guess + disclose) |
| `integration.py` | glue the Risk/Synthesis agents call |
| `demo.py` | offline end-to-end demo (no keys) |

## Try it offline (no API keys)

```bash
python -m questionnaire.demo          # two hospitals, same vendors, opposite rankings
python -m questionnaire.cli new       # run the questionnaire interactively
python -m questionnaire.cli show <slug>
python -m pytest questionnaire/tests -q
```

## Live pipeline

Set the active profile and the Risk agent will append a fit scorecard; Synthesis
surfaces it (and any assumptions) in the final report:

```bash
export HEALTHVET_PROFILE=<your-hospital-slug>   # a saved profile in questionnaire/profiles/
```

If `HEALTHVET_PROFILE` is unset/missing, scoring is skipped and the agents behave
exactly as before.

## How scoring works

`fit = Σ(category_score/10 × weight) × 100`. Deal-breakers hard-cap the fit and
force a `REJECT`. Verdict thresholds come from the hospital's risk appetite.

## Gap-resolution modes (per profile, `settings.gap_resolution_mode`)

- **`ask`** (default): a material uncovered factor → one targeted question →
  permanently adds a weighted category to the profile (version bump, logged).
- **`auto`**: AI assigns a best-guess weight and **every assumption is disclosed
  prominently in the final report** ("ASSUMED … please confirm").
