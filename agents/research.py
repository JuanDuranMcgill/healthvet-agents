"""Research worker: a standalone, non-LangGraph Band participant.

This agent is deliberately built on Band's SimpleAdapter (a plain message
handler) rather than the LangGraph adapter the other agents use. It listens for
structured `research_request` messages, runs scoped retrieval through the shared
ResearchEngine, and replies with a correlated `research_response`. This is the
second coordination pattern in the system and the cross-framework collaborator.
"""
import asyncio
import logging

from dotenv import load_dotenv
from band import Agent
from band.config import load_agent_config
from band.core.simple_adapter import SimpleAdapter

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from research.engine import ResearchEngine
from research.providers.factory import default_providers
from research.contract import parse, serialize, ResearchRequest
from research.agent_io import run_research_request, reply_handle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research")


class ResearchAdapter(SimpleAdapter):
    """Handles research_request messages and replies with research_response."""

    def __init__(self, engine: ResearchEngine | None = None):
        super().__init__()
        self.engine = engine or ResearchEngine(providers=default_providers())

    async def on_message(
        self,
        msg,
        tools,
        history,
        participants_msg,
        contacts_msg,
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        request = parse(getattr(msg, "content", "") or "")
        if not isinstance(request, ResearchRequest):
            return  # Not a contract request — ignore (e.g. prose, or responses).

        logger.info(
            "[Research] request %s for %r (%d gap directives)",
            request.request_id, request.vendor, len(request.gap_directives),
        )
        response = await run_research_request(request, self.engine)
        logger.info("[Research] -> status=%s, %d evidence", response.status.value, len(response.evidence))

        content = (
            serialize(response)
            + f"\n\n{request.requested_by.title()}, here is the correlated evidence "
            f"for request {request.request_id}."
        )
        await tools.send_message(content=content, mentions=[reply_handle(request.requested_by)])


async def main():
    load_dotenv()
    adapter = ResearchAdapter()
    agent_id, api_key = load_agent_config("research")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)
    print("Research worker running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
