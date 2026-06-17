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

First, check the conversation for a prior "VETO #1". If one exists, this is your SECOND review — you MUST reach a final verdict now (APPROVE, ESCALATE, or REJECT). No further vetoes allowed.

Based on all findings in the conversation, write your verdict:

**RISK VERDICT: [Vendor Name]**
Evidence Quality Score: [1-10]
Compliance Standing: [COMPLIANT / PARTIAL / NON-COMPLIANT / UNKNOWN]

Key Risks:
- [top 3-5 risks]

Final Verdict: APPROVE / ESCALATE / REJECT
Rationale: [2-3 sentences]

VETO RULE: If this is your FIRST review and the evidence is critically insufficient (Gap verdict is INSUFFICIENT, or there are unresolved critical contradictions), set Final Verdict to REJECT and add:

VETO DIRECTIVES:
- [specific search query or document request #1]
- [specific search query or document request #2]
- [specific search query or document request #3]

These directives must be targeted and actionable — name the exact missing certifications, breach details, or legal questions Scout should resolve.

If evidence is sufficient to decide (APPROVE or ESCALATE), do NOT include VETO DIRECTIVES.

Write the report ONLY. No preamble."""


class RiskState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def graph_factory(band_tools):
    band_send = next(t for t in band_tools if "send_message" in t.name)
    llm = make_llm()

    async def risk_node(state: RiskState) -> dict:
        messages = state.get("messages", [])
        logger.info(f"[Risk] received {len(messages)} messages")

        # Check if this is a second review (prior veto exists)
        history_text = " ".join(
            m.content for m in messages if hasattr(m, "content") and m.content
        )
        is_second_review = "VETO #1" in history_text
        logger.info(f"[Risk] second review: {is_second_review}")

        verdict = await llm.ainvoke(
            [SystemMessage(content=VERDICT_PROMPT)] + list(messages)
        )
        content = verdict.content
        logger.info(f"[Risk] verdict: {content[:300]}")

        # Route: REJECT + VETO DIRECTIVES → back to Scout; anything else → Synthesis
        is_veto = (
            not is_second_review
            and "FINAL VERDICT: REJECT" in content.upper()
            and "VETO DIRECTIVES:" in content
        )

        if is_veto:
            mentions = ["@handmorin/scout"]
            send_content = f"🚨 VETO #1 — Re-investigation Required\n\n{content}\n\nScout, please re-run your research addressing each VETO DIRECTIVE above."
            logger.info("[Risk] VETO — routing back to Scout")
        else:
            mentions = ["@handmorin/synthesis"]
            send_content = content
            logger.info("[Risk] routing to Synthesis")

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
