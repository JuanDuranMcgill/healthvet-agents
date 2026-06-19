"""Tavily general web search provider (full content, recency window)."""
from __future__ import annotations

import asyncio
import os

from research.models import SourceTier
from research.providers.base import RawResult, SearchProvider

DEFAULT_MAX_RESULTS = 5


class TavilyProvider(SearchProvider):
    name = "tavily"
    tier = SourceTier.PRESS

    def __init__(self, max_results: int = DEFAULT_MAX_RESULTS, include_domains: list[str] | None = None):
        self.max_results = max_results
        self.include_domains = include_domains

    def _search_sync(self, query: str) -> list[RawResult]:
        from tavily import TavilyClient

        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        kwargs = {"search_depth": "advanced", "max_results": self.max_results,
                  "include_raw_content": True}
        if self.include_domains:
            kwargs["include_domains"] = self.include_domains
        data = client.search(query, **kwargs)
        results = []
        for r in data.get("results", []):
            content = r.get("raw_content") or r.get("content") or ""
            results.append(RawResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=content,
                relevance=float(r.get("score", 0.5) or 0.5),
            ))
        return results

    async def search(self, query: str, **opts) -> list[RawResult]:
        return await asyncio.to_thread(self._search_sync, query)
