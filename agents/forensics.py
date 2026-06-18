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

SYSTEM_PROMPT = """You are Forensics, a healthcare vendor evidence analyst.

Your task: analyze the vendor research in this conversation and call band_send_message with your findings.

Write this report based on what Scout found:

**FORENSICS REPORT: [Vendor Name]**
- CERT_STATUS: UNVERIFIED / VALID / NOT_PROVIDED — [reason]
- DIAGRAM_FLAGS: [PHI routing concerns, or "none identified"]
- ANOMALIES: [unverified claims, missing documents, red flags]
- OVERALL: CLEAN / ISSUES_FOUND / CRITICAL / INSUFFICIENT_EVIDENCE

You MUST call band_send_message with:
- mentions: ["@leejongmin1092/compliance"]
- content: the report above + "Compliance, please assess the regulatory standing."

Calling band_send_message is your only action. Call it exactly once. Do it now."""


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=make_llm(),
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
    )

    agent_id, api_key = load_agent_config("forensics")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Forensics agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
