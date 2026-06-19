import unittest

from research.agent_io import extract_vendor, default_status, build_response
from research.contract import Status
from research.models import Evidence, EvidenceBundle, Failure, SourceTier


def evidence(url="https://x.com/a"):
    return Evidence(
        id="e", snippet="s", source_url=url, source_name="X", provider="tavily",
        source_tier=SourceTier.PRESS, retrieved_at="2026-06-19T00:00:00Z",
        query="q", relevance=0.5, raw="r",
    )


def failure():
    return Failure(provider="ddg", query="q", error="rate limited")


class TestExtractVendor(unittest.TestCase):
    def test_plain_trigger(self):
        self.assertEqual(
            extract_vendor("Please run a full vendor assessment on Veradigm"),
            "Veradigm",
        )

    def test_trigger_with_handle_and_trailing_period(self):
        self.assertEqual(
            extract_vendor("@me/scout Please run a full vendor assessment on Epic Systems."),
            "Epic Systems",
        )

    def test_trigger_with_following_context(self):
        self.assertEqual(
            extract_vendor("run a vendor assessment on Cerner. Hospital context: rural"),
            "Cerner",
        )


class TestDefaultStatus(unittest.TestCase):
    def test_evidence_only_is_complete(self):
        self.assertEqual(default_status(EvidenceBundle(evidence=(evidence(),))), Status.COMPLETE)

    def test_evidence_with_failures_is_partial(self):
        bundle = EvidenceBundle(evidence=(evidence(),), failures=(failure(),))
        self.assertEqual(default_status(bundle), Status.PARTIAL)

    def test_failures_only_is_failed(self):
        self.assertEqual(default_status(EvidenceBundle(failures=(failure(),))), Status.FAILED)

    def test_empty_searched_is_complete(self):
        # Searched, found nothing, nothing errored -> an honest COMPLETE.
        self.assertEqual(default_status(EvidenceBundle(queries_run=("q",))), Status.COMPLETE)


class TestBuildResponse(unittest.TestCase):
    def test_carries_bundle_and_correlation(self):
        bundle = EvidenceBundle(evidence=(evidence(),), failures=(failure(),))
        resp = build_response("Veradigm", "req-9", "scout", bundle)
        self.assertEqual(resp.request_id, "req-9")
        self.assertEqual(resp.responded_by, "scout")
        self.assertEqual(resp.vendor, "Veradigm")
        self.assertEqual(resp.evidence, bundle.evidence)
        self.assertEqual(resp.failures, bundle.failures)
        self.assertEqual(resp.status, Status.PARTIAL)
        self.assertIn("Veradigm", resp.summary)

    def test_explicit_status_override(self):
        bundle = EvidenceBundle(evidence=(evidence(),))
        resp = build_response("V", "r", "research", bundle, status=Status.NEEDS_REINVESTIGATION)
        self.assertEqual(resp.status, Status.NEEDS_REINVESTIGATION)


if __name__ == "__main__":
    unittest.main()
