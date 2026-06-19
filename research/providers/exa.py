"""Exa neural/semantic search provider."""
from __future__ import annotations

import asyncio
import os

from research.models import SourceTier
from research.providers.base import RawResult, SearchProvider

DEFAULT_NUM_RESULTS = 5


class ExaProvider(SearchProvider):
    name = "exa"
    tier = SourceTier.PRESS

    def __init__(self, num_results: int = DEFAULT_NUM_RESULTS):
        self.num_results = num_results

    def _search_sync(self, query: str) -> list[RawResult]:
        from exa_py import Exa
        from exa_py.api import ContentsOptions

        exa = Exa(api_key=os.environ["EXA_API_KEY"])
        data = exa.search(
            query,
            num_results=self.num_results,
            type="neural",
            contents=ContentsOptions(text=True),
        )
        results = []
        for r in data.results:
            results.append(RawResult(
                title=getattr(r, "title", "") or "",
                url=getattr(r, "url", "") or "",
                content=getattr(r, "text", "") or "",
                published_date=getattr(r, "published_date", None),
                relevance=float(getattr(r, "score", 0.5) or 0.5),
            ))
        return results

    async def search(self, query: str, **opts) -> list[RawResult]:
        return await asyncio.to_thread(self._search_sync, query)
