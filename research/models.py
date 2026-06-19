"""Structured evidence model for the research engine.

The ``EvidenceBundle`` is the audit-trail artifact: it must keep
"we did not find X", "we did not look for X", and "the lookup failed"
as three distinguishable states. In a regulated workflow a visible gap
is correct and a fabricated answer is dangerous.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class SourceTier(IntEnum):
    """Trust ranking for a piece of evidence. Higher == more authoritative.

    Ranking uses tier first so a vendor's own marketing never outranks a
    regulatory record.
    """

    PRESS = 1
    VENDOR_SELF = 2
    VERIFIED_CUSTOMER = 3
    REGULATORY = 4


@dataclass(frozen=True)
class Evidence:
    """A single normalized, attributed finding."""

    id: str
    snippet: str
    source_url: str
    source_name: str
    provider: str
    source_tier: SourceTier
    retrieved_at: str
    query: str
    relevance: float
    raw: str


@dataclass(frozen=True)
class Failure:
    """A provider/source that errored or returned nothing for a query."""

    provider: str
    query: str
    error: str


@dataclass(frozen=True)
class EvidenceBundle:
    """Aggregated evidence plus the queries actually run and any failures."""

    evidence: tuple[Evidence, ...] = ()
    queries_run: tuple[str, ...] = ()
    failures: tuple[Failure, ...] = ()

    def state_for(self, query: str) -> str:
        """Distinguish failed / not_searched / found / not_found for a query.

        ``failed`` takes precedence: a lookup error must never be presented as
        a confident "not found".
        """
        if any(f.query == query for f in self.failures):
            return "failed"
        if query not in self.queries_run:
            return "not_searched"
        if any(e.query == query for e in self.evidence):
            return "found"
        return "not_found"
