import asyncio
import logging
import operator
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from agents.llm import make_llm
from research.contract import serialize
from research.agent_io import (
    vendor_from_messages,
    directives_from_gap_report,
    build_research_request,
    reply_handle,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gap")

# Tracks rooms where Gap has already requested re-investigation (cap at one).
_gap_requested_rooms: set = set()

GAP_PROMPT = """You are Gap, a healthcare vendor evidence gap analyst.

Based on all findings in this conversation, write a gap analysis report for the vendor.

For each category, assign: VERIFIED / UNVERIFIED / MISSING / NOT_APPLICABLE
For MISSING or UNVERIFIED items, assign severity: CRITICAL / MODERATE / LOW

**GAP ANALYSIS REPORT: [Vendor Name]**
- SOC 2 Type II: [STATUS] — [SEVERITY if not VERIFIED] — [one line]
- HIPAA BAA: [STATUS] — [one line]
- Clinical outcomes: [STATUS] — [SEVERITY if not VERIFIED] — [one line]
- Named customer references: [STATUS] — [SEVERITY if not VERIFIED] — [one line]
- Data breach history: [STATUS] — [one line]
- Active litigation: [STATUS] — [one line]
- FDA clearance: [STATUS] — [SEVERITY if not VERIFIED] — [one line]
- ONC certification: [STATUS] — [SEVERITY if not VERIFIED] — [one line]
- Subprocessor transparency: [STATUS] — [SEVERITY if not VERIFIED] — [one line]

Critical gaps: [count] — [list] | Moderate gaps: [count]
Overall evidence verdict: SUFFICIENT_TO_DECIDE / NEEDS_MORE_EVIDENCE / INSUFFICIENT

Write the report ONLY. No preamble."""


class GapState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def graph_factory(band_tools):
    band_send = next(t for t in band_tools if "send_message" in t.name)
    llm = make_llm()

    async def gap_node(state: GapState, config: RunnableConfig) -> dict:
        messages = state.get("messages", [])
        contents = [m.content for m in messages if hasattr(m, "content")]
        logger.info(f"[Gap] received {len(messages)} messages")

        report = await llm.ainvoke(
            [SystemMessage(content=GAP_PROMPT)] + list(messages)
        )
        logger.info(f"[Gap] report: {report.content[:200]}")

        thread_id = config.get("configurable", {}).get("thread_id", "unknown")
        already_requested = thread_id in _gap_requested_rooms
        insufficient = "INSUFFICIENT" in report.content.upper()
        directives = directives_from_gap_report(report.content)

        if insufficient and directives and not already_requested:
            # Make-or-break hole: negotiate scoped re-investigation with @research
            # before escalating to Risk.
            _gap_requested_rooms.add(thread_id)
            vendor = vendor_from_messages(contents) or "the vendor"
            request = build_research_request(vendor, "gap", directives)
            send_content = (
                report.content
                + "\n\nMaking the critical gaps concrete — requesting scoped "
                "re-investigation before final verdict.\n\n"
                + serialize(request)
            )
            mentions = [reply_handle("research")]
            logger.info(
                f"[Gap] INSUFFICIENT -> research_request {request.request_id} "
                f"({len(directives)} directives) for room {thread_id[:8]}"
            )
        else:
            send_content = report.content + "\n\nRisk, please make your final verdict."
            mentions = [reply_handle("risk")]

        result = await band_send.ainvoke({"content": send_content, "mentions": mentions})
        logger.info(f"[Gap] band_send result: {result}")

        return {"messages": [report]}

    builder = StateGraph(GapState)
    builder.add_node("gap", gap_node)
    builder.set_entry_point("gap")
    builder.add_edge("gap", END)
    return builder.compile(checkpointer=InMemorySaver())


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(graph_factory=graph_factory)

    agent_id, api_key = load_agent_config("gap")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Gap agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
