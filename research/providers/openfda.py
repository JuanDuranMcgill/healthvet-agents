"""openFDA device clearance provider (510(k)). Authoritative, keyless.

Assumption to confirm live: device 510(k) endpoint at
``https://api.fda.gov/device/510k.json`` with ``search=applicant:"<vendor>"``.
Keyless but rate-limited (a free API key raises the limit). If ``OPENFDA_API_KEY``
is set it is appended.
"""
from __future__ import annotations

import os

from research.models import SourceTier
from research.providers.base import RawResult, SearchProvider

BASE_URL = "https://api.fda.gov/device/510k.json"
DEFAULT_LIMIT = 5
DEVICE_LOOKUP_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID="


class OpenFdaProvider(SearchProvider):
    name = "openfda"
    tier = SourceTier.REGULATORY

    def __init__(self, limit: int = DEFAULT_LIMIT, timeout: float = 10.0):
        self.limit = limit
        self.timeout = timeout

    async def search(self, query: str, **opts) -> list[RawResult]:
        import httpx

        # The engine passes a free-text query; openFDA needs a structured search.
        # We search the applicant (vendor) name carried in opts, falling back to query.
        applicant = opts.get("vendor") or query
        params = {"search": f'applicant:"{applicant}"', "limit": self.limit}
        if os.getenv("OPENFDA_API_KEY"):
            params["api_key"] = os.environ["OPENFDA_API_KEY"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(BASE_URL, params=params)
            if resp.status_code == 404:
                return []  # openFDA returns 404 for "no matches"
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            k_number = item.get("k_number", "")
            device = item.get("device_name", "")
            decision = item.get("decision_date", "")
            desc = item.get("decision_description", "")
            content = f"510(k) {k_number}: {device}. Decision {decision} ({desc})."
            results.append(RawResult(
                title=f"openFDA 510(k): {device}",
                url=f"{DEVICE_LOOKUP_URL}{k_number}",
                content=content,
                published_date=decision or None,
                relevance=0.8,
            ))
        return results
