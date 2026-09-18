# SIGROOM UX-18 — Student Lodging Portal Mobile Clarity & Bed Selection Confidence — Handoff

## Status

LOCAL QUALITY GATE PASS — READY FOR COMMIT / PR

## Verified base

- Base branch: `feat/lodging-v5-2`
- Base SHA: `7fa589854117c4f9a5f72ab188b5a6b57e9e74d2` (merge of PR #40 / UX-17)
- UX-18 branch: `feat/ux-18-student-portal-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux18-student-portal-mobile`
- No model, service, URL, permission, transaction, or migration changes.

## Why UX-18

The public student lodging portal is the student-facing path for inspecting lodging rooms, choosing an available bed, and submitting the booking form. Existing business/privacy behavior was correct, but the page did not have a dedicated pass for the current `<768px` mobile standard. Narrow layouts could crowd the cohort/share row, room/bed rows, modal actions, and fixed next-free-bed control.

## Implemented scope

### `templates/lodging/student_portal.html`

- Added one scoped root hook: `.student-lodging-portal`.
- Added `.lodging-portal-share-btn`, `.bed-status-group`, and `.bed-action-group` hooks.
- Added an accessible free-bed label containing room code and bed number.
- Kept the existing POST target and all booking fields unchanged.
- Kept occupied-bed output status-only; no occupant identity was added.

### `static/css/app.css`

Added the scoped `UX-18 Student Lodging Portal Mobile Clarity` block:

- `<47.99rem`: stack cohort/share row; full-width touch-friendly share action.
- Two-column stats grid on phones, one column below 24rem.
- One minmax-safe room column.
- Stack room header and bed status/action rows.
- Full-width bed CTA with >=44px touch target.
- Stack booking modal actions.
- Constrain dialog height and allow internal vertical scrolling.
- Make sticky next-free-bed CTA wrapping-safe and safe-area aware.
- Add bottom breathing room so the fixed CTA does not cover final controls.
- Desktop behavior remains outside the UX-18 media query.

### `bookings/tests_ux18.py`

Added 8 UX-18 regression contracts covering public privacy, room+bed accessible labels, scoped breakpoint/layout rules, width-safe touch controls, modal actions, safe-area sticky CTA, preservation of booking/gallery/focus/reduced-motion hooks, and the unchanged booking POST contract.

## Automated verification

Observed on final source before commit:

- `uv run pytest bookings/tests_ux18.py -q` → **8 passed**
- `uv run pytest bookings/tests_ux18.py bookings/tests_v6_a.py bookings/tests_ui5.py -q` → **20 passed**
- `uv run manage.py check` → **0 issues**
- `uv run manage.py makemigrations --check --dry-run` → **No changes detected**
- `uv run pytest -q` → **449 passed, 170 warnings**
- `git diff --check` → **PASS**

Warnings are existing local-environment / Django transition warnings (pilot HTTP security warning, Django 6 URLField transition, and missing isolated-worktree `staticfiles/` warning), not UX-18 regressions.

## Real Browser QA

Live local Django page: `/lodging/c/nr-70/` using local PostgreSQL data.

| Width | Result |
| ---: | --- |
| 360 | PASS — no horizontal overflow; one-column mobile layout |
| 390 | PASS — no horizontal overflow; mobile layout and modal interactions |
| 430 | PASS — effective inner width 429; no horizontal overflow |
| 768 | PASS — two room columns; bed rows horizontal; sticky mobile CTA hidden |
| 1280 | PASS — three room columns; no horizontal overflow |
| 1440 | PASS — three room columns; no horizontal overflow |

Observed interactions:

- Local dataset exposed 4 rooms, 3 occupied beds, and 13 available-bed actions.
- Booking modal opens from a free-bed button.
- Initial modal focus moves into the dialog (`id_rank`).
- Modal has no horizontal overflow at 390px.
- Cancel closes the dialog and restores focus to the original `เลือกเตียงนี้` button.
- Sticky `ไปที่เตียงว่างถัดไป` action is visible on mobile and invokes the existing scroll behavior.
- Gallery production functions were exercised with two local static images: open → next → previous → close passed, with focus restored to the trigger.
- Public rendered content displayed occupied-bed status only and did not expose roommate/student identity.
- CDP capture recorded 0 page exceptions, console errors, page-log errors, network failures, and HTTP >=400 responses. PowerShell websocket wait errors after capture were helper/tooling noise, not page errors.

### Full-room Browser QA note

The local `nr-70` dataset had no fully occupied room during UX-18 QA. A temporary DB mutation to manufacture a full-room state was intentionally not forced after the safety layer blocked it. The full-room server path is unchanged by UX-18 and is covered by the existing lodging/V6 regression suite included in the 449-test full run. Browser QA covered mixed occupied/free beds and every UX-18 presentation/interaction change.

## Privacy / business invariants preserved

- `is_active` remains the portal open/closed control.
- `allocation_status` semantics are unchanged.
- No conflict, transaction, race, validation, phone-normalization, authorization, or admin logic changed.
- Occupied beds remain status-only in the public portal.
- No PII fields were added to page context or markup.
- No migrations.
- Existing modal error re-open, gallery, focus restoration, and reduced-motion behavior remain present.

## QA cleanup

All QA-only artifacts and browser emulation helpers were removed before release staging. Browser device-metrics override was cleared. No QA marker or temporary wrapper is part of the source diff.

## Files in scope

- `templates/lodging/student_portal.html`
- `static/css/app.css`
- `bookings/tests_ux18.py`
- `docs/plans/2026-09-18-ux-18-student-portal-mobile.md`
- `docs/handoffs/2026-09-18-ux-18-student-portal-mobile.md`

## Release steps

1. Final status/diff review.
2. Stage only the five UX-18 files above.
3. Commit: `feat(ux-18): improve student lodging portal on mobile`
4. Push `feat/ux-18-student-portal-mobile`.
5. Open PR into `feat/lodging-v5-2`.
6. Re-review PR diff and verify final head SHA.
7. Wait for aggregate `SIGROOM PR Safety` / `PR Safety Gate`.
8. Stop at **READY FOR MERGE**. Merge requires a separate explicit user instruction naming the PR.

## Next phase

After UX-18 is explicitly approved and merged, re-fetch the protected integration branch and discover UX-19 from current product evidence rather than assuming a target.