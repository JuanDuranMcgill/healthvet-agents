import asyncio
import logging
import operator
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import BaseMessage, SystemMessage
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from agents.llm import make_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("risk")

VERDICT_PROMPT = """You are Risk, the final decision authority in a healthcare vendor vetting pipeline.

Based on all findings in the conversation, write your risk verdict. Be specific to the vendor name if mentioned.

**RISK VERDICT: [Vendor Name]**
Evidence Quality Score: [1-10]
Compliance Standing: [COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN]

Key Risks:
- [top 3-5 risks identified]

Final Verdict: APPROVE / ESCALATE / REJECT
Rationale: [2-3 sentences]

Write the report ONLY. No preamble or explanation."""


class RiskState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def graph_factory(band_tools):
    band_send = next(t for t in band_tools if "send_message" in t.name)
    llm = make_llm()

    async def risk_node(state: RiskState) -> dict:
        messages = state.get("messages", [])
        logger.info(f"[Risk] received {len(messages)} messages")

        verdict = await llm.ainvoke(
            [SystemMessage(content=VERDICT_PROMPT)] + list(messages)
        )
        logger.info(f"[Risk] verdict generated: {verdict.content[:200]}")

        result = await band_send.ainvoke({
            "content": verdict.content,
            "mentions": ["@handmorin/synthesis"],
        })
        logger.info(f"[Risk] band_send_message result: {result}")

        return {"messages": [verdict]}

    builder = StateGraph(RiskState)
    builder.add_node("risk", risk_node)
    builder.set_entry_point("risk")
    builder.add_edge("risk", END)
    return builder.compile(checkpointer=InMemorySaver())


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(graph_factory=graph_factory)

    agent_id, api_key = load_agent_config("risk")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Risk agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
