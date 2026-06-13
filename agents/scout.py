import asyncio
import logging
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config

logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are Scout, a healthcare vendor intelligence agent.

When asked to research a healthcare technology vendor:
1. Use your search tool to find customer references, case studies, press releases, and news
2. Search for any red flags: lawsuits, data breaches, outages, regulatory violations
3. Summarize all findings clearly

When done, post your findings and @mention @handmorin/forensics and @handmorin/compliance
so they can begin their analysis in parallel.

Always be factual and cite what you found. If search returns nothing useful, say so."""


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
        additional_tools=[DuckDuckGoSearchRun()],
    )

    agent_id, api_key = load_agent_config("scout")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Scout agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
