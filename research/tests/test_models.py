import unittest
from dataclasses import FrozenInstanceError

from research.models import SourceTier, Evidence, Failure, EvidenceBundle


def make_evidence(query="soc 2", tier=SourceTier.PRESS, relevance=0.5, ev_id="e1"):
    return Evidence(
        id=ev_id,
        snippet="snippet",
        source_url="https://example.com/a",
        source_name="Example",
        provider="tavily",
        source_tier=tier,
        retrieved_at="2026-06-19T00:00:00Z",
        query=query,
        relevance=relevance,
        raw="raw text",
    )


class TestSourceTier(unittest.TestCase):
    def test_regulatory_outranks_all_others(self):
        self.assertGreater(SourceTier.REGULATORY, SourceTier.VERIFIED_CUSTOMER)
        self.assertGreater(SourceTier.VERIFIED_CUSTOMER, SourceTier.VENDOR_SELF)
        self.assertGreater(SourceTier.VENDOR_SELF, SourceTier.PRESS)


class TestEvidence(unittest.TestCase):
    def test_is_immutable(self):
        ev = make_evidence()
        with self.assertRaises(FrozenInstanceError):
            ev.relevance = 0.9


class TestEvidenceBundle(unittest.TestCase):
    def test_state_found_when_query_returned_evidence(self):
        ev = make_evidence(query="soc 2")
        bundle = EvidenceBundle(evidence=(ev,), queries_run=("soc 2",))
        self.assertEqual(bundle.state_for("soc 2"), "found")

    def test_state_not_found_when_searched_but_empty(self):
        bundle = EvidenceBundle(evidence=(), queries_run=("fda clearance",))
        self.assertEqual(bundle.state_for("fda clearance"), "not_found")

    def test_state_not_searched_when_query_never_issued(self):
        bundle = EvidenceBundle(evidence=(), queries_run=("soc 2",))
        self.assertEqual(bundle.state_for("litigation"), "not_searched")

    def test_state_failed_takes_precedence_over_not_found(self):
        failure = Failure(provider="openfda", query="fda clearance", error="timeout")
        bundle = EvidenceBundle(
            evidence=(),
            queries_run=("fda clearance",),
            failures=(failure,),
        )
        self.assertEqual(bundle.state_for("fda clearance"), "failed")


if __name__ == "__main__":
    unittest.main()
