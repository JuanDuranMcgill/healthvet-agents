import unittest
from datetime import datetime, timezone

from band.testing.fake_tools import FakeAgentTools
from band.core.types import PlatformMessage

from agents.research import ResearchAdapter
from research.contract import (
    ResearchRequest,
    ResearchResponse,
    Status,
    serialize,
    parse,
)
from research.models import Evidence, EvidenceBundle, SourceTier


def make_msg(content: str) -> PlatformMessage:
    return PlatformMessage(
        id="m1",
        room_id="room-1",
        content=content,
        sender_id="risk-id",
        sender_type="agent",
        sender_name="Risk",
        message_type="text",
        metadata=None,
        created_at=datetime.now(timezone.utc),
    )


def scoped_bundle(vendor, directive):
    query = f"{vendor} {directive}"
    ev = Evidence(
        id="e", snippet="found it", source_url="https://chpl.gov/x", source_name="CHPL",
        provider="openfda", source_tier=SourceTier.REGULATORY,
        retrieved_at="2026-06-19T00:00:00Z", query=query, relevance=0.9, raw="raw",
    )
    return EvidenceBundle(evidence=(ev,), queries_run=(query,))


class FakeEngine:
    def __init__(self, bundle):
        self._bundle = bundle

    async def gather(self, vendor, goals=None, gap_directives=None, hospital_context=None):
        return self._bundle


class TestResearchWorker(unittest.IsolatedAsyncioTestCase):
    async def _handle(self, content, engine):
        adapter = ResearchAdapter(engine=engine)
        tools = FakeAgentTools()
        await adapter.on_message(
            make_msg(content), tools, history=[], participants_msg=None,
            contacts_msg=None, is_session_bootstrap=False, room_id="room-1",
        )
        return tools

    async def test_replies_with_correlated_response_to_requester(self):
        req = ResearchRequest(
            request_id="req-42", requested_by="risk", vendor="Veradigm",
            summary="Risk needs CHPL confirmed", gap_directives=("confirm CHPL listing",),
        )
        engine = FakeEngine(scoped_bundle("Veradigm", "confirm CHPL listing"))
        tools = await self._handle(serialize(req), engine)

        self.assertEqual(len(tools.messages_sent), 1)
        sent = tools.messages_sent[0]
        self.assertEqual(sent["mentions"], ["@leejongmin1092/risk"])
        parsed = parse(sent["content"])
        self.assertIsInstance(parsed, ResearchResponse)
        self.assertEqual(parsed.request_id, "req-42")
        self.assertEqual(parsed.responded_by, "research")
        self.assertEqual(parsed.status, Status.COMPLETE)

    async def test_ignores_non_contract_message(self):
        engine = FakeEngine(scoped_bundle("Veradigm", "x"))
        tools = await self._handle("Please run a full vendor assessment on Veradigm", engine)
        self.assertEqual(len(tools.messages_sent), 0)


if __name__ == "__main__":
    unittest.main()
