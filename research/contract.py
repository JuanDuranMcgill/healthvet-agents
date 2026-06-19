"""Versioned Band message contract for research coordination.

Band messages carry only a text ``content`` field, so the structured schema is
embedded *inside* the message: a one-line human-readable summary (keeps the Band
room legible during a live demo) followed by a fenced ```json block (lets agents
parse a contract instead of scraping prose).

This module is the single source of truth for that schema. All agents serialize
and parse through here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum

from research.models import SourceTier, Evidence, Failure

VERSION = 1

_JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


class MessageType(str, Enum):
    REQUEST = "research_request"
    RESPONSE = "research_response"


class Status(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETE = "complete"
    FAILED = "failed"
    NEEDS_REINVESTIGATION = "needs_reinvestigation"


@dataclass(frozen=True)
class ResearchRequest:
    request_id: str
    requested_by: str
    vendor: str
    summary: str
    goals: tuple[str, ...] = ()
    gap_directives: tuple[str, ...] = ()
    priority: str = "normal"
    version: int = VERSION
    type: str = MessageType.REQUEST.value


@dataclass(frozen=True)
class ResearchResponse:
    request_id: str
    responded_by: str
    vendor: str
    status: Status
    summary: str
    evidence: tuple[Evidence, ...] = ()
    failures: tuple[Failure, ...] = ()
    version: int = VERSION
    type: str = MessageType.RESPONSE.value


def _evidence_to_dict(ev: Evidence) -> dict:
    return {
        "id": ev.id,
        "snippet": ev.snippet,
        "source_url": ev.source_url,
        "source_name": ev.source_name,
        "provider": ev.provider,
        "source_tier": int(ev.source_tier),
        "retrieved_at": ev.retrieved_at,
        "query": ev.query,
        "relevance": ev.relevance,
        "raw": ev.raw,
    }


def _evidence_from_dict(d: dict) -> Evidence:
    return Evidence(
        id=d["id"],
        snippet=d["snippet"],
        source_url=d["source_url"],
        source_name=d["source_name"],
        provider=d["provider"],
        source_tier=SourceTier(d["source_tier"]),
        retrieved_at=d["retrieved_at"],
        query=d["query"],
        relevance=d["relevance"],
        raw=d["raw"],
    )


def _failure_from_dict(d: dict) -> Failure:
    return Failure(provider=d["provider"], query=d["query"], error=d["error"])


def _to_payload(msg: ResearchRequest | ResearchResponse) -> dict:
    if isinstance(msg, ResearchRequest):
        return {
            "type": msg.type,
            "version": msg.version,
            "request_id": msg.request_id,
            "requested_by": msg.requested_by,
            "vendor": msg.vendor,
            "summary": msg.summary,
            "goals": list(msg.goals),
            "gap_directives": list(msg.gap_directives),
            "priority": msg.priority,
        }
    return {
        "type": msg.type,
        "version": msg.version,
        "request_id": msg.request_id,
        "responded_by": msg.responded_by,
        "vendor": msg.vendor,
        "status": msg.status.value,
        "summary": msg.summary,
        "evidence": [_evidence_to_dict(e) for e in msg.evidence],
        "failures": [
            {"provider": f.provider, "query": f.query, "error": f.error}
            for f in msg.failures
        ],
    }


def serialize(msg: ResearchRequest | ResearchResponse) -> str:
    """Render a contract message as a Band ``content`` string.

    Format: human summary line, blank line, fenced JSON payload.
    """
    payload = _to_payload(msg)
    block = json.dumps(payload, indent=2)
    return f"{msg.summary}\n\n```json\n{block}\n```"


def parse(content: str) -> ResearchRequest | ResearchResponse | None:
    """Extract a contract message from a Band ``content`` string.

    Returns ``None`` for plain prose or a malformed payload, so non-contract
    messages (e.g. the initial user prompt) are simply ignored.
    """
    if not content:
        return None
    match = _JSON_BLOCK.search(content)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None

    msg_type = payload.get("type")
    try:
        if msg_type == MessageType.REQUEST.value:
            return ResearchRequest(
                request_id=payload["request_id"],
                requested_by=payload["requested_by"],
                vendor=payload["vendor"],
                summary=payload["summary"],
                goals=tuple(payload.get("goals", ())),
                gap_directives=tuple(payload.get("gap_directives", ())),
                priority=payload.get("priority", "normal"),
                version=payload.get("version", VERSION),
            )
        if msg_type == MessageType.RESPONSE.value:
            return ResearchResponse(
                request_id=payload["request_id"],
                responded_by=payload["responded_by"],
                vendor=payload["vendor"],
                status=Status(payload["status"]),
                summary=payload["summary"],
                evidence=tuple(_evidence_from_dict(e) for e in payload.get("evidence", ())),
                failures=tuple(_failure_from_dict(f) for f in payload.get("failures", ())),
                version=payload.get("version", VERSION),
            )
    except (KeyError, ValueError):
        return None
    return None
