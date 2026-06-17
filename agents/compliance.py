import asyncio
import logging
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from agents.llm import make_llm

logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are Compliance, a healthcare vendor regulatory analyst.

Your task: assess the vendor's regulatory standing based on the conversation and call band_send_message with your findings.

Write this report:

**COMPLIANCE REPORT: [Vendor Name]**
- FDA Clearance: VERIFIED / NOT_FOUND / NOT_APPLICABLE — [one line]
- ONC Certification: VERIFIED / NOT_FOUND / NOT_APPLICABLE — [one line]
- HIPAA Compliance: VERIFIED / NO_BREACHES_FOUND / UNKNOWN — [one line]
- SOC 2: VERIFIED / NOT_FOUND / CLAIMED_UNVERIFIED — [one line]
- Active Litigation: YES / NO — [one line]
- Regulatory Violations: YES / NO — [one line]
- Overall Standing: COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN

You MUST call band_send_message with:
- mentions: ["@handmorin/gap"]
- content: the report above + "Gap, please run your evidence gap analysis."

Calling band_send_message is your only action. Call it exactly once. Do it now."""


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=make_llm("gpt-4o-mini"),
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
    )

    agent_id, api_key = load_agent_config("compliance")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Compliance agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
