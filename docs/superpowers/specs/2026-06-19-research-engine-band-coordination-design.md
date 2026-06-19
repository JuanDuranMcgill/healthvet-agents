# Research/Retrieval Engine + Band Coordination Layer — Design

**Date:** 2026-06-19
**Branch:** `improve-research-engine`
**Status:** Awaiting approval (no code until "go")

> Band of Agents Hackathon, Track 3 (Regulated & High-Stakes Workflows). The deliverable
> is an evidence-gathering capability **plus** the Band coordination contract that makes it a
> first-class collaborator. The coordination is the core; the retrieval engine is the substrate.

## Confirmed decisions

1. **Research agent = standalone non-LangGraph Band worker** (`agents/research.py`), a plain async
   poll loop. Confirmed feasible: `band.client.rest.AsyncRestClient` exposes
   `agent_api_messages.list_agent_messages(chat_id)` and `create_agent_chat_message(...)`
   (see `scratch/test_band2.py`). Requires provisioning a **7th Band External Agent** (new
   `agent_id`/`api_key`, added to the room, new handle, config + `.env` + `@mention` targets).
2. **Phase-1 providers:** Tavily, Exa, DuckDuckGo (web tiers) + **openFDA** (the one confirmed
   keyless regulatory API) + **OCR breach** as the existing Tavily domain-filtered lookup promoted
   to a tier. **ONC CHPL deferred** to a later phase (likely needs a free API key + live shape
   confirmation).
3. **Phased delivery, core first.**

## Load-bearing mechanic: the contract lives inside message `content`

Band messages carry only a text `content` field (+ mentions) — there is no structured payload slot
(`scratch/test_band2.py:20-22`; `web_server.py:127-135` reads `m.get('content')` as a string).
Therefore the versioned schema is **embedded in the content string**:

```
<one-line human summary for room legibility>

```json
{ "type": "...", "version": 1, "request_id": "...", ... }
```
```

- `serialize(msg)` → that text blob (summary line + fenced JSON).
- `parse(content)` → dataclass, or `None` if no valid block is present.

This keeps the Band room human-legible during the live demo **and** machine-parseable by downstream
agents, which already receive prior messages as text.

## Architecture

```
                 ┌─────────────────── Band room (shared chat) ───────────────────┐
 user ─@scout──▶ │                                                                │
                 │  Scout ──research_response──▶ Forensics ─▶ Compliance ─▶ Gap ─▶ Risk ─▶ Synthesis
                 │    ▲                              │(calls engine for reg tiers)      │
                 │    │                              │                                  │
                 │  research_response          research_request (gap_directives) ◀──────┘
                 │    │                              │
                 │  Research worker ◀────────────────┘   (agents/research.py, non-LangGraph)
                 └────────────────────────────────────────────────────────────────────┘
```

- Scout runs the **broad sweep** via the engine and posts the first `research_response`.
- Compliance calls the engine itself for **regulatory tiers** (role specialization).
- Risk/Gap post a **`research_request` with `gap_directives`** on a make-or-break hole; the Research
  worker (or Scout fallback) runs **scoped** retrieval and posts a correlated `research_response`
  with `status = complete` or `needs_reinvestigation`. This turns the existing veto into a
  structured negotiation rather than a blind full re-run.

## Components

### `research/contract.py`
- `VERSION` constant; `MessageType` (`research_request`, `research_response`),
  `Status` (`pending`, `partial`, `complete`, `failed`, `needs_reinvestigation`) enums.
- `ResearchRequest`: `type, version, request_id, requested_by, vendor, goals[], gap_directives[], priority`.
- `ResearchResponse`: `type, version, request_id, responded_by, status, evidence[], failures[], summary`.
- `serialize() / parse()` helpers (single source of truth for all agents).

### `research/models.py`
- `SourceTier` enum, trust-ordered: `REGULATORY` > `VERIFIED_CUSTOMER` > `VENDOR_SELF` > `PRESS`.
- `Evidence`: `id, snippet, source_url, source_name, provider, source_tier, retrieved_at, query, relevance(0..1), raw`.
- `EvidenceBundle`: `evidence[], queries_run[], failures[]`. Must distinguish three states:
  **not-found** (searched, nothing), **not-searched** (no query for it), **failed** (provider errored).
- Frozen dataclasses; matches `questionnaire` dataclass style.

### `research/providers/`
- `base.py`: `SearchProvider` ABC, async `search(query, **opts) -> list[RawResult]`. Sync clients
  (tavily-python, exa_py, duckduckgo-search) wrapped via `asyncio.to_thread`; REST APIs via `httpx`.
- Phase 1: `tavily.py`, `exa.py`, `ddg.py`, `openfda.py`, `ocr.py` (Tavily domain-filtered).
  Reuse existing keys/clients from `agents/scout.py`; invent no new auth. DuckDuckGo is best-effort
  (deprecated/rate-limited) → failures land in `failures`, never abort.
- Deferred: `chpl.py` (later phase).

### `research/engine.py`
- `ResearchEngine.gather(vendor, goals, gap_directives=None, hospital_context=None) -> EvidenceBundle`.
- Plan sub-queries → concurrent fan-out (`asyncio.gather(..., return_exceptions=True)`, per-provider
  timeout + bounded retry) → normalize → dedup (by normalized URL) → rank (**tier first, then
  relevance**, so vendor marketing never outranks a regulatory record).
- When `gap_directives` present → scoped retrieval for those directives only.

### `research/planner.py`
- `make_llm()`-based expansion of vendor + goals/directives into sub-queries.
- On LLM failure → **templated fallback** query set, log it, never fake success.

### `research/cache.py`
- Key = normalized query + provider; short TTL; JSON or sqlite; disable via env flag.

### `research/sanitize.py`
- `sanitize()` boundary helper. Retrieved web/vendor text is **data, never instructions** — fenced +
  labeled untrusted before any LLM sees it, so a vendor page cannot influence its own assessment.

### `research/README.md`
- Public interface, source tiers, Band message schema, and the demo narration (broad sweep →
  parallel evaluation → gap-directed re-investigation → synthesis).

## Agent wiring (inside scope guard)
- `agents/research.py` — standalone poll-loop worker (dedup handled `request_id`s).
- `agents/scout.py` — calls engine, emits `research_response` (evidence + one-line summary).
- `agents/compliance.py` — calls engine for regulatory tiers within its node.
- `agents/risk.py` / `agents/gap.py` — emit `research_request` w/ `gap_directives` on make-or-break
  gaps; read correlated `research_response`. **Risk: map already-computed low categories →
  directive strings only — no change to scoring math.**

## Scope guard (do NOT touch)
`questionnaire/` scoring math; `risk.py` scoring logic beyond consuming structured requests/evidence;
`web_server.py` re-scoring; the auto-email path. If tempted, stop and ask. Agent handles and chat
ownership unchanged.

## Conventions
Files < 800 lines, functions < 50 lines, no duplicated boilerplate (factor shared HTTP/client setup
once). Secrets via `os.getenv` only. `requirements.txt`: add+pin new deps (`httpx`); pin existing
unpinned lines without churning unrelated ones.

## Tests (`unittest`, mirroring `questionnaire/tests/`, providers + Band mocked)
1. Contract round-trip: serialize→parse a request and response, incl. `request_id` correlation + status transitions.
2. A `gap_directive` request triggers **scoped** retrieval only (not a full sweep) + correlated response.
3. Query planning expansion + templated fallback when the LLM is unavailable.
4. Dedup across providers returning overlapping URLs.
5. Ranking respects `source_tier` then `relevance`.
6. One provider raising does not abort the run and is recorded in `failures`.
7. `sanitize()` neutralizes an injected instruction string.
8. `EvidenceBundle` distinguishes not-found / not-searched / failed.
9. One live smoke test gated behind `RUN_LIVE_TESTS=1`, skipped by default.

## Commit sequence
1. `contract.py` + `models.py` + their tests.
2. `engine.py` + Phase-1 providers + `cache.py` + `sanitize.py` + `planner.py` + tests.
3. Scout rewrite (calls engine, emits `research_response`).
4. `agents/research.py` standalone worker.
5. Compliance / Risk / Gap wiring + re-investigation loop.
6. `requirements.txt` pin + README updates.

## README updates required (Presentation score)
- Agent framing: 6 → 7, or Research framed as shared infra (`README.md:5,55-62`).
- "Sequential chain … No polling, no orchestrator" → reframe as structured request/response (`README.md:423`).
- Scout row + demo transcript → show the new `research_response` format (`README.md:57,290-294`).
- Project Structure → add `research/` + `agents/research.py` (`README.md:383-411`).
- Setup/`.env.example` → new 7th-agent Band creds, optional openFDA key (`README.md:147-171`).
- Step 5 handle replacement → include `research.py` + new handle (`README.md:209-215`).
- (Out of scope, noted only: auto-email "Done" is live; Risk README describes dead `VERDICT_PROMPT`.)

## Assumptions to confirm during implementation (per spec instruction)
- **openFDA**: `https://api.fda.gov/device/{510k,pma,classification}.json?search=...`, keyless,
  rate-limited (free key raises limits). High confidence; confirm response shape live.
- **OCR breach portal**: no stable official JSON API → keep Tavily domain-filtered lookup as a tier.
- **CHPL** (deferred): `chpl.healthit.gov/rest/...` likely needs a free `API-Key` header — confirm before building.
- **Band raw REST**: `create_agent_chat_message` mentions field shape to confirm against the SDK.

## Definition of done (from task spec)
1. `research/` package: engine, providers, `Evidence`/`EvidenceBundle`, `contract.py`, cache, `sanitize()`.
2. Standalone `agents/research.py` worker (fallback to in-process Scout documented, identical contract).
3. Scout, Compliance, Risk, Gap wired to the contract + re-investigation loop.
4. `requirements.txt` updated + pinned.
5. Unit tests pass; live smoke test present but skipped.
6. `research/README.md` documenting interface, tiers, schema, and coordination narration.
