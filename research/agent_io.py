"""Dependency-free helpers shared by the research-producing agents.

Kept free of band/langgraph imports so it is unit-testable in isolation. Covers
parsing a fresh trigger into a vendor name and turning an EvidenceBundle into a
contract ``ResearchResponse``.
"""
from __future__ import annotations

import re

from research.contract import ResearchResponse, Status
from research.models import EvidenceBundle

_VENDOR_RE = re.compile(r"assessment on\s+(.+?)(?:[.\n]|$)", re.IGNORECASE)


def extract_vendor(text: str) -> str:
    """Pull the vendor name out of a free-text assessment trigger."""
    match = _VENDOR_RE.search(text or "")
    if match:
        return match.group(1).strip()
    return (text or "").strip()


def default_status(bundle: EvidenceBundle) -> Status:
    """Honest status: failures with no evidence is FAILED, never a silent pass."""
    if not bundle.evidence and bundle.failures:
        return Status.FAILED
    if bundle.failures:
        return Status.PARTIAL
    return Status.COMPLETE


def _summary(vendor: str, responded_by: str, bundle: EvidenceBundle) -> str:
    parts = [f"{responded_by} returned {len(bundle.evidence)} evidence item(s) for {vendor}"]
    if bundle.failures:
        parts.append(f"{len(bundle.failures)} lookup(s) failed")
    return "; ".join(parts)


def build_response(
    vendor: str,
    request_id: str,
    responded_by: str,
    bundle: EvidenceBundle,
    status: Status | None = None,
) -> ResearchResponse:
    """Turn an EvidenceBundle into a correlated ResearchResponse."""
    return ResearchResponse(
        request_id=request_id,
        responded_by=responded_by,
        vendor=vendor,
        status=status or default_status(bundle),
        summary=_summary(vendor, responded_by, bundle),
        evidence=bundle.evidence,
        failures=bundle.failures,
    )
