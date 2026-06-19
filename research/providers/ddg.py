"""DuckDuckGo web search provider (best-effort; may be rate-limited).

Adds free breadth. Failures land in the engine's ``failures`` list rather than
aborting the run, per the anti-fabrication policy.
"""
from __future__ import annotations

import asyncio

from research.models import SourceTier
from research.providers.base import RawResult, SearchProvider

DEFAULT_MAX_RESULTS = 5


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"
    tier = SourceTier.PRESS

    def __init__(self, max_results: int = DEFAULT_MAX_RESULTS):
        self.max_results = max_results

    def _search_sync(self, query: str) -> list[RawResult]:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=self.max_results):
                results.append(RawResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    content=r.get("body", ""),
                ))
        return results

    async def search(self, query: str, **opts) -> list[RawResult]:
        return await asyncio.to_thread(self._search_sync, query)
