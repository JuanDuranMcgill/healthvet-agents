import unittest

from research.agent_io import (
    extract_vendor,
    default_status,
    build_response,
    resolution_status,
    reply_handle,
    run_research_request,
)
from research.contract import Status, ResearchRequest
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


def scoped_bundle(vendor, directive, found=True):
    query = f"{vendor} {directive}"
    ev = (evidence(),) if found else ()
    return EvidenceBundle(evidence=tuple(
        e.__class__(**{**e.__dict__, "query": query}) for e in ev
    ), queries_run=(query,))


class FakeEngine:
    def __init__(self, bundle):
        self._bundle = bundle
        self.calls = []

    async def gather(self, vendor, goals=None, gap_directives=None, hospital_context=None):
        self.calls.append((vendor, tuple(goals or ()), tuple(gap_directives or ())))
        return self._bundle


class TestReplyHandle(unittest.TestCase):
    def test_builds_handle_for_role(self):
        self.assertEqual(reply_handle("risk"), "@leejongmin1092/risk")


class TestResolutionStatus(unittest.TestCase):
    def test_no_directives_uses_default(self):
        req = ResearchRequest(request_id="r", requested_by="risk", vendor="V", summary="s")
        self.assertEqual(resolution_status(req, EvidenceBundle(evidence=(evidence(),))), Status.COMPLETE)

    def test_all_directives_found_is_complete(self):
        req = ResearchRequest(request_id="r", requested_by="risk", vendor="Veradigm",
                              summary="s", gap_directives=("confirm CHPL",))
        bundle = scoped_bundle("Veradigm", "confirm CHPL", found=True)
        self.assertEqual(resolution_status(req, bundle), Status.COMPLETE)

    def test_unresolved_directive_needs_reinvestigation(self):
        req = ResearchRequest(request_id="r", requested_by="risk", vendor="Veradigm",
                              summary="s", gap_directives=("confirm CHPL",))
        bundle = scoped_bundle("Veradigm", "confirm CHPL", found=False)
        self.assertEqual(resolution_status(req, bundle), Status.NEEDS_REINVESTIGATION)


class TestRunResearchRequest(unittest.IsolatedAsyncioTestCase):
    async def test_runs_scoped_and_returns_correlated_response(self):
        req = ResearchRequest(request_id="req-7", requested_by="risk", vendor="Veradigm",
                              summary="s", gap_directives=("confirm CHPL",))
        engine = FakeEngine(scoped_bundle("Veradigm", "confirm CHPL", found=True))
        resp = await run_research_request(req, engine)
        self.assertEqual(resp.request_id, "req-7")
        self.assertEqual(resp.responded_by, "research")
        self.assertEqual(resp.status, Status.COMPLETE)
        # Engine was called with the gap directives (scoped retrieval).
        self.assertEqual(engine.calls[0][2], ("confirm CHPL",))


if __name__ == "__main__":
    unittest.main()
