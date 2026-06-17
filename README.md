# HealthVet Agents

**Band of Agents Hackathon 2026 · Track 3: Regulated & High-Stakes Workflows**

A multi-agent system that automates healthcare technology vendor due diligence. Six specialized AI agents collaborate through Band to vet vendors that U.S. health systems are considering purchasing — a process that normally takes weeks of manual work.

---

## The Problem

When a hospital wants to buy a new clinical AI tool or EHR system, their procurement team must:
- Find and verify customer references
- Read SOC 2 reports, 510(k) clearances, and BAAs
- Check for data breaches, lawsuits, and regulatory violations
- Cross-reference all of this against the vendor's marketing claims

This takes 2–6 weeks and requires multiple specialized reviewers. Half the evidence is never found.

---

## How It Works

Six agents coordinate through a shared Band room, each handling a distinct part of the vetting process:

```
User → @Scout → searches web for references, breaches, lawsuits, news
                    ↓
             @Forensics → analyzes document and certification evidence
                    ↓
             @Compliance → checks FDA, ONC, HIPAA, SOC 2 regulatory standing
                    ↓
               @Gap → maps every evidence category: VERIFIED / MISSING / CRITICAL
                    ↓
              @Risk → cross-references everything, makes final APPROVE / ESCALATE / REJECT
                    ↓
           @Synthesis → generates final auditable vendor trust report → @User
```

The key coordination mechanic: **Risk has veto authority**. If it finds contradictions between Scout's research, Forensics' document findings, and Compliance's regulatory assessment, it posts a `VETO` and specific re-investigation directives back into the Band room.

---

## Agent Architecture

| Agent | Model | Role |
|---|---|---|
| **Scout** | AI/ML API `gpt-4o` | Web search: customer references, breach history, lawsuits, news |
| **Forensics** | AI/ML API `gpt-4o` | Document analysis: certifications, architecture flags, anomalies |
| **Compliance** | AI/ML API `gpt-4o-mini` | Regulatory standing: FDA, ONC, HIPAA, SOC 2 |
| **Gap** | AI/ML API `gpt-4o` | Evidence gap mapping across 9 categories with severity ratings |
| **Risk** | AI/ML API `gpt-4o` | Adversarial review + final verdict (APPROVE / ESCALATE / REJECT) |
| **Synthesis** | Featherless `Qwen/Qwen2.5-72B-Instruct` | Final auditable vendor trust report |

**LLM Providers:**
- [AI/ML API](https://aimlapi.com) — unified access to frontier models
- [Featherless AI](https://featherless.ai) — serverless open-source model inference
- [Band](https://band.ai) — agent coordination layer, shared rooms, @mention routing

**Implementation note:** Gap and Risk use LangGraph's `graph_factory` pattern for deterministic tool execution — the graph node always calls `band_send_message` directly rather than relying on LLM tool-choice. This guarantees the handoff chain never stalls.

---

## Example Output

```
Scout:      SCOUT RESEARCH REPORT: Veradigm
            Customer References: ... Legal Issues: $10.5M breach settlement ...
               ↓
Forensics:  FORENSICS REPORT: CERT_STATUS: UNVERIFIED — OVERALL: CRITICAL
               ↓
Compliance: COMPLIANCE REPORT: NON-COMPLIANT — Active Litigation: YES
               ↓
Gap:        GAP ANALYSIS: 3 critical gaps (SOC 2, FDA, ONC) — INSUFFICIENT
               ↓
Risk:       RISK VERDICT: ESCALATE — Evidence Quality Score: 4/10
               ↓
Synthesis:  VENDOR TRUST REPORT — Verdict: ESCALATE
            [full audit trail delivered to @User]
```

Full chain completes in ~30–90 seconds.

---

## Setup

### Prerequisites
- Python 3.11+
- A [Band](https://band.ai) account (use promo code `BANDHACK26` for free Pro)
- [AI/ML API](https://aimlapi.com) key
- [Featherless AI](https://featherless.ai) key (use promo code `BOA26`)
- [Tavily](https://tavily.com) API key (Scout's web search)
- [Exa](https://exa.ai) API key (Scout's semantic search)

### Installation

```bash
git clone https://github.com/juanduranmcgill/healthvet-agents
cd healthvet-agents

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

**1. Copy and fill in API keys:**
```bash
cp .env.example .env
```
Edit `.env` with your actual keys (AI/ML, Featherless, Tavily, Exa, and Band credentials for each agent).

**2. Copy and fill in Band agent credentials:**
```bash
cp agent_config.yaml.example agent_config.yaml
```

To get Band agent credentials:
1. Go to [app.band.ai/agents](https://app.band.ai/agents)
2. Click **New Agent → External Agent** for each of the 6 agents (Scout, Forensics, Compliance, Gap, Risk, Synthesis)
3. Copy the `agent_id` and `api_key` into `agent_config.yaml`
4. Create a Band room and add all 6 agents as participants

---

## Running the Agents

Start all 6 agents in one command:

```bash
./start.sh
```

Logs are written to `logs/<agent>.log`. Watch the handoff in real time:

```bash
tail -f logs/risk.log logs/synthesis.log
```

Then trigger a vetting workflow in the Band room:

```
@<your-username>/scout Please run a full vendor assessment on Veradigm
```

---

## Project Structure

```
healthvet-agents/
├── agents/
│   ├── llm.py           # Shared LLM factory (ChatOpenAINoStrict patch)
│   ├── scout.py         # Web search agent (Tavily + Exa + HHS breach)
│   ├── forensics.py     # Document analysis agent
│   ├── compliance.py    # Regulatory checker
│   ├── gap.py           # Evidence gap analyst (graph_factory)
│   ├── risk.py          # Final decision authority (graph_factory)
│   └── synthesis.py     # Report generator (Featherless Qwen 72B)
├── start.sh             # Starts all 6 agents with per-agent log files
├── .env.example
├── agent_config.yaml.example
├── requirements.txt
└── README.md
```

---

## Key Technical Details

**`ChatOpenAINoStrict`** — Band SDK tool schemas contain `anyOf` fields (optional parameters). The `langchain.agents.create_agent` function hardcodes `strict=True` in `bind_tools`, which causes 400 errors on AI/ML API. `ChatOpenAINoStrict` subclasses `ChatOpenAI` and drops the `strict` kwarg.

**`graph_factory` for Gap and Risk** — These agents use a deterministic LangGraph graph instead of the ReAct tool-choice loop. The graph node calls `band_send_message` directly after LLM generation, guaranteeing the handoff always fires regardless of how the model decides to respond.

**Sequential chain** — The pipeline is fully sequential (Scout → Forensics → Compliance → Gap → Risk → Synthesis). Each agent's `band_send_message` call includes the next agent's @mention, creating a reliable message-passing chain through Band rooms.

---

## Roadmap

- **Interactive graph view** — visual dashboard showing the vendor's trust profile with nodes for each evidence type and edges showing contradictions
- **Automated scoring system** — structured pros/cons score derived from all agent findings with a defensible, configurable rubric
- **Criteria setup wizard** — 10-minute conversational onboarding where the system asks the hospital about their specific requirements before running the vetting
- **Automated email outreach** — when agents detect missing information (expired cert, unverifiable reference), automatically draft and send a request to the vendor
- **Proactive gap notification** — agents self-identify when stuck and route it as a low-priority notification rather than blocking the workflow

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
