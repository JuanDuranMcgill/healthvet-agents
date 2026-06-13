# HealthVet Agents

**Band of Agents Hackathon 2026 · Track 3: Regulated & High-Stakes Workflows**

A multi-agent system that automates healthcare technology vendor due diligence. Five specialized AI agents collaborate through Band to vet vendors that U.S. health systems are considering purchasing — a process that normally takes weeks of manual work.

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

Five agents coordinate through a shared Band room, each handling a distinct part of the vetting process:

```
User → @Scout → searches web for references, breaches, news
             ↓
       @Forensics → reads submitted documents with vision (SOC 2, 510(k), diagrams)
       @Compliance → checks FDA, ONC, HIPAA regulatory standing
             ↓
       @Risk → cross-checks everything, can VETO and send agents back to re-investigate
             ↓
       @Synthesis → generates final auditable vendor trust report
```

The key coordination mechanic: **Risk has veto authority**. If it finds a contradiction between what Scout found, what Forensics read in the documents, and what Compliance determined — it posts a `VETO` and specific re-investigation directives back into the Band room. This non-linear loop is what makes Band necessary.

---

## Agent Architecture

| Agent | Model | Role |
|---|---|---|
| **Scout** | AI/ML API `gpt-4o-mini` | Web search: customer references, breach history, lawsuits, news |
| **Forensics** | AI/ML API `gpt-4o` (vision) | Document analysis: SOC 2 certs, 510(k) clearances, architecture diagrams |
| **Compliance** | AI/ML API `gpt-4o-mini` | Regulatory standing: FDA, ONC, HIPAA, SOC 2 requirements |
| **Risk** | AI/ML API `gpt-4o` | Adversarial review + veto authority. Triggers re-investigation loops |
| **Synthesis** | Featherless `Qwen/Qwen2.5-72B-Instruct` | Final auditable trust report generation |

**LLM Providers:**
- [AI/ML API](https://aimlapi.com) — unified access to frontier models (GPT-4o, Claude, etc.)
- [Featherless AI](https://featherless.ai) — serverless open-source model inference (Qwen 72B)
- [Band](https://band.ai) — agent coordination layer, shared rooms, @mention routing

---

## Demo Scenarios

**Vendor A — Clean vendor:** Packet in → Forensics verifies certs → Scout finds solid references → Compliance passes → Risk approves → auditable report in ~90 seconds.

**Vendor B — Problem vendor:** Forensics reads the SOC 2 and flags it as Type I (not Type II), expired, with scope excluding the clinical module being sold. Scout surfaces a 2024 breach the vendor never disclosed. Risk vetoes and posts specific re-investigation directives. Final verdict: **DO NOT PROCEED**, with a full audit trail.

---

## Setup

### Prerequisites
- Python 3.11+
- A [Band](https://band.ai) account (use promo code `BANDHACK26` for free Pro)
- [AI/ML API](https://aimlapi.com) key
- [Featherless AI](https://featherless.ai) key (use promo code `BOA26`)

### Installation

```bash
git clone https://github.com/juanduranmcgill/healthvet-agents
cd healthvet-agents

module load python/3.11.5   # if on HPC; skip otherwise
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

**1. Copy and fill in API keys:**
```bash
cp .env.example .env
```
Edit `.env` with your actual keys.

**2. Copy and fill in Band agent credentials:**
```bash
cp agent_config.yaml.example agent_config.yaml
```

To get Band agent credentials:
1. Go to [app.band.ai/agents](https://app.band.ai/agents)
2. Click **New Agent → External Agent** for each of the 5 agents (Scout, Forensics, Compliance, Risk, Synthesis)
3. Copy the `agent_id` and `api_key` for each into `agent_config.yaml`
4. Create a Band room and add all 5 agents as participants

---

## Running the Agents

Open 5 terminals and run each agent:

```bash
source venv/bin/activate && python agents/scout.py
source venv/bin/activate && python agents/forensics.py
source venv/bin/activate && python agents/compliance.py
source venv/bin/activate && python agents/risk.py
source venv/bin/activate && python agents/synthesis.py
```

Then trigger a vetting workflow in the Band room:

```
@scout research the vendor "Veradigm" for our healthcare vendor vetting
```

---

## Project Structure

```
healthvet-agents/
├── agents/
│   ├── scout.py         # Web search agent (AI/ML API)
│   ├── forensics.py     # Document vision agent (AI/ML API GPT-4o)
│   ├── compliance.py    # Regulatory checker (AI/ML API)
│   ├── risk.py          # Veto authority (AI/ML API)
│   └── synthesis.py     # Report generator (Featherless Qwen 72B)
├── .env.example
├── agent_config.yaml.example
├── requirements.txt
└── README.md
```

---

## Make-or-Break Features (Roadmap)

These are the features that would turn this from a prototype into a production system:

- **Automated email outreach** — when agents detect missing information (expired cert, unverifiable reference), automatically draft and send a request to the vendor. Should only trigger in genuine edge cases (~once/month per vendor), not on every gap.

- **Interactive graph view** — visual dashboard showing the vendor's trust profile: nodes for each evidence type, edges showing contradictions, pros/cons clearly labeled. Currently all output is text.

- **Automated scoring system** — a structured pros/cons score that Risk derives from all agent findings. Key challenge: most vendor evaluation criteria are qualitative, not quantitative (unlike hardware benchmarks). Needs a defensible rubric.

- **Criteria setup wizard** — a 10-minute conversational onboarding where the system asks the hospital about their specific requirements (PHI volume, required certifications, integration environment) before running the vetting. This determines the scoring weights.

- **Proactive gap notification** — agents should self-identify when they're stuck ("I cannot verify this reference — the health system doesn't have a public case study"). Risk routes this as a low-priority notification rather than blocking the workflow.

- **Existing system research** — validate whether equivalent tools already exist in the market (health IT vendor intelligence platforms, procurement automation tools) and where this system's approach is differentiated.

---

## Built With

- [Band](https://band.ai) — multi-agent coordination
- [AI/ML API](https://aimlapi.com) — frontier model access
- [Featherless AI](https://featherless.ai) — open-source model inference
- [LangGraph](https://langchain-ai.github.io/langgraph/) — agent framework
- [LangChain](https://python.langchain.com/) — LLM tooling

---

## Team

Built during the [Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon) · June 12–19, 2026
