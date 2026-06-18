# Questionnaire & Vendor Fit Scoring — Design

**Date:** 2026-06-17
**Status:** Approved (brainstorm)
**Component:** `questionnaire/` (new, self-contained module within healthvet-agents)

## Problem

The current pipeline (Scout → Forensics → Compliance → Gap → Risk → Synthesis)
produces rich *qualitative* findings, but the final verdict is the LLM's holistic
judgment. An LLM cannot reliably decide "5 pros / 1 con" vs "2 pros / 0 con"
because pro/con weight is **hospital-specific and qualitative**. A rural hospital
values uptime and cost; an academic center values clinical-outcome evidence and
interoperability.

We need a short, bounded onboarding that **quantifies a hospital's values into a
weighted scoring model**, so the agents can score and rank vendors numerically
and defensibly — and a mechanism to extend that model when a vendor surfaces a
factor the onboarding never asked about.

## Goals

- A bounded, structured, concrete ~10-minute questionnaire (not an open-ended chat).
- Output: an editable, versioned **hospital profile** = category weights +
  deal-breakers + verdict thresholds.
- A scorer that turns agent findings into a **weighted fit score (0–100) + verdict**,
  supporting multi-vendor ranking.
- A "smart & critical" gap loop: when a material factor isn't covered by the
  profile, either ask the hospital one targeted question and permanently improve
  the profile, or (optional autonomous mode) best-guess the weight and transparently
  disclose every assumption in the final report.
- Self-contained under `questionnaire/`, independently testable, then imported by
  the Risk and Synthesis agents.

## Non-Goals (YAGNI)

- No web UI this round — terminal CLI only.
- LLM does **not** decide weights. Weight mapping from answers is deterministic.
  The LLM is used only to (a) extract per-category scores from agent text, and
  (b) write a plain-English rationale into the profile.
- No automated email outreach / dashboards (separate roadmap items).

## Evaluation Dimensions (shared vocabulary)

Nine fixed scoring categories, aligned with what the agents already produce
(Gap's 9 categories + hospital-value dimensions). Every vendor is scored 0–10 on
each; the profile only assigns **weights** and **deal-breakers** over them.

| key | meaning |
|---|---|
| `patient_safety` | clinical outcomes, safety evidence |
| `security_breach` | breach history, OCR notifications, security posture |
| `regulatory_compliance` | FDA clearance, ONC cert, HIPAA, SOC 2 |
| `deployment_speed` | time-to-value, implementation effort |
| `cost` | pricing, total cost of ownership |
| `integration_interop` | EHR fit, interoperability |
| `vendor_stability` | litigation, financial/business stability |
| `support_service` | support quality, SLAs, service |
| `data_transparency` | data residency, subprocessor transparency |

## Architecture

```
questionnaire/
  questions.yaml      # the ~16 fixed form items + answer→weight mapping rules
  profile.py          # HospitalProfile: load / save / edit / version bump
  cli.py              # runs the form (~10 min); `edit` subcommand to modify later
  extractor.py        # LLM: agent free-text report  -> per-category 0-10 scores
                      #                              + list of uncovered factors
  scorer.py           # scores x weights -> fit (0-100), breakdown, verdict, ranking
  gap.py              # uncovered-factor loop; modes: ask | auto
  profiles/           # saved hospital profiles, one yaml per hospital (gitignored)
  demo.py             # feeds canned findings -> prints scorecard (offline test)
  tests/              # unit tests for scorer, profile, mapping
```

Data flow:

```
cli.py  --(answers)-->  profile.yaml
                              |
agent reports --extractor--> {category: score, uncovered: [...]}
                              |                         |
                              v                         v
                         scorer.score(profile, scores)  gap.resolve(uncovered, profile, mode)
                              |                              |  (ask: question->answer->profile v++)
                              v                              |  (auto: best-guess + disclosure)
                    fit 0-100 + verdict + breakdown <--------+ (re-score after profile update)
```

## Questionnaire (`questions.yaml` + `cli.py`)

~16 bounded items, deterministic mapping to weights:

1. **Rank the 9 categories** (forced ordering). Base weight from rank via a fixed
   decreasing schedule (e.g. rank-based points normalized to sum 1.0).
2. **5 sliders (1–5)** fine-tuning the importance multiplier of the top concerns.
3. **Deal-breaker checklist** — concrete rules, e.g.:
   - "Any unresolved HIPAA/OCR breach" → `security_breach`
   - "No FDA clearance when device-class applies" → `regulatory_compliance`
   - "No SOC 2 Type II" → `regulatory_compliance`
4. **Risk appetite** (1 question, 3 choices) → maps to verdict thresholds
   (conservative `approve:80/escalate:60`, balanced `75/50`, lenient `65/40`).

Mapping is pure/deterministic and unit-tested. The LLM is called once at the end
only to write a human-readable `rationale` string into the profile.

`cli.py edit <hospital-slug>` reopens any subset of questions, recomputes weights,
bumps `version`, preserves the `assumptions` log.

## Profile schema (`profile.py`)

```yaml
hospital: "Mercy Rural Health"
slug: mercy-rural-health
version: 3                 # bumps on every edit or gap-update
updated: "2026-06-17"
settings:
  gap_resolution_mode: ask     # ask | auto
categories:
  patient_safety:   { weight: 0.28, rank: 1 }
  security_breach:  { weight: 0.22, rank: 2 }
  # ... all 9, weights normalized to sum 1.0
deal_breakers:
  - factor: open_hipaa_breach
    category: security_breach
    rule: "unresolved OCR breach present"
thresholds: { approve: 75, escalate: 50 }   # < escalate => reject
rationale: "Small rural hospital; uptime and cost dominate; ..."
assumptions: []   # appended log of every ask/auto gap-resolution
```

`HospitalProfile` provides: `load(slug)`, `save()`, `add_category(key, weight, source)`
(renormalizes, bumps version, appends to `assumptions`), `to_summary()`.

## Scoring (`extractor.py` + `scorer.py`)

**`extractor.py`** — one LLM call per vendor over the concatenated agent reports.
Returns structured JSON:
```json
{
  "scores": { "patient_safety": {"score": 9, "evidence": "...", "confidence": 0.8}, ... },
  "uncovered": [ {"factor": "data residency (EU)", "evidence": "...", "materiality": "..."} ]
}
```
Validated against the 9 known keys; missing categories default to a neutral score
with `confidence: 0` and are flagged.

**`scorer.py`** — pure, no LLM:
- `fit = round(100 * Σ(score/10 × weight))`.
- Deal-breakers: if a rule matches the extracted findings, hard-cap fit (e.g. to 0
  or below the reject line) and force verdict.
- Verdict from `fit` vs `thresholds` (unless a deal-breaker forces it).
- Returns `{fit, verdict, breakdown:[{category, score, weight, contribution}],
  triggered_deal_breakers, assumptions_applied}`.
- `rank(profile, [vendor_findings...])` → vendors sorted by fit, deal-breakers last.

## Gap-resolution loop (`gap.py`)

Input: `uncovered` factors from the extractor + the profile + mode.

- **`ask`** (default): for each material uncovered factor, emit one targeted
  question ("How much does *data residency* matter? deal-breaker / high / med /
  low / ignore"). On answer, `profile.add_category(...)` with the mapped weight
  (renormalize, `version++`, log to `assumptions`), then re-score. Profile
  permanently improves.
- **`auto`**: assign a best-guess weight from the factor's stated materiality,
  score with it, mark `assumed: true` in `assumptions`. **Every assumption is
  surfaced prominently in the final report** ("⚠ Assumed data_residency = HIGH —
  please confirm"). Transparency is mandatory in this mode.

Materiality threshold filters trivial factors so the loop fires rarely (the
"broad but characteristic onboarding" goal).

## Wiring into the pipeline

- **Risk** (`agents/risk.py`): loads the active profile, calls `extractor` then
  `scorer.score(...)`; the verdict it posts is now driven by fit + deal-breakers
  rather than pure LLM judgment. Runs `gap.resolve(...)` per `gap_resolution_mode`.
- **Synthesis** (`agents/synthesis.py`): final report includes the scorecard
  (fit, per-category breakdown) and the disclosed `assumptions`.
- Profile selection: an env/config value names the active profile slug.

`questionnaire/` has no hard dependency on Band — `demo.py` exercises the full
extract→score→gap flow offline with canned findings for testing.

## Testing

- `scorer.py`: deterministic unit tests (weights, deal-breaker hard-cap, verdict
  thresholds, ranking order) — no LLM.
- `profile.py`: load/save round-trip, `add_category` renormalization + version bump.
- `questions.yaml` mapping: ranking → normalized weights, risk-appetite → thresholds.
- `extractor.py`: schema-validation test with a canned report (LLM mocked).
- `demo.py`: end-to-end offline smoke (canned Veradigm findings → ranked output).

## Open considerations

- Exact rank→weight schedule and slider multipliers: pin concrete numbers in the
  implementation plan.
- Deal-breaker rule expressiveness: start with simple keyword/flag matching on
  extracted findings; richer rules later if needed.
