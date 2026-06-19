import unittest

from research.planner import QueryPlanner


async def _raising_expander(vendor, goals, gap_directives):
    raise RuntimeError("LLM unavailable")


async def _empty_expander(vendor, goals, gap_directives):
    return []


class TestQueryPlanner(unittest.IsolatedAsyncioTestCase):
    async def test_uses_expander_result_when_available(self):
        async def expander(vendor, goals, gap_directives):
            return ["custom query one", "custom query two"]

        planner = QueryPlanner(expander=expander)
        queries = await planner.plan("Veradigm", goals=["check compliance"])
        self.assertEqual(queries, ["custom query one", "custom query two"])

    async def test_falls_back_to_templated_when_expander_raises(self):
        planner = QueryPlanner(expander=_raising_expander)
        queries = await planner.plan("Veradigm", goals=["check compliance"])
        self.assertTrue(queries)
        self.assertTrue(all("Veradigm" in q for q in queries))

    async def test_falls_back_when_expander_returns_empty(self):
        planner = QueryPlanner(expander=_empty_expander)
        queries = await planner.plan("Veradigm", goals=[])
        self.assertTrue(queries)

    async def test_gap_directives_produce_scoped_queries_only(self):
        planner = QueryPlanner(expander=_raising_expander)
        directives = ["confirm ONC CHPL listing", "find SOC 2 report"]
        queries = await planner.plan("Veradigm", goals=[], gap_directives=directives)
        # Scoped: one query per directive, nothing from the broad sweep.
        self.assertEqual(len(queries), 2)
        self.assertTrue(any("CHPL" in q for q in queries))
        self.assertFalse(any("customer references" in q for q in queries))


if __name__ == "__main__":
    unittest.main()
