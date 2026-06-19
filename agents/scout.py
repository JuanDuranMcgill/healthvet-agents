"""Scout: initial broad web sweep.

Refactored to call the shared ResearchEngine (web providers) and emit a
structured `research_response` into the Band room instead of loose prose. Uses
the deterministic graph_factory pattern so the handoff always fires regardless
of model formatting. Regulatory tiers are owned by Compliance (see A3).
"""
import asyncio
import logging
import operator
import uuid
from typing import TypedDict, Annotated

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import BaseMessage, AIMessage
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from research.engine import ResearchEngine
from research.providers.factory import web_providers
from research.agent_io import extract_vendor, build_response
from research.contract import serialize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scout")

FORENSICS = "@leejongmin1092/forensics"


class ScoutState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def graph_factory(band_tools):
    band_send = next(t for t in band_tools if "send_message" in t.name)
    engine = ResearchEngine(providers=web_providers())

    async def scout_node(state: ScoutState) -> dict:
        messages = state.get("messages", [])
        trigger = next(
            (m.content for m in reversed(messages) if getattr(m, "content", "").strip()),
            "",
        )
        vendor = extract_vendor(trigger)
        request_id = uuid.uuid4().hex[:12]
        logger.info("[Scout] broad sweep for %r (request_id=%s)", vendor, request_id)

        bundle = await engine.gather(vendor, goals=[])
        logger.info(
            "[Scout] %d evidence, %d failures", len(bundle.evidence), len(bundle.failures)
        )

        response = build_response(vendor, request_id, "scout", bundle)
        content = serialize(response) + "\n\nForensics, please analyze this evidence."

        await band_send.ainvoke({"content": content, "mentions": [FORENSICS]})
        return {"messages": [AIMessage(content=response.summary)]}

    builder = StateGraph(ScoutState)
    builder.add_node("scout", scout_node)
    builder.set_entry_point("scout")
    builder.add_edge("scout", END)
    return builder.compile(checkpointer=InMemorySaver())


async def main():
    load_dotenv()
    adapter = LangGraphAdapter(graph_factory=graph_factory)
    agent_id, api_key = load_agent_config("scout")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)
    print("Scout agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
