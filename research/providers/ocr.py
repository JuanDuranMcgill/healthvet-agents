"""HHS OCR breach lookup.

The HHS OCR "breach portal" has no stable official JSON API, so this generalizes
the existing approach: a Tavily search constrained to authoritative breach-record
domains. Tier is REGULATORY because the underlying sources are government /
official breach records.
"""
from __future__ import annotations

import asyncio
import os

from research.models import SourceTier
from research.providers.base import RawResult, SearchProvider

BREACH_DOMAINS = [
    "hhs.gov",
    "ocrportal.hhs.gov",
    "hipaajournal.com",
    "healthitsecurity.com",
    "databreaches.net",
]
DEFAULT_MAX_RESULTS = 5


class OcrBreachProvider(SearchProvider):
    name = "ocr_breach"
    tier = SourceTier.REGULATORY

    def __init__(self, max_results: int = DEFAULT_MAX_RESULTS):
        self.max_results = max_results

    def _search_sync(self, vendor: str) -> list[RawResult]:
        from tavily import TavilyClient

        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        data = client.search(
            f"{vendor} HIPAA data breach OCR notification",
            search_depth="advanced",
            max_results=self.max_results,
            include_domains=BREACH_DOMAINS,
        )
        results = []
        for r in data.get("results", []):
            results.append(RawResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                relevance=float(r.get("score", 0.6) or 0.6),
            ))
        return results

    async def search(self, query: str, **opts) -> list[RawResult]:
        vendor = opts.get("vendor") or query
        return await asyncio.to_thread(self._search_sync, vendor)
