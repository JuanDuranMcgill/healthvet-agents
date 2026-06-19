import unittest

from research.engine import ResearchEngine
from research.planner import QueryPlanner
from research.providers.base import SearchProvider, RawResult
from research.models import SourceTier


async def _raising_expander(vendor, goals, gap_directives):
    raise RuntimeError("no LLM in tests")


def deterministic_planner():
    # Force the templated path so query sets are predictable in tests.
    return QueryPlanner(expander=_raising_expander)


class FakeProvider(SearchProvider):
    def __init__(self, results, name="fake", tier=SourceTier.PRESS):
        self.name = name
        self.tier = tier
        self._results = results

    async def search(self, query, **opts):
        return list(self._results)


class RaisingProvider(SearchProvider):
    name = "boom"
    tier = SourceTier.PRESS

    async def search(self, query, **opts):
        raise RuntimeError("provider down")


def result(url, relevance=0.5, title="t"):
    return RawResult(title=title, url=url, content="content", relevance=relevance)


class TestEngineDedup(unittest.IsolatedAsyncioTestCase):
    async def test_dedup_collapses_same_url_across_providers(self):
        same = [result("https://example.com/page")]
        engine = ResearchEngine(
            providers=[
                FakeProvider(same, name="a", tier=SourceTier.PRESS),
                FakeProvider(same, name="b", tier=SourceTier.REGULATORY),
            ],
            planner=deterministic_planner(),
            cache=None,
        )
        bundle = await engine.gather("Veradigm", goals=[])
        urls = [e.source_url for e in bundle.evidence]
        self.assertEqual(len(urls), 1)
        # Higher tier wins the dedup.
        self.assertEqual(bundle.evidence[0].source_tier, SourceTier.REGULATORY)


class TestEngineRanking(unittest.IsolatedAsyncioTestCase):
    async def test_ranking_is_tier_first_then_relevance(self):
        engine = ResearchEngine(
            providers=[
                FakeProvider([result("https://reg.gov/x", relevance=0.1)],
                             name="reg", tier=SourceTier.REGULATORY),
                FakeProvider([result("https://blog.com/y", relevance=0.99)],
                             name="press", tier=SourceTier.PRESS),
            ],
            planner=deterministic_planner(),
            cache=None,
        )
        bundle = await engine.gather("Veradigm", goals=[])
        self.assertEqual(bundle.evidence[0].source_url, "https://reg.gov/x")


class TestEngineResilience(unittest.IsolatedAsyncioTestCase):
    async def test_one_provider_raising_does_not_abort_and_is_recorded(self):
        engine = ResearchEngine(
            providers=[
                FakeProvider([result("https://good.com/z")], name="good"),
                RaisingProvider(),
            ],
            planner=deterministic_planner(),
            cache=None,
            retries=0,
        )
        bundle = await engine.gather("Veradigm", goals=[])
        self.assertTrue(any(e.source_url == "https://good.com/z" for e in bundle.evidence))
        self.assertTrue(any(f.provider == "boom" for f in bundle.failures))


class TestEngineScopedRetrieval(unittest.IsolatedAsyncioTestCase):
    async def test_gap_directives_run_scoped_queries_only(self):
        engine = ResearchEngine(
            providers=[FakeProvider([result("https://chpl.gov/listing")], name="reg")],
            planner=deterministic_planner(),
            cache=None,
        )
        bundle = await engine.gather(
            "Veradigm", goals=[], gap_directives=["confirm ONC CHPL listing"]
        )
        self.assertEqual(len(bundle.queries_run), 1)
        self.assertNotIn(
            "Veradigm healthcare customer references case studies", bundle.queries_run
        )


class TestEngineBundleStates(unittest.IsolatedAsyncioTestCase):
    async def test_empty_results_yield_not_found_not_failure(self):
        engine = ResearchEngine(
            providers=[FakeProvider([], name="empty")],
            planner=deterministic_planner(),
            cache=None,
        )
        bundle = await engine.gather("Veradigm", goals=[])
        a_query = bundle.queries_run[0]
        self.assertEqual(bundle.state_for(a_query), "not_found")
        self.assertEqual(bundle.failures, ())


if __name__ == "__main__":
    unittest.main()
