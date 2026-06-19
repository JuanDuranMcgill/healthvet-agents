"""
Per-user, in-memory rate limiting (rolling window) to prevent abuse of the
public deployment. Keyed by the logged-in Google email.

Emails listed in UNLIMITED_EMAILS (comma-separated env var) bypass all limits —
use this for the owner's account.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def unlimited_emails() -> set[str]:
    raw = os.getenv("UNLIMITED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_unlimited(email: str | None) -> bool:
    return bool(email) and email.lower() in unlimited_emails()


def check(email: str | None, bucket: str, limit: int, window: int) -> tuple[bool, int]:
    """
    Returns (allowed, retry_after_seconds). Records the hit when allowed.
    `window` is in seconds. Owner emails always allowed.
    """
    if is_unlimited(email):
        return True, 0
    key = f"{email or 'anon'}:{bucket}"
    now = time.time()
    with _lock:
        dq = _hits[key]
        cutoff = now - window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return False, max(1, int(dq[0] + window - now))
        dq.append(now)
        return True, 0


# path -> list of (bucket, limit, window_seconds). Multiple buckets are ANDed.
# Tuned to comfortably demo while blocking runaway abuse.
LIMITS: dict[str, list[tuple[str, int, int]]] = {
    "/api/start_vetting":        [("vet_h", 6, 3600), ("vet_d", 20, 86400)],
    "/api/submit_questionnaire": [("q", 15, 3600)],
    # shared LLM-call budget across the auxiliary AI endpoints
    "/api/find_email":           [("llm", 60, 3600)],
    "/api/send_outreach":        [("llm", 60, 3600)],
    "/api/extract_pros_cons":    [("llm", 60, 3600)],
    "/api/clinical_insights":    [("llm", 60, 3600)],
    "/api/vendor_chat":          [("llm", 60, 3600)],
    "/api/compare":              [("llm", 60, 3600)],
}


def enforce(email: str | None, path: str) -> tuple[bool, int]:
    """Check all buckets configured for `path`. Returns (allowed, retry_after)."""
    for bucket, limit, window in LIMITS.get(path, []):
        ok, retry = check(email, bucket, limit, window)
        if not ok:
            return False, retry
    return True, 0
