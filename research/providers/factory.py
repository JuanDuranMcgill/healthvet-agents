"""Provider bundles for the different agent lanes.

Scout owns the broad web sweep; Compliance owns the regulatory tiers. Phase 1
ships the web providers + openFDA + the OCR breach lookup. ONC CHPL is deferred.
"""
from __future__ import annotations

from research.providers.base import SearchProvider
from research.providers.ddg import DuckDuckGoProvider
from research.providers.exa import ExaProvider
from research.providers.ocr import OcrBreachProvider
from research.providers.openfda import OpenFdaProvider
from research.providers.tavily import TavilyProvider


def web_providers() -> list[SearchProvider]:
    """General web retrieval — Scout's broad sweep."""
    return [TavilyProvider(), ExaProvider(), DuckDuckGoProvider()]


def regulatory_providers() -> list[SearchProvider]:
    """Authoritative regulatory tiers — Compliance's lane."""
    return [OpenFdaProvider(), OcrBreachProvider()]


def default_providers() -> list[SearchProvider]:
    """Everything available in Phase 1."""
    return web_providers() + regulatory_providers()
