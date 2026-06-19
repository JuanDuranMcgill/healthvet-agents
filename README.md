# HealthVet Agents

**Band of Agents Hackathon 2026 · Track 3: Regulated & High-Stakes Workflows**

A multi-agent system that automates healthcare technology vendor due diligence. Seven specialized AI agents coordinate through Band to vet vendors that U.S. health systems are considering purchasing — a process that normally takes 2–6 weeks of manual work.

Coordination is a **versioned message contract**, not loose prose: agents exchange structured `research_request` / `research_response` messages with correlation IDs and status, so the Band room is a traceable audit trail. A standalone, **non-LangGraph** research worker collaborates across frameworks, and the Risk veto is a targeted re-investigation negotiation rather than a blind full re-run. See [research/README.md](research/README.md).

---

## The Problem

When a hospital wants to buy a new clinical AI tool or EHR system, their procurement team must:

- Find and verify customer references
- Review SOC 2 reports, 510(k) clearances, and Business Associate Agreements
- Check for data breaches, lawsuits, and regulatory violations
- Cross-reference vendor marketing claims against actual evidence

This takes weeks and requires multiple specialized reviewers. Half the evidence is never found.

---

## How It Works

Six pipeline agents coordinate through a shared Band room (plus a standalone Research worker). Each pipeline agent handles one layer of the vetting and hands off to the next via @mention:

```
User → @Scout
         searches web: customer references, lawsuits, HIPAA breaches, news
                    ↓
       @Forensics
         analyzes: certifications, architecture flags, anomalies
                    ↓
       @Compliance
         checks: FDA, ONC, HIPAA, SOC 2 regulatory standing
                    ↓
       @Gap
         maps every evidence category: VERIFIED / MISSING / CRITICAL
                    ↓
       @Risk
         adversarial cross-reference → APPROVE / ESCALATE / REJECT
         (if evidence is too thin: posts a structured research_request to @Research)
                    |
                    |   re-investigation negotiation:
                    |   @Risk --research_request(gap_directives)--> @Research
                    |   @Research --research_response(evidence)----> @Risk
                    ↓   (@Research is a standalone, non-LangGraph worker)
       @Synthesis
         generates final auditable vendor trust report → @User
```

Two agents call the shared retrieval engine in different lanes: **Scout** runs the
broad web sweep; **Compliance** runs the regulatory tiers (openFDA, OCR breach)
itself. The **Research** worker answers gap-directed re-investigation requests —
both **Gap** (when it flags CRITICAL gaps) and **Risk** (on veto) can post a
`research_request`, each at most once per session.

### The Veto Loop (structured re-investigation)

Risk has veto authority. If it finds critical evidence gaps, instead of a blind
full re-run it posts a `research_request` carrying specific `gap_directives` to
the standalone **Research** worker. The worker runs *only* the scoped retrieval
for those directives and replies with a correlated `research_response`
(`complete`, or `needs_reinvestigation` if still unresolved). Risk reads the
correlated evidence and makes a final, non-vetoable verdict. The loop runs at
most once per session and is a genuine negotiation through Band.

---

## Agent Architecture

| # | Agent | Model | Role |
|---|---|---|---|
| 1 | **Scout** | `gpt-4o` | Web search: customer references, breach history, lawsuits, news |
| 2 | **Forensics** | `gpt-4o` | Document analysis: certifications, architecture flags, anomalies |
| 3 | **Compliance** | `gpt-4o-mini` | Regulatory standing: FDA, ONC, HIPAA, SOC 2 |
| 4 | **Gap** | `gpt-4o` | Evidence gap mapping across 9 categories with severity ratings |
| 5 | **Risk** | `gpt-4o` | Adversarial review + final verdict with veto authority |
| 6 | **Synthesis** | `Qwen/Qwen2.5-72B-Instruct` | Final auditable vendor trust report |
| 7 | **Research** | _(no LLM agent loop)_ | Standalone non-LangGraph worker; answers `research_request` messages via the shared retrieval engine |

Scout and Compliance also drive the shared retrieval engine directly (web lane and regulatory lane respectively). The Research worker is built on Band's `SimpleAdapter` rather than LangGraph — a deliberate second coordination pattern collaborating across frameworks.

**LLM Providers:**
- [AI/ML API](https://aimlapi.com) — unified frontier model access (gpt-4o, gpt-4o-mini)
- [Featherless AI](https://featherless.ai) — serverless open-source model inference (Qwen 72B)
- [Band](https://band.ai) — multi-agent coordination layer

**Why this provider stack?**

[AI/ML API](https://aimlapi.com) gives us a single OpenAI-compatible endpoint to access multiple model tiers without managing separate integrations. HealthVet uses this to cost-optimize across agents: `gpt-4o-mini` for fast structured extraction (Compliance), `gpt-4o` for deep adversarial reasoning (Scout, Forensics, Gap, Risk). One API key, one SDK, two model tiers — exactly what a production multi-agent system needs. For teams building regulated-industry pipelines where model selection per task actually matters, AI/ML API makes that practical without the overhead of maintaining multiple provider clients.

[Featherless AI](https://featherless.ai) powers Synthesis — the agent that writes the final vendor trust report delivered to the hospital. We chose an open-weight model (`Qwen2.5-72B-Instruct`) here deliberately: in a regulated industry, the compliance artifact needs to be reproducible and auditable end-to-end. Open-weight models mean a hospital's legal or IT team can inspect exactly what model produced their vendor report — not a black box. Featherless makes running a 72B model serverless and instant, with no GPU infrastructure to manage. For healthcare and other regulated domains where open-weight inference is a compliance requirement, not just a preference, Featherless fills a gap that hosted-only providers cannot.

---

## Setup

### Prerequisites

- Python 3.11+
- A [Band](https://band.ai) account — use promo code `BANDHACK26` for free Pro
- [AI/ML API](https://aimlapi.com) key
- [Featherless AI](https://featherless.ai) key — use promo code `BOA26`
- [Tavily](https://tavily.com) API key (1,000 free searches/month)
- [Exa](https://exa.ai) API key (free tier available)

---

### Step 1 — Clone and install

```bash
git clone https://github.com/juanduranmcgill/healthvet-agents
cd healthvet-agents

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### Step 2 — Create 7 agents in Band

You need to create one External Agent in Band for each of the 7 roles. Do this at [app.band.ai/agents](https://app.band.ai/agents).

For **each** of the seven agents below, repeat these steps:

1. Click **New Agent** → **External Agent**
2. Enter the agent name (use the exact names in the table)
3. Click **Create** — Band generates an `agent_id` (UUID) and `api_key`
4. Copy both values — you'll need them in Step 4

| Agent Name | Role |
|---|---|
| `Scout` | Web research |
| `Forensics` | Document analysis |
| `Compliance` | Regulatory checker |
| `Gap` | Evidence gap analyst |
| `Risk` | Final decision authority |
| `Synthesis` | Report generator |
| `Research` | Standalone retrieval worker (non-LangGraph) |

> The agent names don't need to match exactly in Band's UI — what matters is that each agent's `agent_id` and `api_key` are placed under the right key in `agent_config.yaml` (see Step 4).

---

### Step 3 — Create a Band room and add all 7 agents

1. In the Band app, click **New Room** (or use an existing room)
2. Open the room settings → **Members** → **Add Member**
3. Add all 7 agents you created: Scout, Forensics, Compliance, Gap, Risk, Synthesis, Research
4. Also note your own Band @handle (e.g. `@yourhandle`) — you'll use it to trigger Scout

> All 7 agents must be members of the same room. The pipeline passes messages between them via @mentions, so they all need to be present to receive triggers.

---

### Step 4 — Configure credentials

**Copy the example files:**

```bash
cp .env.example .env
cp agent_config.yaml.example agent_config.yaml
```

**Fill in `.env`** with your API keys:

```env
# LLM providers
AIML_API_KEY=sk-...          # from aimlapi.com
FEATHERLESS_API_KEY=...      # from featherless.ai

# Search
TAVILY_API_KEY=tvly-...      # from tavily.com
EXA_API_KEY=...              # from exa.ai

# Band — one pair per agent (from Step 2)
SCOUT_AGENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
SCOUT_API_KEY=...
FORENSICS_AGENT_ID=...
FORENSICS_API_KEY=...
COMPLIANCE_AGENT_ID=...
COMPLIANCE_API_KEY=...
GAP_AGENT_ID=...
GAP_API_KEY=...
RISK_AGENT_ID=...
RISK_API_KEY=...
SYNTHESIS_AGENT_ID=...
SYNTHESIS_API_KEY=...
```

**Fill in `agent_config.yaml`** — this is what the agents actually read at startup:

```yaml
scout:
  agent_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  api_key: "your-scout-band-api-key"

forensics:
  agent_id: "..."
  api_key: "..."

compliance:
  agent_id: "..."
  api_key: "..."

gap:
  agent_id: "..."
  api_key: "..."

risk:
  agent_id: "..."
  api_key: "..."

synthesis:
  agent_id: "..."
  api_key: "..."
```

**Important:** `agent_config.yaml` is gitignored. Never commit it — it contains your Band API keys.

---

### Step 5 — Update agent @mentions to match your handle

The agents reference each other by @handle. You need to update these to match your Band username.

Search for all @mentions across the code:

```bash
grep -rn "leejongmin1092" agents/ research/
```

Then replace every occurrence of `leejongmin1092` with your own Band handle. The agents that send @mentions are `scout.py`, `forensics.py`, `compliance.py`, `gap.py`, `risk.py`, and `synthesis.py`; the shared handle prefix the Risk veto and the Research worker use lives in [research/agent_io.py](research/agent_io.py) (`HANDLE_PREFIX`).

---

### Step 6 — Start all agents

```bash
./start.sh
```

This starts all 7 agents in the background and writes logs to `logs/<agent>.log`.

Verify they connected:

```bash
tail logs/scout.log logs/risk.log logs/synthesis.log
```

You should see `Agent started: Scout (band-sdk 1.0.0)` for each.

---

### Step 7 — (Optional) Run the hospital onboarding wizard

Before vetting a vendor, configure the hospital's priorities. This creates a weighted scoring profile used by the Risk agent:

```bash
python -m questionnaire.cli onboarding my-hospital
```

The wizard walks through 4 phases: ranking 9 evaluation categories, fine-tuning priority sliders, selecting deal-breakers (e.g. missing SOC 2, unresolved breach), and choosing risk appetite. The profile is saved to `questionnaire/profiles/my-hospital.yaml`. Set `HOSPITAL_PROFILE=my-hospital` in `.env` so Risk loads it automatically.

If you skip this step, Risk falls back to a balanced default profile.

---

### Step 8 — (Optional) Start the web dashboard

```bash
python web_server.py
```

Opens a dashboard at `http://localhost:8000` where you can:
- Start a vendor assessment by name (triggers the full 6-agent pipeline)
- Watch live status as each agent reports in
- View the quantitative scorecard with category breakdown
- Compare two vendors side by side
- Export results as CSV

---

## Running a Vendor Assessment

Open your Band room and send:

```
@yourhandle/scout Please run a full vendor assessment on [Vendor Name]
```

The full chain completes in **30–90 seconds**.

---

### Demo: Veradigm Assessment

Veradigm (formerly Allscripts) is a healthcare data and EHR company with a documented breach settlement and mixed compliance history — a good test case that exercises the full pipeline including the veto loop.

**Trigger:**
```
@yourhandle/scout Please run a full vendor assessment on Veradigm
```

**Expected output chain** (illustrative — Scout and Research messages carry a one-line human summary followed by a structured JSON payload; the lines below show the human-readable summaries):

```
Scout:      SCOUT RESEARCH REPORT: Veradigm
            Customer References: collaborations for digital health media, EHR integrations...
            Legal & Regulatory Issues: $10.5M breach settlement (2024), breach affecting
            millions of patients...
            HIPAA Breach Record: multiple breaches including substantial 2025 incident...
            → @Forensics

Forensics:  FORENSICS REPORT: Veradigm
            CERT_STATUS: UNVERIFIED — no explicit compliance certifications confirmed
            DIAGRAM_FLAGS: PHI routing concerns due to multiple breaches
            ANOMALIES: unverified claims on EHR integration reach; active legal settlement
            OVERALL: ISSUES_FOUND
            → @Compliance

Compliance: COMPLIANCE REPORT: Veradigm
            FDA Clearance: NOT_FOUND
            ONC Certification: NOT_FOUND
            HIPAA Compliance: NO_BREACHES_FOUND
            SOC 2: CLAIMED_UNVERIFIED
            Active Litigation: YES
            Overall Standing: NON-COMPLIANT
            → @Gap

Gap:        GAP ANALYSIS REPORT: Veradigm
            SOC 2 Type II: UNVERIFIED — CRITICAL
            FDA clearance: MISSING — CRITICAL
            ONC certification: MISSING — CRITICAL
            Critical gaps: 3 | Overall: NEEDS_MORE_EVIDENCE
            → @Risk

              *** STRUCTURED RE-INVESTIGATION FIRES ***

Risk:       🚨 VETO — structured re-investigation requested
            Fit Score: 31/100 · Verdict: REJECT
            research_request (request_id ab12cd34) → @Research
              gap_directives:
                - Find authoritative evidence for 'regulatory_compliance' (score 3/10)
                - Find authoritative evidence for 'security_breach' (score 4/10)

Research:   research_response (request_id ab12cd34, status=complete) → @Risk
            [REGULATORY, openfda] 510(k) clearance record(s) for Veradigm devices...
            [REGULATORY, ocr_breach] OCR breach portal entries...
            (scoped retrieval for the directives only; a failed lookup is reported
             as FAILED, never as "not found")

Risk:       RISK VERDICT: Veradigm — FINAL
            Evidence Quality Score: 4
            Compliance Standing: PARTIAL
            Final Verdict: ESCALATE
            Rationale: Unresolved HIPAA BAA gap and subprocessor opacity require
            higher scrutiny before vendor can proceed.
            → @Synthesis

Synthesis:  VENDOR TRUST REPORT: Veradigm
            Overall Verdict: ESCALATE
            Recommended Next Steps:
              1. Request HIPAA BAA from Veradigm
              2. Obtain subprocessor disclosure
              3. Gather clinical outcomes data
            → @User
```

---

## Monitoring Logs

Watch any agent in real time:

```bash
tail -f logs/risk.log       # see veto decisions
tail -f logs/synthesis.log  # see final reports
tail -f logs/scout.log      # see search activity
```

Watch the full pipeline at once:

```bash
tail -f logs/scout.log logs/forensics.log logs/compliance.log \
         logs/gap.log logs/risk.log logs/synthesis.log
```

---

## Project Structure

```
healthvet-agents/
├── agents/
│   ├── llm.py           # Shared LLM factory (ChatOpenAINoStrict patch)
│   ├── scout.py         # Web search: Tavily + Exa + HHS breach check
│   ├── forensics.py     # Document and certification analysis
│   ├── compliance.py    # Regulatory standing checker (graph_factory)
│   ├── gap.py           # Evidence gap analyst (graph_factory)
│   ├── risk.py          # Final decision authority + structured veto loop + scoring (graph_factory)
│   ├── synthesis.py     # Auditable trust report generator
│   └── research.py      # Standalone non-LangGraph retrieval worker (SimpleAdapter)
├── research/            # Retrieval engine + Band message contract (see research/README.md)
│   ├── engine.py        # Concurrent fan-out, dedup, tier-then-relevance ranking
│   ├── contract.py      # Versioned research_request / research_response schema
│   ├── models.py        # Evidence, EvidenceBundle, SourceTier
│   ├── planner.py       # LLM query expansion + templated fallback
│   ├── cache.py         # TTL query cache (disable via RESEARCH_CACHE_DISABLED)
│   ├── sanitize.py      # Prompt-injection hygiene for untrusted content
│   ├── agent_io.py      # Dep-free helpers shared by the agents
│   ├── providers/       # Tavily, Exa, DuckDuckGo, openFDA, OCR-breach adapters
│   └── tests/           # unittest suite (providers + Band mocked)
├── questionnaire/
│   ├── cli.py           # 4-phase hospital onboarding wizard (CLI)
│   ├── profile.py       # HospitalProfile — weighted categories, deal-breakers, thresholds
│   ├── scorer.py        # Quantitative fit scoring engine (0–100, APPROVE/ESCALATE/REJECT)
│   ├── extractor.py     # LLM extraction of 9-category evidence scores from agent reports
│   ├── gap.py           # Gap resolution for uncovered evidence categories
│   └── profiles/        # Saved hospital profiles (YAML)
├── web/
│   ├── index.html       # Dashboard UI
│   ├── app.js           # Live polling, vendor comparison, scorecard charts
│   └── style.css        # Styles
├── web_server.py        # HTTP dashboard server (port 8000)
├── run_agents.py        # Alternative launcher (supports --agent flag for single agent)
├── start.sh             # Starts all 7 agents with per-agent log files
├── .env.example         # API key template (copy to .env)
├── agent_config.yaml.example  # Band credential template (copy to agent_config.yaml)
├── requirements.txt
└── README.md
```

---

## Key Technical Details

**`ChatOpenAINoStrict`** — Band SDK tool schemas use `anyOf` for optional parameters. LangChain's default `bind_tools` passes `strict=True`, which causes 400 errors on AI/ML API. `ChatOpenAINoStrict` subclasses `ChatOpenAI` and drops the `strict` kwarg, fixing this silently.

**`graph_factory` for Compliance, Gap, and Risk** — These agents use a deterministic LangGraph graph instead of the ReAct tool-choice loop. The graph node calls `band_send_message` directly after LLM generation. This guarantees the handoff chain always fires, regardless of how the model decides to format its response.

**Veto state via module-level dict** — Risk tracks vetoed rooms in a module-level Python `set` (`_vetoed_rooms`), not in LangGraph's InMemorySaver. The Band SDK does not guarantee state persistence between message triggers for graph_factory agents. The module-level set persists for the lifetime of the process, correctly capping the veto loop at one round per room.

**Message-driven coordination** — The chain advances by @mention (Scout → Forensics → Compliance → Gap → Risk → Synthesis): each agent's `band_send_message` includes the next agent's @mention and Band wakes that agent. There is no central orchestrator. On top of this, Risk and the standalone Research worker exchange a structured `research_request` / `research_response` contract for gap-directed re-investigation, so coordination state (correlation IDs, status) is explicit in the room rather than implied by prose.

**Structured Band contract + cross-framework worker** — `research/contract.py` defines a versioned schema embedded in message content (a human summary line + fenced JSON), so downstream agents parse a contract instead of scraping text. The Research worker (`agents/research.py`) is built on Band's `SimpleAdapter`, **not** LangGraph — a second coordination pattern that collaborates with the LangGraph agents purely through the shared message contract.

**Anti-fabrication evidence** — The retrieval engine never invents a value to mask a failure. `EvidenceBundle` keeps *not-found*, *not-searched*, and *failed* as three distinct states, and ranking is tier-first (regulatory > vendor marketing). Retrieved text is sanitized as untrusted before any LLM sees it.

---

## Features

| Feature | Status |
|---|---|
| 6-agent message-driven pipeline | ✅ Done |
| Versioned Band research contract (request/response, correlation IDs, status) | ✅ Done |
| Multi-provider retrieval engine (web + openFDA + OCR), tier-ranked, anti-fabrication | ✅ Done |
| Standalone non-LangGraph Research worker (cross-framework) | ✅ Done |
| Structured Risk veto → scoped re-investigation negotiation (capped at 1) | ✅ Done |
| Quantitative scoring rubric (weighted fit 0–100, deal-breakers) | ✅ Done |
| Hospital criteria setup wizard (4-phase CLI onboarding) | ✅ Done |
| Web dashboard (live status, scorecard, vendor comparison, CSV export) | ✅ Done |
| Automated email outreach on ESCALATE verdict | ✅ Done |
| Interactive graph view (frontend) | 🔄 In progress |
| Proactive gap notification | 📋 Planned |

---

## Built With

- [Band](https://band.ai) — multi-agent coordination
- [AI/ML API](https://aimlapi.com) — frontier model access
- [Featherless AI](https://featherless.ai) — open-source model inference
- [LangGraph](https://langchain-ai.github.io/langgraph/) — agent framework
- [Tavily](https://tavily.com) — web search
- [Exa](https://exa.ai) — semantic search
- [openFDA](https://open.fda.gov) — authoritative device clearance records (regulatory tier)

---

## Team

Built during the [Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon) · June 12–19, 2026
