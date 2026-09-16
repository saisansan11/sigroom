# UX-12 Lodging Cohort Roster Mobile Clarity — Handoff

Status: READY FOR PR

## Scope

Changed only the planned UX-12 source/test scope:

- `templates/lodging/cohort_detail.html`
- `static/css/app.css`
- `bookings/tests_ux12.py`
- `docs/plans/2026-09-16-ux-12-lodging-roster-mobile.md`
- `docs/handoffs/2026-09-16-ux-12-lodging-roster-mobile.md`

No views, services, models, URLs, settings, migrations, allocation rules, or check-in business logic were changed.

## Implementation

- Keeps one canonical semantic roster `<table>`.
- Mobile `<768px` renders roster rows as cards without horizontal scrolling.
- Desktop `>=768px` retains normal table layout.
- Preserves the exact `{% if students %}` behavior and the original seven roster values/order.
- Adds wrap-safe handling for long Thai names, units, phone, timestamps, and status metadata.
- Mobile CSV export CTA is full width with `min-height: 44px`.
- Preserves share URL, LINE share, QR, edit link, CSV route, and `copyShareLink` behavior.

## Antigravity / Repair Evidence

Repair attempt worktree:

`C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux12-base-20260916-131640-9147d8`

Antigravity exit: `0`

`deniedActionDetected=true` was reviewed. The log contained no out-of-scope source mutation; canonical source remained unchanged. The repair worktree source diff was limited to the three intended source/test files. QA helper files remained untracked and are not part of release scope.

The verified repair files and release-branch files were byte-equivalent under `git diff --no-index` for all three implementation files.

## Verification

- `git diff --check` — PASS
- Targeted regression:
  - `bookings/tests_ux12.py`
  - `bookings/tests_guest_and_lodging.py`
  - `bookings/tests_lodging_v4.py`
  - Result: **53 passed, 24 warnings**
- `manage.py check` — **0 issues**
- `manage.py makemigrations --check --dry-run` — **No changes detected**
- Full regression: **290 passed, 136 warnings**

## Real Browser QA

Authorized supervisor fixture was rendered through Django and opened in a real Chromium tab via CDP.

Viewports verified: `360`, `390`, `430`, `768`, `1280`, `1440`.

PASS criteria observed:

- no page, wrapper, table, row, or cell horizontal overflow
- mobile rows render as cards at 360/390/430
- desktop rows render as normal table rows at 768+
- one canonical roster table
- all 7 data labels preserved
- long Thai text wraps without overflow
- CSV CTA height >=44px and full-width on mobile
- visible keyboard focus outline on CSV CTA
- empty cohort preserves no-roster-table behavior
- CSS/JS assets loaded successfully (`pico.min.css`, `fonts.css`, `app.css`, `htmx.min.js` all HTTP 200)
- no console errors, runtime exceptions, or failed network loads

A standalone static QA server returned `404` for `manifest.webmanifest`; this is an artifact of the temporary static QA server and not an application asset regression. Required CSS/JS assets loaded successfully.

## Release Gate

Target base branch: `feat/lodging-v5-2`

Do not merge without a new explicit user merge instruction.
