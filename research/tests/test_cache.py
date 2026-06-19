import os
import tempfile
import unittest

from research.cache import QueryCache


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


class TestQueryCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "cache.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_set_then_get_returns_value(self):
        cache = QueryCache(path=self.path, ttl_seconds=100)
        cache.set("veradigm soc 2", "tavily", [{"url": "u"}])
        self.assertEqual(cache.get("veradigm soc 2", "tavily"), [{"url": "u"}])

    def test_get_returns_none_on_miss(self):
        cache = QueryCache(path=self.path, ttl_seconds=100)
        self.assertIsNone(cache.get("nope", "tavily"))

    def test_same_query_different_provider_is_separate_key(self):
        cache = QueryCache(path=self.path, ttl_seconds=100)
        cache.set("q", "tavily", ["a"])
        self.assertIsNone(cache.get("q", "exa"))

    def test_expired_entry_returns_none(self):
        clock = FakeClock(0.0)
        cache = QueryCache(path=self.path, ttl_seconds=10, now=clock)
        cache.set("q", "tavily", ["a"])
        clock.t = 11.0
        self.assertIsNone(cache.get("q", "tavily"))

    def test_disabled_cache_is_noop(self):
        cache = QueryCache(path=self.path, ttl_seconds=100, enabled=False)
        cache.set("q", "tavily", ["a"])
        self.assertIsNone(cache.get("q", "tavily"))

    def test_disabled_via_env_var(self):
        os.environ["RESEARCH_CACHE_DISABLED"] = "1"
        try:
            cache = QueryCache(path=self.path, ttl_seconds=100)
            cache.set("q", "tavily", ["a"])
            self.assertIsNone(cache.get("q", "tavily"))
        finally:
            del os.environ["RESEARCH_CACHE_DISABLED"]


if __name__ == "__main__":
    unittest.main()
