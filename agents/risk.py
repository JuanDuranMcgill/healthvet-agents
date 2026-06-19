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
    directives_from_breakdown,
    build_research_request,
    reply_handle,
)

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

        # Gather all text from messages
        message_contents = [m.content for m in messages if hasattr(m, "content")]
        full_text = "\n".join(message_contents)
        vendor = vendor_from_messages(message_contents) or "the vendor"

        import os
        from questionnaire.profile import HospitalProfile
        from questionnaire.extractor import extract_findings
        from questionnaire.scorer import score_vendor
        from questionnaire.gap import resolve_gaps
        import json
        
        # We will use a default test profile if none is provided, or load one
        # For this integration, we'll assume the slug is in env or default
        profile_slug = os.environ.get("HOSPITAL_PROFILE", "test-hospital")
        profile = HospitalProfile(profile_slug).load()
        if not profile.categories:
            # Fallback mock for testing if no profile generated yet
            profile.categories = {
                "patient_safety": {"weight": 0.2},
                "security_breach": {"weight": 0.2},
                "regulatory_compliance": {"weight": 0.2},
                "cost": {"weight": 0.2},
                "deployment_speed": {"weight": 0.2}
            }
            
        logger.info(f"[Risk] Extracting findings via LLM...")
        extracted = extract_findings(full_text)
        
        if profile.settings.get("gap_resolution_mode", "ask") == "auto":
            resolve_gaps(extracted.get("uncovered", []), profile)
            
        res = score_vendor(profile, extracted)
        
        fit = res["fit"]
        verdict = res["verdict"]
        breakdown_str = json.dumps(res["breakdown"], indent=2)
        dbs = res["triggered_deal_breakers"]
        
        # Build the final content
        content = f"**RISK VERDICT — QUANTITATIVE SCORECARD**\n"
        content += f"Fit Score: {fit}/100\n"
        content += f"Verdict: {verdict}\n\n"
        if dbs:
            content += f"Triggered Deal Breakers: {[db.get('factor') for db in dbs]}\n\n"
        content += f"Category Breakdown:\n```json\n{breakdown_str}\n```\n"

        # VETO Logic (still applicable if not vetoed yet and verdict is REJECT)
        is_veto = (
            not has_vetoed
            and verdict == "REJECT"
            and any(b.get("score", 10) < 5 for b in res["breakdown"]) # simple heuristic for gaps
        )

        if is_veto:
            _vetoed_rooms.add(thread_id)
            directives = directives_from_breakdown(res["breakdown"]) or [
                "Find concrete evidence for categories scoring below 5/10"
            ]
            request = build_research_request(vendor, "risk", directives)
            mentions = [reply_handle("research")]
            send_content = (
                f"🚨 VETO — structured re-investigation requested\n\n{content}\n\n"
                + serialize(request)
            )
            logger.info(
                f"[Risk] VETO -> research_request {request.request_id} "
                f"({len(directives)} directives) for room {thread_id[:8]}"
            )
        else:
            mentions = ["@leejongmin1092/synthesis"]
            send_content = content
            logger.info(f"[Risk] final decision for room {thread_id[:8]}")

        # Update the state with our verdict message
        from langchain_core.messages import AIMessage
        verdict_msg = AIMessage(content=content)

        result = await band_send.ainvoke({
            "content": send_content,
            "mentions": mentions,
        })
        logger.info(f"[Risk] band_send result: {result}")

        return {"messages": [verdict_msg]}

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
