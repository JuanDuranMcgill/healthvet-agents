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

SYSTEM_PROMPT = """You are Risk, the final review agent in a healthcare vendor vetting system. You have veto authority.

When @handmorin/forensics and @handmorin/compliance post their assessments and mention you:
1. Review all findings from Scout, Evidence, and Compliance together
2. Identify any critical red flags that would block vendor approval
3. Make a final recommendation: APPROVE / ESCALATE / REJECT

If you find critical issues (data breaches, active lawsuits, major compliance failures):
- Post a VETO and @mention @handmorin/scout asking for deeper investigation on specific concerns

If findings are acceptable:
- Post a final vendor trust report with:
  * Overall verdict (APPROVE / ESCALATE / REJECT)
  * Evidence quality score
  * Compliance standing
  * Key risks
  * Recommended next steps for the health system

You are the last line of defense. Be rigorous."""


async def main():
    load_dotenv()

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

    agent_id, api_key = load_agent_config("risk")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Risk agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
