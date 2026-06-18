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
logger = logging.getLogger("compliance")

COMPLIANCE_PROMPT = """You are Compliance, a healthcare vendor regulatory analyst.

Based on all findings in this conversation, write a compliance report for the vendor.

**COMPLIANCE REPORT: [Vendor Name]**
- FDA Clearance: VERIFIED / NOT_FOUND / NOT_APPLICABLE — [one line]
- ONC Certification: VERIFIED / NOT_FOUND / NOT_APPLICABLE — [one line]
- HIPAA Compliance: VERIFIED / NO_BREACHES_FOUND / UNKNOWN — [one line]
- SOC 2: VERIFIED / NOT_FOUND / CLAIMED_UNVERIFIED — [one line]
- Active Litigation: YES / NO — [one line]
- Regulatory Violations: YES / NO — [one line]
- Overall Standing: COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN

Write the report ONLY. No preamble."""


class ComplianceState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def graph_factory(band_tools):
    band_send = next(t for t in band_tools if "send_message" in t.name)
    llm = make_llm("gpt-4o-mini")

    async def compliance_node(state: ComplianceState) -> dict:
        messages = state.get("messages", [])
        logger.info(f"[Compliance] received {len(messages)} messages")

        report = await llm.ainvoke(
            [SystemMessage(content=COMPLIANCE_PROMPT)] + list(messages)
        )
        logger.info(f"[Compliance] report: {report.content[:200]}")

        result = await band_send.ainvoke({
            "content": report.content + "\n\nGap, please run your evidence gap analysis.",
            "mentions": ["@leejongmin1092/gap"],
        })
        logger.info(f"[Compliance] band_send result: {result}")

        return {"messages": [report]}

    builder = StateGraph(ComplianceState)
    builder.add_node("compliance", compliance_node)
    builder.set_entry_point("compliance")
    builder.add_edge("compliance", END)
    return builder.compile(checkpointer=InMemorySaver())


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(graph_factory=graph_factory)

    agent_id, api_key = load_agent_config("compliance")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Compliance agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
