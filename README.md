# HealthVet Agents

**Band of Agents Hackathon 2026 · Track 3: Regulated & High-Stakes Workflows**

A multi-agent system that automates healthcare technology vendor due diligence. Six specialized AI agents coordinate through Band to vet vendors that U.S. health systems are considering purchasing — a process that normally takes 2–6 weeks of manual work.

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

Six agents coordinate through a shared Band room. Each agent handles one layer of the vetting pipeline and hands off to the next via @mention:

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
         (if evidence is too thin: issues VETO, sends @Scout back for re-investigation)
                    ↓
       @Synthesis
         generates final auditable vendor trust report → @User
```

### The Veto Loop

Risk has veto authority. If it finds 2+ critical evidence gaps, it rejects the first run and sends Scout back with specific re-investigation directives. Scout re-runs targeted searches. The full chain fires again. Risk makes a final, non-vetoable verdict. This loop runs at most once per vetting session.

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

### Step 2 — Create 6 agents in Band

You need to create one External Agent in Band for each of the 6 roles. Do this at [app.band.ai/agents](https://app.band.ai/agents).

For **each** of the six agents below, repeat these steps:

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

> The agent names don't need to match exactly in Band's UI — what matters is that each agent's `agent_id` and `api_key` are placed under the right key in `agent_config.yaml` (see Step 4).

---

### Step 3 — Create a Band room and add all 6 agents

1. In the Band app, click **New Room** (or use an existing room)
2. Open the room settings → **Members** → **Add Member**
3. Add all 6 agents you created: Scout, Forensics, Compliance, Gap, Risk, Synthesis
4. Also note your own Band @handle (e.g. `@yourhandle`) — you'll use it to trigger Scout

> All 6 agents must be members of the same room. The pipeline passes messages between them via @mentions, so they all need to be present to receive triggers.

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

The agents reference each other by @handle (e.g. `@handmorin/scout`). You need to update these to match your Band username.

Search for all @mentions across the agent files and replace `handmorin` with your handle:

```bash
grep -r "handmorin" agents/
```

Then open each file and replace `@handmorin/` with `@yourhandle/`. The agents that send @mentions are: `scout.py`, `forensics.py`, `compliance.py`, `gap.py`, `risk.py`, and `synthesis.py`.

---

### Step 6 — Start all agents

```bash
./start.sh
```

This starts all 6 agents in the background and writes logs to `logs/<agent>.log`.

Verify they connected:

```bash
tail logs/scout.log logs/risk.log logs/synthesis.log
```

You should see `Agent started: Scout (band-sdk 1.0.0)` for each.

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

**Expected output chain:**

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

                    *** VETO LOOP FIRES ***

Risk:       🚨 VETO #1 — Re-investigation Required
            Evidence Quality Score: 3
            Final Verdict: REJECT
            VETO DIRECTIVES:
              - Evaluation of SOC 2 Type II compliance documentation
              - Verification of FDA clearance processes
              - Investigation of ONC certification status
            → @Scout (re-investigation)

Scout:      SCOUT RESEARCH REPORT: Veradigm (RE-INVESTIGATION)
            SOC 2 Type II: Veradigm claims SOC 2, Type 2 compliance; documentation
            exists on their legal security program page...
            ONC Certification: Veradigm EHR achieved 2015 ONC Health IT Certification...
            → @Forensics

            [Forensics → Compliance → Gap chain re-runs with updated findings]

Gap:        Critical gaps: 2 (HIPAA BAA, Subprocessor transparency)
            Overall: NEEDS_MORE_EVIDENCE
            → @Risk

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
│   ├── risk.py          # Final decision authority + veto loop (graph_factory)
│   └── synthesis.py     # Auditable trust report generator
├── start.sh             # Starts all 6 agents with per-agent log files
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

**Sequential chain** — The pipeline is fully sequential (Scout → Forensics → Compliance → Gap → Risk → Synthesis). Each agent's `band_send_message` call includes the next agent's @mention. Band delivers the message; the next agent wakes up. No polling, no orchestrator.

---

## Roadmap

- **Interactive graph view** — visual trust profile dashboard with nodes for each evidence type and edges showing contradictions
- **Automated scoring rubric** — structured pros/cons score with a defensible, configurable weighting system
- **Criteria setup wizard** — 10-minute conversational onboarding where the system learns the hospital's specific requirements before vetting
- **Automated email outreach** — when agents detect a missing document (expired cert, unverifiable reference), auto-draft a request to the vendor
- **Proactive gap notification** — route stalls as low-priority async notifications rather than blocking the workflow

---

## Built With

- [Band](https://band.ai) — multi-agent coordination
- [AI/ML API](https://aimlapi.com) — frontier model access
- [Featherless AI](https://featherless.ai) — open-source model inference
- [LangGraph](https://langchain-ai.github.io/langgraph/) — agent framework
- [Tavily](https://tavily.com) — web search
- [Exa](https://exa.ai) — semantic search

---

## Team

Built during the [Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon) · June 12–19, 2026
