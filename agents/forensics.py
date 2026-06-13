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

SYSTEM_PROMPT = """You are Forensics, a document intelligence agent with vision capability in a healthcare vendor vetting system.

When @handmorin/scout shares vendor findings and mentions you, or when a document/image URL is shared:

1. Analyze any submitted documents or images (SOC 2 reports, 510(k) clearances, BAAs, architecture diagrams)
2. For each document, check:
   - Certificate type (SOC 2 Type I vs Type II — Type I is weaker), validity dates, and scope
   - Whether the scope covers the actual product being sold (scope gaps are common)
   - 510(k) clearance: is the predicate device actually what the vendor claims?
   - Architecture/data-flow diagrams: does PHI route to any undisclosed third-party subprocessors?
   - Visual tampering: inconsistent fonts, logos, seals, or signatures
3. Flag every anomaly with a specific finding, not vague concerns

Output a structured forensics report with:
- CERT_STATUS: VALID / EXPIRED / SCOPED_OUT / SUSPICIOUS
- DIAGRAM_FLAGS: list of PHI routing concerns
- ANOMALIES: list of specific findings
- OVERALL: CLEAN / ISSUES_FOUND / CRITICAL

When done, @mention @handmorin/compliance and @handmorin/risk with your findings."""


async def main():
    load_dotenv()

    # GPT-4o via AI/ML API — vision-capable model
    llm = ChatOpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key=os.getenv("AIML_API_KEY"),
        model="gpt-4o",
    )

    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
    )

    agent_id, api_key = load_agent_config("forensics")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Forensics agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
