"""ResearchEngine: plan -> concurrent fan-out -> normalize -> dedup -> rank.

Resilience and anti-fabrication are first-class: providers run concurrently with
``return_exceptions=True`` and a per-provider timeout; one failing provider is
recorded in ``failures`` and never aborts the run; nothing is ever fabricated to
mask a failure.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from research.cache import QueryCache
from research.models import Evidence, EvidenceBundle, Failure
from research.planner import QueryPlanner
from research.providers.base import RawResult, SearchProvider

logger = logging.getLogger("research.engine")

DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 1
SNIPPET_LEN = 500


def _normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def _evidence_id(provider: str, url: str, query: str) -> str:
    digest = hashlib.sha1(f"{provider}|{url}|{query}".encode("utf-8")).hexdigest()
    return digest[:16]


class ResearchEngine:
    def __init__(
        self,
        providers: list[SearchProvider],
        planner: QueryPlanner | None = None,
        cache: QueryCache | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ):
        self.providers = providers
        self.planner = planner or QueryPlanner()
        self.cache = cache
        self.timeout = timeout
        self.retries = retries

    async def gather(
        self,
        vendor: str,
        goals: list[str] | None = None,
        gap_directives: list[str] | None = None,
        hospital_context: str | None = None,
    ) -> EvidenceBundle:
        queries = await self.planner.plan(vendor, goals, gap_directives)

        jobs = [(provider, query) for provider in self.providers for query in queries]
        raw_results = await asyncio.gather(
            *(self._search_one(provider, query, vendor) for provider, query in jobs),
            return_exceptions=True,
        )

        evidence: list[Evidence] = []
        failures: list[Failure] = []
        for (provider, query), outcome in zip(jobs, raw_results):
            if isinstance(outcome, Exception):
                logger.warning("provider %s failed for %r: %s", provider.name, query, outcome)
                failures.append(Failure(provider=provider.name, query=query, error=str(outcome)))
                continue
            for raw in outcome:
                evidence.append(self._to_evidence(provider, query, raw))

        evidence = self._rank(self._dedup(evidence))
        return EvidenceBundle(
            evidence=tuple(evidence),
            queries_run=tuple(queries),
            failures=tuple(failures),
        )

    async def _search_one(self, provider: SearchProvider, query: str, vendor: str) -> list[RawResult]:
        if self.cache is not None:
            cached = self.cache.get(query, provider.name)
            if cached is not None:
                return [RawResult(**item) for item in cached]

        last_exc: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                results = await asyncio.wait_for(
                    provider.search(query, vendor=vendor), timeout=self.timeout
                )
                if self.cache is not None:
                    self.cache.set(query, provider.name, [asdict(r) for r in results])
                return results
            except Exception as exc:  # noqa: BLE001 - surfaced to caller as a Failure
                last_exc = exc
        raise last_exc if last_exc else RuntimeError("unknown search failure")

    def _to_evidence(self, provider: SearchProvider, query: str, raw: RawResult) -> Evidence:
        return Evidence(
            id=_evidence_id(provider.name, raw.url, query),
            snippet=(raw.content or "")[:SNIPPET_LEN],
            source_url=raw.url,
            source_name=raw.title or raw.url,
            provider=provider.name,
            source_tier=provider.tier,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            query=query,
            relevance=raw.relevance,
            raw=raw.content or "",
        )

    @staticmethod
    def _dedup(evidence: list[Evidence]) -> list[Evidence]:
        best: dict[str, Evidence] = {}
        for ev in evidence:
            key = _normalize_url(ev.source_url)
            current = best.get(key)
            if current is None or (ev.source_tier, ev.relevance) > (current.source_tier, current.relevance):
                best[key] = ev
        return list(best.values())

    @staticmethod
    def _rank(evidence: list[Evidence]) -> list[Evidence]:
        return sorted(evidence, key=lambda e: (int(e.source_tier), e.relevance), reverse=True)
