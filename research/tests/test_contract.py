import unittest

from research.contract import (
    VERSION,
    MessageType,
    Status,
    ResearchRequest,
    ResearchResponse,
    serialize,
    parse,
)
from research.models import SourceTier, Evidence, Failure


def make_evidence():
    return Evidence(
        id="e1",
        snippet="Veradigm holds a SOC 2 Type II report.",
        source_url="https://example.com/soc2",
        source_name="Example",
        provider="tavily",
        source_tier=SourceTier.VENDOR_SELF,
        retrieved_at="2026-06-19T00:00:00Z",
        query="Veradigm SOC 2",
        relevance=0.7,
        raw="raw page text",
    )


class TestRequestRoundTrip(unittest.TestCase):
    def test_request_round_trips_with_correlation_id(self):
        req = ResearchRequest(
            request_id="req-123",
            requested_by="risk",
            vendor="Veradigm",
            summary="Risk requests scoped re-investigation of 2 gaps for Veradigm",
            goals=("verify regulatory standing",),
            gap_directives=("confirm ONC CHPL listing", "find SOC 2 evidence"),
            priority="high",
        )
        parsed = parse(serialize(req))
        self.assertEqual(parsed, req)
        self.assertEqual(parsed.request_id, "req-123")
        self.assertEqual(parsed.version, VERSION)
        self.assertEqual(parsed.type, MessageType.REQUEST.value)


class TestResponseRoundTrip(unittest.TestCase):
    def test_response_round_trips_with_evidence_and_status(self):
        resp = ResearchResponse(
            request_id="req-123",
            responded_by="scout",
            vendor="Veradigm",
            status=Status.COMPLETE,
            summary="Scout found 1 evidence item for Veradigm",
            evidence=(make_evidence(),),
            failures=(Failure(provider="ddg", query="Veradigm news", error="rate limited"),),
        )
        parsed = parse(serialize(resp))
        self.assertEqual(parsed, resp)
        self.assertEqual(parsed.request_id, resp.request_id)
        self.assertEqual(parsed.status, Status.COMPLETE)
        self.assertEqual(parsed.evidence[0].source_tier, SourceTier.VENDOR_SELF)

    def test_each_status_value_round_trips(self):
        for status in Status:
            resp = ResearchResponse(
                request_id="r",
                responded_by="scout",
                vendor="V",
                status=status,
                summary="s",
            )
            self.assertEqual(parse(serialize(resp)).status, status)


class TestSerializedFormat(unittest.TestCase):
    def test_summary_is_first_human_readable_line(self):
        req = ResearchRequest(
            request_id="r",
            requested_by="risk",
            vendor="V",
            summary="HUMAN SUMMARY LINE",
        )
        text = serialize(req)
        self.assertEqual(text.splitlines()[0], "HUMAN SUMMARY LINE")
        self.assertIn("```json", text)


class TestParseNonContract(unittest.TestCase):
    def test_parse_returns_none_for_plain_prose(self):
        self.assertIsNone(parse("Please run a full vendor assessment on Veradigm"))

    def test_parse_returns_none_for_malformed_json_block(self):
        self.assertIsNone(parse("summary\n\n```json\n{not valid json}\n```"))


if __name__ == "__main__":
    unittest.main()
