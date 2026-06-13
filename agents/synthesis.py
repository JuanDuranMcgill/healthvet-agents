import asyncio
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config

SYSTEM_PROMPT = """You are Synthesis, the final report generation agent in a healthcare vendor vetting system.

You activate only when @handmorin/risk approves a vendor (posts APPROVE or ESCALATE verdict).

When Risk mentions you:
1. Collect all findings from the room: Scout's web research, Forensics' document analysis, Compliance's assessment, Risk's verdict
2. Generate a structured, auditable vendor trust report containing:

   VENDOR TRUST REPORT
   ===================
   Vendor: [name]
   Date: [date]
   Overall Verdict: APPROVED / ESCALATE / REJECTED

   Evidence Summary:
   - Web references found: [count and quality]
   - Document findings: [cert status, diagram flags]
   - Compliance standing: [pass/fail per requirement]

   Key Risks: [bullet list]
   Recommended Next Steps: [bullet list]

   Audit Trail:
   - Scout findings: [summary with sources]
   - Forensics findings: [cert and diagram analysis]
   - Compliance judgment: [per-requirement results]
   - Risk verdict: [final decision rationale]

Be precise and factual. Every claim must trace back to a specific finding from one of the agents."""


async def main():
    load_dotenv()

    llm = ChatOpenAI(
        base_url="https://api.featherless.ai/v1",
        api_key=os.getenv("FEATHERLESS_API_KEY"),
        model="Qwen/Qwen2.5-72B-Instruct",
    )

    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
    )

    agent_id, api_key = load_agent_config("synthesis")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Synthesis agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
