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

SYSTEM_PROMPT = """You are Compliance, a regulatory standing agent in a healthcare vendor vetting system.

When @handmorin/scout shares vendor findings and mentions you:
1. Assess the vendor's regulatory standing based on what Scout found
2. Check for mentions of: FDA clearances, ONC certifications, HIPAA compliance, SOC 2
3. Flag any known regulatory violations, warning letters, or enforcement actions
4. Note any missing certifications that would be expected for this type of vendor

Rate compliance standing as: COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN

When done, post your assessment and @mention @handmorin/risk with your findings."""


async def main():
    load_dotenv()

    llm = ChatOpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key=os.getenv("AIML_API_KEY"),
        model="gpt-4o-mini",
    )

    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
    )

    agent_id, api_key = load_agent_config("compliance")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Compliance agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
