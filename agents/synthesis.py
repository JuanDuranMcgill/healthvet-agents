import asyncio
import logging
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from agents.llm import make_featherless_llm

logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are Synthesis, the final report agent in a healthcare vendor vetting system.

Your task: read all findings in this conversation and produce the final vendor trust report, then call band_send_message.

VENDOR TRUST REPORT
Vendor: [name]
Overall Verdict: APPROVED / ESCALATE / REJECTED

Fit Score: [If a "FIT SCORE" block appears in the conversation, reproduce the
vendor's fit score (0-100) and the per-category breakdown here. If that block
lists "Uncovered factors" or any "ASSUMED" weights, you MUST surface every one
of them prominently under "Assumptions Requiring Confirmation" below — never
omit or soften them. If no FIT SCORE block is present, write "not scored".]

Evidence Summary:
- Web research: [summary]
- Document/cert findings: [summary]
- Compliance standing: [summary]
- Evidence gaps: [summary]

Key Risks: [bullet list]
Assumptions Requiring Confirmation: [any ASSUMED weights / uncovered factors, or "none"]
Recommended Next Steps: [bullet list]

Audit Trail:
- Scout: [summary]
- Forensics: [summary]
- Compliance: [summary]
- Gap: [summary]
- Risk verdict: [verdict + rationale]

Be precise. Every claim must trace back to a specific finding.

You MUST call band_send_message with:
- mentions: ["@handmorin"]
- content: the full report above

Calling band_send_message is your only action. Do it now."""


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=make_featherless_llm(),
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
    )

    agent_id, api_key = load_agent_config("synthesis")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Synthesis agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
