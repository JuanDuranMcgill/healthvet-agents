"""Dependency-free helpers shared by the research-producing agents.

Kept free of band/langgraph imports so it is unit-testable in isolation. Covers
parsing a fresh trigger into a vendor name and turning an EvidenceBundle into a
contract ``ResearchResponse``.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Any

from research.contract import ResearchRequest, ResearchResponse, Status, parse
from research.models import EvidenceBundle
from research.sanitize import sanitize

_VENDOR_RE = re.compile(r"assessment on\s+(.+?)(?:[.\n]|$)", re.IGNORECASE)

# Band handles are namespaced under one prefix across the room. Resolve each
# role's handle from env (<ROLE>_HANDLE, e.g. RISK_HANDLE) so the chain works for
# any Band account; fall back to BAND_HANDLE_PREFIX/<role> if that var is unset.
HANDLE_PREFIX = os.getenv("BAND_HANDLE_PREFIX", "leejongmin1092")


def reply_handle(role: str) -> str:
    """Band @handle for a given agent role, from <ROLE>_HANDLE env or the prefix."""
    env = os.getenv(f"{role.upper()}_HANDLE")
    if env:
        return env if env.startswith("@") else f"@{env}"
    return f"@{HANDLE_PREFIX}/{role}"


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


def resolution_status(request: ResearchRequest, bundle: EvidenceBundle) -> Status:
    """Status for a re-investigation: are the requested gap directives resolved?

    A directive is resolved only if its scoped query returned evidence. Any
    unresolved directive yields NEEDS_REINVESTIGATION rather than a false COMPLETE.
    """
    if not request.gap_directives:
        return default_status(bundle)
    unresolved = [
        directive
        for directive in request.gap_directives
        if bundle.state_for(f"{request.vendor} {directive}") != "found"
    ]
    return Status.NEEDS_REINVESTIGATION if unresolved else Status.COMPLETE


def build_research_request(
    vendor: str,
    requested_by: str,
    gap_directives: list[str],
    goals: tuple[str, ...] = (),
    priority: str = "high",
) -> ResearchRequest:
    """Build a correlatable research_request for a scoped re-investigation."""
    return ResearchRequest(
        request_id=uuid.uuid4().hex[:12],
        requested_by=requested_by,
        vendor=vendor,
        summary=(
            f"{requested_by.title()} requests scoped re-investigation of "
            f"{len(gap_directives)} gap(s) for {vendor}"
        ),
        goals=tuple(goals),
        gap_directives=tuple(gap_directives),
        priority=priority,
    )


def vendor_from_messages(contents: list[str]) -> str:
    """Find the vendor: prefer a parsed contract message, else prose extraction."""
    for content in contents:
        parsed = parse(content)
        if parsed is not None and getattr(parsed, "vendor", ""):
            return parsed.vendor
    for content in contents:
        vendor = extract_vendor(content)
        if vendor:
            return vendor
    return ""


def directives_from_gap_report(report_text: str) -> list[str]:
    """Turn a Gap report's CRITICAL item lines into re-investigation directives.

    Matches item lines like ``- SOC 2 Type II: UNVERIFIED — CRITICAL — ...`` and
    ignores summary lines such as ``Critical gaps: 2``.
    """
    directives = []
    for raw in (report_text or "").splitlines():
        line = raw.strip()
        if not line.startswith("-") or "CRITICAL" not in line:
            continue
        body = line.lstrip("-").strip()
        item = body.split(":", 1)[0].strip()
        if item:
            directives.append(f"Find authoritative evidence for {item} (flagged CRITICAL)")
    return directives


def evidence_digest(bundle: EvidenceBundle, header: str = "Evidence") -> str:
    """Human/LLM-readable digest of a bundle. Snippets are sanitized as untrusted.

    Keeps 'failed' distinct from 'not found' so the reader is never misled.
    """
    if not bundle.evidence and not bundle.failures:
        return f"{header}: no evidence found, and no lookups failed."
    lines = [f"{header}:"]
    for i, ev in enumerate(bundle.evidence, 1):
        lines.append(f"[{i}] ({ev.source_tier.name}, {ev.provider}) {ev.source_url}")
        lines.append(sanitize(ev.snippet))
    if bundle.failures:
        fails = ", ".join(f"{f.provider} ({f.error})" for f in bundle.failures)
        lines.append(f"Lookups that FAILED (distinct from 'not found'): {fails}")
    return "\n".join(lines)


def directives_from_breakdown(breakdown: list[dict], threshold: int = 5) -> list[str]:
    """Turn low-scoring scorecard categories into targeted re-investigation directives.

    Reads already-computed scores only — it does not change any scoring logic.
    """
    directives = []
    for item in breakdown:
        if item.get("score", 10) < threshold:
            category = item.get("category", "unknown")
            directives.append(
                f"Find authoritative evidence for '{category}' "
                f"(current score {item.get('score')}/10)"
            )
    return directives


async def run_research_request(
    request: ResearchRequest,
    engine: Any,
    responded_by: str = "research",
) -> ResearchResponse:
    """Execute a (possibly scoped) research request and build a correlated response."""
    bundle = await engine.gather(
        request.vendor,
        goals=list(request.goals),
        gap_directives=list(request.gap_directives),
    )
    return build_response(
        request.vendor,
        request.request_id,
        responded_by,
        bundle,
        status=resolution_status(request, bundle),
    )
