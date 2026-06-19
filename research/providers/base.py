"""Uniform async interface every search provider implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from research.models import SourceTier


@dataclass(frozen=True)
class RawResult:
    """A single result as returned by a provider, before normalization."""

    title: str
    url: str
    content: str
    published_date: str | None = None
    relevance: float = 0.5


class SearchProvider(ABC):
    """A search backend. Subclasses set ``name`` and ``tier`` and implement ``search``.

    ``tier`` is the trust level for results from this provider so ranking can put
    regulatory sources above vendor marketing.
    """

    name: str = "provider"
    tier: SourceTier = SourceTier.PRESS

    @abstractmethod
    async def search(self, query: str, **opts) -> list[RawResult]:
        ...
