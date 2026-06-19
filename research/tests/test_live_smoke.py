"""Live smoke test for the research engine. Skipped unless RUN_LIVE_TESTS=1.

Hits real provider APIs, so it needs network access and the relevant API keys
(TAVILY_API_KEY, EXA_API_KEY). openFDA is keyless.
"""
import os
import unittest

from research.engine import ResearchEngine
from research.providers.factory import default_providers


@unittest.skipUnless(os.getenv("RUN_LIVE_TESTS") == "1", "live tests disabled")
class TestLiveSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_gather_returns_a_bundle(self):
        engine = ResearchEngine(providers=default_providers())
        bundle = await engine.gather(
            "Epic Systems", goals=["customer references", "regulatory standing"]
        )
        # We assert structure, never specific findings: the bundle is the artifact.
        self.assertTrue(bundle.queries_run)
        self.assertIsInstance(bundle.evidence, tuple)
        self.assertIsInstance(bundle.failures, tuple)


if __name__ == "__main__":
    unittest.main()
