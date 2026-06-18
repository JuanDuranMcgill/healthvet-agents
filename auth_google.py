"""
Google OAuth (login-only) for the HealthVet backend.

Self-contained: uses `requests` (already a dependency) and an in-memory session
store keyed by a random cookie. No external auth framework.

Enforcement is automatic: if GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are set,
auth is REQUIRED; if they are absent (local dev), auth is disabled and everyone
is treated as anonymous so the app still runs.

Env vars:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET   — OAuth client (Google Cloud Console)
  OAUTH_REDIRECT_URI                       — e.g. https://srv-dev-01.<tailnet>.ts.net/auth/google/callback
  ALLOWED_EMAILS (optional)                — comma-separated allowlist; empty = any Google account
"""
from __future__ import annotations

import os
import secrets
import time
import urllib.parse

import requests

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = "openid email profile"
SESSION_TTL = 60 * 60 * 12  # 12h

# session_id -> {"email", "name", "picture", "exp"}
_SESSIONS: dict[str, dict] = {}
# state -> exp  (CSRF protection for the OAuth round-trip)
_STATES: dict[str, float] = {}


def _client_id() -> str | None:
    return os.environ.get("GOOGLE_CLIENT_ID")


def _client_secret() -> str | None:
    return os.environ.get("GOOGLE_CLIENT_SECRET")


def _redirect_uri() -> str:
    return os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")


def _allowed_emails() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "").strip()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def auth_enabled() -> bool:
    """Auth is enforced only when an OAuth client is configured."""
    return bool(_client_id() and _client_secret())


# ---- OAuth flow ----
def build_auth_url() -> str:
    state = secrets.token_urlsafe(24)
    _STATES[state] = time.time() + 600
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, state: str) -> tuple[str | None, str | None]:
    """Returns (session_id, error). On success a session cookie value is returned."""
    # validate state
    exp = _STATES.pop(state, None)
    if not exp or exp < time.time():
        return None, "invalid_or_expired_state"

    resp = requests.post(TOKEN_ENDPOINT, data={
        "code": code,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "redirect_uri": _redirect_uri(),
        "grant_type": "authorization_code",
    }, timeout=15)
    if resp.status_code != 200:
        return None, f"token_exchange_failed: {resp.text[:200]}"
    access_token = resp.json().get("access_token")
    if not access_token:
        return None, "no_access_token"

    ui = requests.get(USERINFO_ENDPOINT,
                      headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if ui.status_code != 200:
        return None, "userinfo_failed"
    info = ui.json()
    email = (info.get("email") or "").lower()
    if not email:
        return None, "no_email"

    allow = _allowed_emails()
    if allow and email not in allow:
        return None, f"email_not_allowed: {email}"

    sid = secrets.token_urlsafe(32)
    _SESSIONS[sid] = {
        "email": email,
        "name": info.get("name", email),
        "picture": info.get("picture", ""),
        "exp": time.time() + SESSION_TTL,
    }
    return sid, None


# ---- session lookup ----
def get_session(session_id: str | None) -> dict | None:
    if not session_id:
        return None
    s = _SESSIONS.get(session_id)
    if not s:
        return None
    if s["exp"] < time.time():
        _SESSIONS.pop(session_id, None)
        return None
    return s


def destroy_session(session_id: str | None) -> None:
    if session_id:
        _SESSIONS.pop(session_id, None)
