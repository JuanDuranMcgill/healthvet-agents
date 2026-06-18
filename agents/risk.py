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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("risk")

# Module-level: tracks which rooms have already received a veto.
# Survives concurrent triggers within the same process run.
_vetoed_rooms: set = set()

VERDICT_PROMPT = """You are Risk, the final decision authority in a healthcare vendor vetting pipeline.

Based on all findings in the conversation, write your verdict:

**RISK VERDICT: [Vendor Name]**
Evidence Quality Score: [1-10]
Compliance Standing: [COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN]

Key Risks:
- [top 3-5 risks]

Final Verdict: APPROVE / ESCALATE / REJECT
Rationale: [2-3 sentences]

VETO RULE: If Gap's overall verdict is INSUFFICIENT and there are 2+ critical gaps, set Final Verdict to REJECT and add:

VETO DIRECTIVES:
- [specific targeted search #1]
- [specific targeted search #2]
- [specific targeted search #3]

If evidence is sufficient to decide (APPROVE or ESCALATE), do NOT include VETO DIRECTIVES."""

SECOND_REVIEW_PROMPT = """You are Risk, the final decision authority in a healthcare vendor vetting pipeline.

This is your SECOND and FINAL review after a re-investigation. Make a definitive verdict — APPROVE, ESCALATE, or REJECT. No further vetoes.

Based on ALL findings in the conversation (original research + re-investigation), write your final verdict:

**RISK VERDICT: [Vendor Name] — FINAL**
Evidence Quality Score: [1-10]
Compliance Standing: [COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN]

Key Risks:
- [top 3-5 risks]

Final Verdict: APPROVE / ESCALATE / REJECT
Rationale: [2-3 sentences]

Write the report ONLY. No preamble. Do NOT include VETO DIRECTIVES."""


class RiskState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def graph_factory(band_tools):
    band_send = next(t for t in band_tools if "send_message" in t.name)
    llm = make_llm()

    async def risk_node(state: RiskState, config: RunnableConfig) -> dict:
        messages = state.get("messages", [])
        thread_id = config.get("configurable", {}).get("thread_id", "unknown")
        has_vetoed = thread_id in _vetoed_rooms
        logger.info(f"[Risk] room={thread_id[:8]}, messages={len(messages)}, has_vetoed={has_vetoed}")

        prompt = SECOND_REVIEW_PROMPT if has_vetoed else VERDICT_PROMPT

        verdict = await llm.ainvoke(
            [SystemMessage(content=prompt)] + list(messages)
        )
        content = verdict.content
        logger.info(f"[Risk] verdict: {content[:300]}")

        is_veto = (
            not has_vetoed
            and "FINAL VERDICT: REJECT" in content.upper()
            and "VETO DIRECTIVES:" in content
        )

        if is_veto:
            _vetoed_rooms.add(thread_id)
            mentions = ["@handmorin/scout"]
            send_content = f"🚨 VETO #1 — Re-investigation Required\n\n{content}\n\nScout, please re-run your research addressing each VETO DIRECTIVE above."
            logger.info(f"[Risk] VETO issued for room {thread_id[:8]}")
        else:
            mentions = ["@handmorin/synthesis"]
            send_content = content
            logger.info(f"[Risk] final decision for room {thread_id[:8]}")

        result = await band_send.ainvoke({
            "content": send_content,
            "mentions": mentions,
        })
        logger.info(f"[Risk] band_send result: {result}")

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
