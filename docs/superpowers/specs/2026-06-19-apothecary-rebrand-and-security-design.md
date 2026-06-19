# HealthVet Rebrand (Apothecary) + Frontend Rebuild + Security Hardening

**Date:** 2026-06-19
**Status:** Approved in brainstorm (visual direction, logo, full-screen look all confirmed)
**Scope:** Three coupled deliverables that ship on the same site:
1. A new brand / design system ("Apothecary").
2. A full frontend rebuild (Vite + React + TS, static, served same-origin by the existing Python backend).
3. Anti-bot (Cloudflare Turnstile) + security hardening on the backend.

Backend API, auth flow, questionnaire engine, scoring, and the agent pipeline are
NOT rebuilt. The rebuild is frontend-only; the backend gains security middleware.

---

## 1. Brand / Design System ("Apothecary")

### Typography rule (HARD, project-wide)
Never use em dashes or middots in copy, UI, or docs. Use a longer blank space as a
separator instead (an em-space, or a fixed-width inline spacer). This applies to
every surface and all generated content.

### Palette (tokens)
| token | hex | use |
|---|---|---|
| `--bone` | `#F4EFE6` | app background |
| `--paper` | `#FBF8F2` | cards / surfaces |
| `--report` | `#FFFDF8` | white-paper report surface |
| `--ink` | `#2B2230` | primary text (aubergine-black) |
| `--muted` | `#6B6470` | secondary text |
| `--line` | `#E3DCCF` | borders / dividers |
| `--sage` | `#6E8F6B` | accent: approve / positive |
| `--terracotta` | `#C77B57` | accent: escalate / warm highlight |
| `--aubergine` | `#5A4A63` | accent: reject / deep |

Verdict styling: APPROVE = sage text on `rgba(110,143,107,.16)`; ESCALATE =
`#9a4f2c` on `rgba(199,123,87,.18)`; REJECT = aubergine on `rgba(90,74,99,.16)`.

### Fonts
- **Spectral** (serif): display, headings, numerals, report titles.
- **Inter** (sans): UI labels, body, tables, controls.
Loaded from Google Fonts with preconnect.

### Logo (final mark)
Two pills forming a V that also reads as a checkmark. Short ink pill (left) plus
one straight two-tone capsule (sage then terracotta) on the long arm, colinear,
round caps. Canonical SVG (viewBox `0 0 72 72`, stroke-width 13):
```
left  : (15,36) -> (31,53)      stroke ink
long-a: (31,53) -> (43.5,34.5)  stroke sage      (round caps)
long-b: (43.5,34.5) -> (56,16)  stroke terracotta
```
On dark, the ink arm becomes `--bone`. Provided as a React `<Logo>` component
(sizes: 24 favicon, 30 sidebar, 48 lockup, 120 hero) and a favicon.

### Surfaces and feel
White-paper aesthetic: bone background, paper cards with 1px `--line` borders,
12 to 16px radii, generous whitespace, quiet chrome, one warm accent per state.
The vendor Trust Report renders as a literal white-paper document (the `--report`
surface, a "Verified" seal, a sage to terracotta fit bar, dotted category rows).

---

## 2. Frontend rebuild (Vite + React + TypeScript)

### Why same-origin static
The app must keep being served by the Python backend over the Tailscale Funnel
URL so the Google session cookie and all JSON endpoints work without cross-origin
or Private-Network friction (the problem we already solved). So: build a static
SPA, output it to the directory the backend serves (`web/`), no separate host.

### Build + serve
- Vite builds to the backend's static dir (replaces the current `web/` contents).
- `web_server.py` serves `index.html` as an SPA fallback for any non-API,
  non-file GET path (client-side routing). API routes and real files are unchanged.
- Dev: `vite dev` proxies `/api` and `/auth` to the backend (or run against the
  Funnel URL); production is the static build.

### Routes / views
`/login`, `/onboarding` (questionnaire), `/` (dashboard), `/report/:taskId`,
`/assess`, `/priorities`. The first-time vs returning routing (from `/api/me`'s
`onboarded` flag) moves into a React auth guard: unauthenticated to `/login`;
authenticated and not onboarded to `/onboarding`; else the app.

### Components (each small, one purpose)
`Logo`, `AppShell` (sidebar + topbar), `NavItem`, `KpiTile`, `VendorTable` /
`VendorRow`, `VerdictChip`, `FitBar`, `TrustReport` (white-paper), `Questionnaire`
(ranking, sliders, deal-breakers, risk appetite, gap-mode), `LoginPage`,
`AssessForm`, `Toast`. A `theme.css` (or CSS vars module) holds the tokens above.

### API client
A thin `api.ts` wrapping `fetch` with `credentials: "include"`, hitting the
existing endpoints: `/api/me`, `/auth/google`, `/auth/logout`,
`/api/questionnaire`, `/api/submit_questionnaire`, `/api/profile`,
`/api/start_vetting`, `/api/vetting_status`, `/api/history`, plus the AI helper
endpoints. No endpoint changes.

### Preserved behavior
Google login, the onboarding-first routing, the questionnaire to profile flow,
the fit scorecard, rate limiting, and the agent pipeline all stay as-is.

---

## 3. Security hardening (backend)

### Cloudflare Turnstile (anti-bot)
- Turnstile widget on the **login page** and gating the **start-vetting** and
  **submit-questionnaire** actions.
- Backend verifies the token server-side via `siteverify` with the secret before
  honoring the action; failure returns 403.
- Env: `TURNSTILE_SITE_KEY` (frontend), `TURNSTILE_SECRET_KEY` (backend). If unset,
  verification is skipped (local dev), mirroring how Google auth degrades.

### Security headers (all responses, in `end_headers`)
`Content-Security-Policy` (allow `'self'`, Google Fonts `fonts.googleapis.com` /
`fonts.gstatic.com`, Turnstile `challenges.cloudflare.com`; `frame-ancestors 'none'`;
no inline script needed once React is bundled), `Strict-Transport-Security`,
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin`, a minimal `Permissions-Policy`.

### Auth / session hardening
- CSRF protection on state-changing POSTs (double-submit cookie or per-session
  token header checked server-side).
- Session cookie stays `HttpOnly; Secure; SameSite=None` (needed for any
  cross-site use); rotate the session id on each login; keep the 12h TTL.
- Keep strict OAuth `state` validation + expiry (already present).

### Input limits + abuse logging
- Cap POST body size (e.g. 64 KB) and reject oversize with 413.
- Validate / sanitize vendor names (length + allowed chars) and questionnaire
  payloads (known keys, numeric ranges) before use.
- Append-only audit log of auth events (login success or failure with email),
  vetting starts, and rate-limit / Turnstile rejections.

### Already in place (kept)
Per-user rate limiting with owner exemption; Google login required.

---

## Testing
- **Design system:** visual check of dashboard, login, questionnaire, report in
  the browser (Apothecary tokens, Spectral or Inter, logo, no dashes or middots).
- **Frontend:** SPA routes resolve, auth guard + onboarding redirect behave,
  questionnaire submits and scores, report renders; build artifact served
  same-origin and login round-trips end to end.
- **Security:** Turnstile blocks a tokenless POST (403); headers present on
  responses; oversize body rejected (413); CSRF-less POST rejected; audit log
  records a login and a vetting start.

## Out of scope
Backend API redesign, the agent pipeline, Band wiring, and the homelab/Funnel
deployment topology (unchanged). Tightening CORS to specific origins is deferred.

## Decisions pinned during the build plan
- Exact CSP string and Permissions-Policy values.
- CSRF mechanism (double-submit cookie vs per-session token) and where the SPA
  reads/sends it.
- Vite output wiring into `web/` and the backend SPA-fallback route.
