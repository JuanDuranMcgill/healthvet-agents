# `research/` — Evidence engine + Band coordination contract

This package is two things:

1. A **retrieval engine** that gathers attributed, tier-ranked evidence about a
   vendor from multiple providers concurrently.
2. A **versioned Band message contract** that turns retrieval into a first-class
   collaborator in the agent room — with correlated requests, responses, and a
   traceable audit trail.

Everything here is plain async Python with **no LangGraph dependency**, so the
engine can be driven equally by a LangGraph agent (Scout, Compliance) or by the
standalone `SimpleAdapter` worker (`agents/research.py`).

## Public interface

```python
from research.engine import ResearchEngine
from research.providers.factory import default_providers, web_providers, regulatory_providers

engine = ResearchEngine(providers=default_providers())
bundle = await engine.gather(
    vendor="Veradigm",
    goals=["customer references", "regulatory standing"],
    gap_directives=None,          # when present, retrieval is scoped to these only
    hospital_context=None,
)
# bundle.evidence -> tuple[Evidence]  (ranked: tier first, then relevance)
# bundle.queries_run -> tuple[str]
# bundle.failures -> tuple[Failure]
```

### The audit-trail artifact

`EvidenceBundle` deliberately keeps three states **distinct** — this is the
product, not an implementation detail:

| State | Meaning |
|---|---|
| **not_found** | We searched and found nothing |
| **not_searched** | We never issued a query for it |
| **failed** | A provider errored (recorded in `failures`) |

`bundle.state_for(query)` returns one of these. In a regulated workflow a visible
gap is correct; a fabricated answer is dangerous. Nothing is ever defaulted to
mask a failure.

## Source tiers

Ranking and dedup use **tier first, then relevance**, so a vendor's own marketing
can never outrank a regulatory record.

| Tier | Examples (Phase 1) |
|---|---|
| `REGULATORY` (highest) | openFDA 510(k), HHS/OCR breach records |
| `VERIFIED_CUSTOMER` | (reserved — heuristic classification is a future extension) |
| `VENDOR_SELF` | (reserved) |
| `PRESS` (lowest) | Tavily / Exa / DuckDuckGo general web |

## Band message contract (`contract.py`)

Band messages carry only text, so the schema is embedded in the message: a
one-line human summary (keeps the room legible during a demo) + a fenced JSON
payload (lets agents parse a contract instead of scraping prose).

- `research_request`: `{type, version, request_id, requested_by, vendor, goals, gap_directives, priority, summary}`
- `research_response`: `{type, version, request_id, responded_by, vendor, status, evidence[], failures[], summary}`
- `Status`: `pending | partial | complete | failed | needs_reinvestigation`
- `serialize(msg) -> str` / `parse(content) -> ResearchRequest | ResearchResponse | None`

Every message carries a `request_id` for correlation, so the room is a traceable
audit trail.

## Prompt-injection hygiene

Retrieved web/vendor text is data, never instructions. `sanitize()` wraps any
untrusted snippet in labelled markers and strips fence-breakout attempts before
it reaches an LLM (used by `evidence_digest()` and at every boundary). A
vendor-controlled page cannot influence its own assessment.

## The coordination flow (demo narration)

1. **Broad sweep.** A user triggers `@scout`. Scout calls the engine (web lane),
   then posts a `research_response` (summary + evidence) to Forensics.
2. **Parallel evaluation.** Forensics → Compliance → Gap → Risk. Compliance runs
   the engine itself on the **regulatory lane** (openFDA + OCR) — real division
   of labor, not one agent doing everything.
3. **Gap-directed re-investigation.** When **Gap** flags CRITICAL gaps (verdict
   INSUFFICIENT) or **Risk** vetoes, it posts a `research_request` with specific
   `gap_directives` to the **standalone Research worker** (a non-LangGraph agent
   — collaboration across frameworks). The worker runs *scoped* retrieval and
   replies with a correlated `research_response` (`complete`, or
   `needs_reinvestigation` if still unresolved). Each requester escalates at most
   once per session.
4. **Synthesis.** Risk makes its final, non-vetoable verdict and hands to
   Synthesis for the auditable report.

The veto is no longer a blind full re-run — it is a structured negotiation
through Band with specific directives and correlated responses.

## Tests

```bash
python -m unittest discover -s research/tests
```

Providers and Band are mocked. A live smoke test (`test_live_smoke.py`) is
skipped unless `RUN_LIVE_TESTS=1`.

## Phase-1 scope / assumptions to confirm

- **openFDA** device 510(k): `https://api.fda.gov/device/510k.json?search=applicant:"<vendor>"`, keyless (optional `OPENFDA_API_KEY` raises limits).
- **OCR breach**: no stable official JSON API, so it is a Tavily search constrained to authoritative breach-record domains, ranked `REGULATORY`.
- **ONC CHPL** is deferred to a later phase (likely needs a free API key).
- DuckDuckGo is best-effort (deprecated / rate-limited); its failures land in `failures`.
